# =============================================================================
#                          BIGQUERY LARGE DATA UPLOAD TEMPLATE
# This script helps you:
#   1. Upload files to Google Cloud Storage (GCS)
#   2. Clean them for BigQuery compatibility
#   3. Move files between buckets
#   4. Load data into BigQuery with an archive link
# =============================================================================

import datetime
import logging
import re
from collections import defaultdict
from io import BytesIO, StringIO
import time

import config
import pandas as pd
from config import preprocess_dataframe

# --- IMPORTS ---
from google.cloud import bigquery, storage

# =============================================================================
#                                CONFIGURATION
# =============================================================================

DATASET_ID = config.DATASET_ID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATE_STR = datetime.date.today().isoformat()  # 'YYYY-MM-DD'
STORAGE_CLIENT = storage.Client()
CLIENT = bigquery.Client()

# =============================================================================
#                               HELPER FUNCTIONS
# =============================================================================


def blob_from_bucket(bucket_name: str, file_name: str, client: storage.Client = STORAGE_CLIENT) -> storage.Blob:
    """Helper function for GCS files."""
    bucket = client.get_bucket(bucket_name)
    return bucket.blob(file_name)


def upload_raw_to_gcs(
    file_path: str,
    object_name: str,
    content_type: str,
    bucket_name: str = "raw_analyst_uploads",
    client: storage.Client = STORAGE_CLIENT,
) -> None:
    """
    Upload a file to a Google Cloud Storage bucket.
    """
    try:
        dated_object_name = f"{DATE_STR}/{object_name}"
        blob = blob_from_bucket(bucket_name=bucket_name, file_name=dated_object_name, client=client)
        start_ts = time.perf_counter()
        with open(file_path, "rb") as file:
            blob.upload_from_file(file, content_type=content_type)
        end_ts = time.perf_counter()
        elapsed = end_ts - start_ts
        logger.info(
            f"Successfully uploaded {object_name} to GCS bucket {bucket_name} "
            f"Local CSV file to GCS upload took {elapsed:.2f} seconds"
        )

    except Exception as e:
        raise RuntimeError(f"Failed to upload file to GCS: {str(e)}")


def gcs_to_pandas(
    object_name: str,
    bucket_name: str = "raw_analyst_uploads",
    client: storage.Client = STORAGE_CLIENT,
    data_format: str = "csv",
    delimiter: str = ",",  # <-- Add delimiter here, default to comma
    **read_kwargs,
) -> pd.DataFrame:
    """
    Load a CSV or XLSX file from GCS into a pandas DataFrame.
    Args:
        bucket_name (str): Name of the GCS bucket.
        object_name (str): Path to the file in the bucket.
        client (storage.Client): GCS client.
        data_format (str): "csv" or "xlsx".
        delimiter (str): Delimiter to use for CSV files. Default is ','.
        **read_kwargs: Any extra keyword arguments for pandas read_csv/read_excel.
    Returns:
        pd.DataFrame: The loaded DataFrame.
    """
    dated_object_name = f"{DATE_STR}/{object_name}"
    blob = blob_from_bucket(bucket_name, dated_object_name, client)
    start_ts = time.perf_counter()
    data = blob.download_as_bytes()
    if data_format == "csv":
        df = pd.read_csv(BytesIO(data), delimiter=delimiter, **read_kwargs)
    elif data_format == "xlsx":
        df =  pd.read_excel(BytesIO(data), **read_kwargs)
    else:
        raise ValueError("data_format must be 'csv' or 'xlsx'")
    end_ts = time.perf_counter()
    elapsed = end_ts - start_ts
    logger.info(f"GCS to pandas processing took {elapsed:.2f} seconds")
    return df


def pandas_to_gcs(
    df: pd.DataFrame,
    object_name: str,
    bucket_name: str = "landing_analyst_uploads",
    data_format: str = "csv",
    client: storage.Client = STORAGE_CLIENT,
) -> None:
    """
    Convert a pandas DataFrame to CSV or XLSX (with a write_dt column) and upload it to Google Cloud Storage.

    Args:
        df (pd.DataFrame): The DataFrame to be uploaded.
        bucket_name (str): The name of the GCS bucket.
        object_name (str): The name (including path) of the object in the bucket.
        data_format (str): The format to convert the DataFrame to. Either "csv" or "xlsx". Defaults to "csv".

    Raises:
        Exception: If there's an error during the upload process.
    """
    try:
        dated_object_name = f"{DATE_STR}/{object_name}"
        logger.info(f"Starting upload of DataFrame to GCS: {bucket_name}/{dated_object_name}")
        blob = blob_from_bucket(bucket_name=bucket_name, file_name=dated_object_name, client=client)

        # Add write_dt column with current timestamp
        df = df.copy()
        df["write_dt"] = pd.Timestamp.now()
        start_ts = time.perf_counter()

        # Prepare the data
        if data_format == "csv":
            buffer = BytesIO()
            df.to_csv(buffer, index=False)
            buffer.seek(0)
            blob.upload_from_file(buffer, content_type="text/csv")
        elif data_format == "xlsx":
            buffer = BytesIO()
            df.to_excel(buffer, index=False)
            buffer.seek(0)
            blob.upload_from_file(
                buffer, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            raise ValueError(f"Invalid data format: {data_format}")

        end_ts = time.perf_counter()
        elapsed = end_ts - start_ts
        logger.info(f"Upload of DataFrame to GCS took {elapsed:.2f} seconds for '{object_name}'")
        logger.info(f"Successfully uploaded DataFrame to GCS: {bucket_name}/{object_name}")
    except Exception as e:
        raise RuntimeError(f"Failed to upload DataFrame to GCS: {str(e)}")


def clean_raw_data_for_bq(raw_data: pd.DataFrame, convert_to_str: bool = True) -> pd.DataFrame:
    """
    Cleans a dataframe to make it BigQuery compatible.
    Column name transformations are as follows:
    1) remove unwanted chars
        a) replace each occurrence with an underscore
        b) remove leading and trailing underscores
        c) remove multiple consecutive underscores
    2) ensure the name does not exceed BQ char limit
    3) signal empty headers in source with 'empty_header'
    4) append _n to duplicate column names (i.e. two input 'system' cols would become 'system' and 'system_1')
    5) convert all values to string type
    6) replace all null-type values with None

    Args:
        raw_data: input df

    Returns:
        df: The cleaned df ready for ingestion
    """

    def clean_col_name(col: str) -> str:
        col = str(col).lower().strip()
        # 1) remove unsupported chars
        # For full list, see: https://cloud.google.com/bigquery/docs/schemas#flexible-column-names
        new_name = re.sub(r"[ \[\]!\"()*,./;?@\\^`{}~-]", "_", col)
        new_name = new_name.strip("_")
        new_name = re.sub(r"_+", "_", new_name)

        new_name = re.sub(r"\$", "dollar", new_name)
        new_name = re.sub(r"\£", "gbp", new_name)

        # 2) ensure the name does not exceed 300 chars
        if len(new_name) > 300:
            logger.warning(f"Column name {col} exceeds BQ character limit. Truncating to 300 characters.")
            new_name = new_name[:300]

        # 3) signal empty headers as a precaution against data loss
        new_name = new_name if new_name else "empty_header"
        return new_name

    start_ts = time.perf_counter()
    df = raw_data.rename(columns=clean_col_name)

    # Rename columns with duplicate names by appending _n from 2nd occurrence (n starts at 1)
    renamer = defaultdict()
    for column_name in df.columns[df.columns.duplicated(keep=False)].tolist():
        if column_name in renamer:
            renamer[column_name].append(column_name + "_" + str(len(renamer[column_name])))
        else:
            renamer[column_name] = [column_name]
    df.rename(
        columns=lambda column_name: renamer[column_name].pop(0) if column_name in renamer else column_name, inplace=True
    )

    if convert_to_str:
        # Convert all values to string
        df = df.astype(str)
    # Replace all NaN and null values with BQ-compatible None (case insensitive regex match)
    df = df.where(pd.notnull(df), None)  # this doesnt always seem to work
    df = df.replace(r"(?i)^(n/a|none|nan|na|-)$", None, regex=True)

    end_ts = time.perf_counter()
    elapsed = end_ts - start_ts

    logger.info(f"Data cleaning took {elapsed:.2f} seconds")
    # We are not dropping null columns at this stage -- log as warning
    logger.warning(f"{df.columns[df.isnull().all()]} column(s) entirely null in source")

    logger.info(f"Column name cleaning complete: {df.shape[1]} headers cleaned")
    # Print header transformations side by side
    logging_message = ""
    for raw_col, cleaned_col in zip(raw_data.columns, df.columns):
        logging_message += f"{raw_col} -> {cleaned_col}\n"
    logger.info(logging_message)
    return df


def load_file_to_bigquery(
    table_name: str,
    skip_leading_rows: int,
    write_disposition: str,  # "WRITE_TRUNCATE" or "WRITE_APPEND"
    gcs_uri: str = f"gs://landing_analyst_uploads/{DATE_STR}/{config.LANDING_OBJECT_NAME}",
    dataset_id: str = DATASET_ID,
    source_format: str = "CSV",  # "CSV" or "XLSX"
    schema: list = None,  # List of bigquery.SchemaField
    enable_character_map_v2: bool = False,
    client: bigquery.Client = CLIENT,
    project_id: str = "tz-data-dev",
) -> None:
    """
    Helper function to load CSV or XLSX data into BigQuery with an archive_link column.
    Allows specifying a custom schema.

    Parameters:
        client (bigquery.Client): BigQuery client instance.
        project_id (str): The GCP project ID.
        dataset_id (str): The BigQuery dataset ID.
        table_name (str): The name of the BigQuery table.
        gcs_uri (str): The GCS URI of the file to load, also used as the archive link.
        skip_leading_rows (int): Number of header rows to skip (applies to CSV, ignored for XLSX).
        write_disposition (str): BigQuery write disposition, e.g., WRITE_TRUNCATE or WRITE_APPEND.
        source_format (str): "CSV" or "XLSX".
        schema (list): Optional; list of bigquery.SchemaField to specify schema and types.
        enable_character_map_v2 (bool, optional): Flag to enable character map V2.

    Returns:
        None
    """

    table_id = f"{project_id}.{dataset_id}.{table_name}"

    # Set source format for BigQuery
    if source_format.upper() == "CSV":
        bq_source_format = bigquery.SourceFormat.CSV
    elif source_format.upper() == "XLSX":
        bq_source_format = bigquery.SourceFormat.EXCEL
    else:
        raise ValueError("source_format must be either 'CSV' or 'XLSX'")

    # Only use schema if it's not None and not empty
    autodetect = not (schema and len(schema) > 0)

    # Configure job config
    job_config = bigquery.LoadJobConfig(
        source_format=bq_source_format,
        skip_leading_rows=skip_leading_rows if bq_source_format == bigquery.SourceFormat.CSV else 0,
        write_disposition=write_disposition,
        autodetect=autodetect,
        schema=schema if schema else None,
        field_delimiter=",",  # Explicit for CSV; ignored for XLSX
    )

    # Enable Character Map V2 if specified
    if enable_character_map_v2:
        job_config.column_name_character_map = "V2"
        logger.info("Character Map V2 is enabled.")

    # Load data from GCS to BigQuery table
    start_ts = time.perf_counter()
    load_job = client.load_table_from_uri(gcs_uri, table_id, job_config=job_config)
    load_job.result()  # Wait for the job to complete
    end_ts = time.perf_counter()
    elapsed = end_ts - start_ts

    logger.info(f"BigQuery load job took in {elapsed:.2f} seconds")
    logger.info(f"Loaded data from {gcs_uri} to BigQuery table {table_id}")

    # Add the archive_link column to the table (if not present)
    add_archive_link_column = f"""
    ALTER TABLE {table_id}
    ADD COLUMN IF NOT EXISTS archive_link STRING
    """
    add_archive_column_data = f"""
    UPDATE {table_id}
    SET archive_link = '{gcs_uri}'
    WHERE write_dt = (SELECT MAX(write_dt) FROM {table_id})
    """
    client.query(add_archive_link_column).result()
    client.query(add_archive_column_data).result()

    logger.info(f"Added archive_link column to table {table_id} with value {gcs_uri}")


# =============================================================================
#                                  USAGE
# =============================================================================
def main():
    # --- STEP 1: Upload raw file from local to GCS ---
    upload_raw_to_gcs(config.LOCAL_FILE_PATH, config.RAW_OBJECT_NAME, config.RAW_CONTENT_TYPE)

    # --- STEP 2: Load the file from GCS into a pandas DataFrame ---
    df = gcs_to_pandas(
        object_name=config.RAW_OBJECT_NAME,
        data_format=config.DATA_FORMAT,
        delimiter=config.DELIMITER,
    )
    # --- STEP 3: Clean and process the DataFrame for BigQuery compatibility ---
    df = clean_raw_data_for_bq(df, convert_to_str=False)

    df = preprocess_dataframe(df)

    # --- STEP 4: Upload cleaned and processed data to a landing bucket in GCS ---
    pandas_to_gcs(
        df,
        object_name=config.LANDING_OBJECT_NAME,
        data_format=config.DATA_FORMAT,
    )

    # Validate dataset id
    ALLOWED_DATASETS = {"india_pypsa_outputs", "taiwan_pypsa_outputs", "japan_pypsa_outputs", "ASEAN_pypsa_outputs"}

    if config.DATASET_ID not in ALLOWED_DATASETS:
        raise PermissionError(
            f"Unauthorized DATASET_ID '{config.DATASET_ID}'. " f"Allowed values are only: {', '.join(ALLOWED_DATASETS)}"
        )

    load_file_to_bigquery(
        table_name=config.BIGQUERY_TABLE_NAME,
        skip_leading_rows=config.SKIP_ROWS,
        write_disposition=config.BIGQUERY_WRITE_METHOD,
        source_format=config.DATA_FORMAT,
        schema=config.CUSTOM_SCHEMA,
    )


if __name__ == "__main__":
    main()
# =============================================================================
#                                  END
# =============================================================================
