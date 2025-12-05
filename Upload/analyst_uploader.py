# =============================================================================
#                          BIGQUERY LARGE DATA UPLOAD TEMPLATE
# This script helps you:
#   1. Upload files to Google Cloud Storage (GCS)
#   2. Clean them for BigQuery compatibility
#   3. Move files between buckets
#   4. Load data into BigQuery with an archive link
# =============================================================================

# =============================================================================
#                          BIGQUERY LARGE DATA UPLOAD TEMPLATE (w/ NC support)
# =============================================================================

import datetime
 
import logging
import os
import re
import threading
from collections import defaultdict
from io import BytesIO
from tempfile import NamedTemporaryFile

import config
import pandas as pd
import pypsa
from config import preprocess_dataframe
from google.cloud import bigquery, storage
from transform_nc_for_visualisation import transform_visualiser_hourly_output, transform_visualiser_yearly_output

# =============================================================================
#                                CONFIGURATION
# =============================================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATE_STR = datetime.date.today().isoformat()  # 'YYYY-MM-DD'
STORAGE_CLIENT = storage.Client()
CLIENT = bigquery.Client()

ALLOWED_DATASETS = {"india_pypsa_outputs", "taiwan_pypsa_outputs", "japan_pypsa_outputs", "ASEAN_pypsa_outputs", "japan_occto_lnd"}

# =============================================================================
#                               HELPER FUNCTIONS
# =============================================================================

def validate_config():
    """Validate that required config values are set."""
    required_fields = ['LOCAL_FILE_PATH', 'RAW_OBJECT_NAME', 'LANDING_OBJECT_NAME', 'DATASET_ID', 'BIGQUERY_TABLE_NAME']
    for field in required_fields:
        value = getattr(config, field)
        if value is None:
            raise ValueError(f"Configuration error: {field} must be set before running")
        if not isinstance(value, str):
            raise ValueError(f"Configuration error: {field} must be a string")
    
    logger.info("Configuration validated successfully")
    logger.info("  Using configuration:  ")
    logger.info(f"  LOCAL_FILE_PATH: {config.LOCAL_FILE_PATH}")
    logger.info(f"  RAW_OBJECT_NAME: {config.RAW_OBJECT_NAME}")
    logger.info(f"  LANDING_OBJECT_NAME: {config.LANDING_OBJECT_NAME}")
    logger.info(f"  DATASET_ID: {config.DATASET_ID}")
    logger.info(f"  BIGQUERY_TABLE_NAME: {config.BIGQUERY_TABLE_NAME}")

def blob_from_bucket(bucket_name: str, file_name: str, client: storage.Client = STORAGE_CLIENT) -> storage.Blob:
    bucket = client.get_bucket(bucket_name)
    return bucket.blob(file_name)


def upload_raw_to_gcs_async(
    file_path: str,
    object_name: str,
    content_type: str,
    bucket_name: str = "raw_analyst_uploads",
    client: storage.Client = STORAGE_CLIENT,
) -> None:
    """Uploads the file to GCS asynchronously in a background thread."""

    def upload():
        try:
            dated_object_name = f"{DATE_STR}/{object_name}"
            blob = blob_from_bucket(bucket_name=bucket_name, file_name=dated_object_name, client=client)
            with open(file_path, "rb") as file:
                blob.upload_from_file(file, content_type=content_type)
            logger.info(f"Successfully uploaded {object_name} to GCS bucket {bucket_name}.")
        except Exception as e:
            logger.error(f"Failed to upload file to GCS: {str(e)}")

    thread = threading.Thread(target=upload, daemon=True)
    thread.start()


def async_upload_and_load(df_to_upload: pd.DataFrame, table_name: str, object_name: str):
    def task():
        try:
            # Add archive_link before any uploading
            archive_link = f"gs://landing_analyst_uploads/{DATE_STR}/{object_name}"
            df_to_upload["archive_link"] = archive_link

            # 1. Upload to GCS (archival)
            pandas_to_gcs(df_to_upload, object_name=object_name, data_format="csv")

            client = CLIENT
            job_config = bigquery.LoadJobConfig(
                write_disposition=config.BIGQUERY_WRITE_METHOD,
                schema=config.CUSTOM_SCHEMA,
                autodetect=not config.CUSTOM_SCHEMA,
            )

            client.load_table_from_dataframe(
                df_to_upload,
                destination=f"{client.project}.{config.DATASET_ID}.{table_name}",
                job_config=job_config,
            ).result()

            logger.info(f"Uploaded {object_name} to GCS and loaded DataFrame into BigQuery table {table_name}")
        except Exception as e:
            logger.error(f"Failed to upload and load for {table_name}: {e}")

    thread = threading.Thread(target=task, daemon=True)
    thread.start()
    return thread


def pandas_to_gcs(
    df: pd.DataFrame,
    object_name: str,
    bucket_name: str = "landing_analyst_uploads",
    data_format: str = "csv",
    client: storage.Client = STORAGE_CLIENT,
) -> None:

    try:
        dated_object_name = f"{DATE_STR}/{object_name}"
        logger.info(f"Starting upload of DataFrame to GCS: {bucket_name}/{dated_object_name}")
        blob = blob_from_bucket(bucket_name=bucket_name, file_name=dated_object_name, client=client)

        df = df.copy()
        df["write_dt"] = pd.Timestamp.now()

        buffer = BytesIO()
        if data_format == "csv":
            df.to_csv(buffer, index=False)
            content_type = "text/csv"
        elif data_format == "xlsx":
            df.to_excel(buffer, index=False)
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            raise ValueError(f"Invalid data format: {data_format}")

        buffer.seek(0)
        blob.upload_from_file(buffer, content_type=content_type)
        logger.info(f"Successfully uploaded DataFrame to GCS: {bucket_name}/{dated_object_name}")
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
    pattern = re.compile(r"(?i)^(n/a|none|nan|na|-)$")
    df.replace(to_replace=pattern, value=None, regex=True)
    # We are not dropping null columns at this stage -- log as warning
    logger.warning(f"{df.columns[df.isnull().all()]} column(s) entirely null in source")

    logger.info(f"Column name cleaning complete: {df.shape[1]} headers cleaned")
    # Print header transformations side by side
    logging_message = ""
    for raw_col, cleaned_col in zip(raw_data.columns, df.columns):
        logging_message += f"{raw_col} -> {cleaned_col}\n"
    logger.info(logging_message)
    return df


# =============================================================================
#                 NEW: .NC CONVERSION FUNCTION (for PyPSA)
# =============================================================================


def export_pypsa_outputs_to_df(data) -> pd.DataFrame:
    """Download .nc file from GCS, load with PyPSA, and apply both hourly + yearly transforms."""

    with NamedTemporaryFile(delete=False, suffix=".nc") as tmp_file:
        tmp_file.write(data)
        tmp_file.close()

    network = pypsa.Network(tmp_file.name)

    # Apply visualiser transforms
    df_hourly = transform_visualiser_hourly_output(network)
    df_yearly = transform_visualiser_yearly_output(network)
    df_combined = pd.concat([df_hourly, df_yearly], ignore_index=True)

    os.remove(tmp_file.name)
    return df_combined


def get_raw_content_type(file_type: str) -> str:
    """
    Returns the appropriate raw content type based on file type string.

    Args:
        file_type (str): Type of the file (e.g., 'csv', 'nc', 'xlsx')

    Returns:
        str: Corresponding MIME type for the file
    """
    file_type = file_type.lower()

    mime_types = {
        "csv": "text/csv",
        "nc": "application/x-netcdf",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    if file_type in mime_types:
        return mime_types[file_type]
    else:
        raise ValueError(f"Unsupported file type: {file_type}")


# =============================================================================
#                                  USAGE
# =============================================================================


def main():
    """Main function to process and upload data."""
    # Validate config values before proceeding
    validate_config()
    
    if config.DATASET_ID not in ALLOWED_DATASETS:
        raise PermissionError(
            f"Unauthorized DATASET_ID '{config.DATASET_ID}'. " f"Allowed values are: {', '.join(ALLOWED_DATASETS)}"
        )
    data_format = config.DATA_FORMAT.lower()

    assert data_format in [
        "csv",
        "xlsx",
        "nc",
    ], f"Unsupported data format: {data_format}. Only 'csv', 'xlsx', or 'nc' are supported."
    assert (
        data_format in config.LOCAL_FILE_PATH
    ), f"Local file path {config.LOCAL_FILE_PATH} does not match the expected data format: {data_format}."

    raw_content_type = get_raw_content_type(data_format)

    upload_raw_to_gcs_async(
        file_path=config.LOCAL_FILE_PATH, object_name=config.RAW_OBJECT_NAME, content_type=raw_content_type
    )

    # Proceed immediately with loading the local file into pandas
    if data_format == "csv":
        df = pd.read_csv(config.LOCAL_FILE_PATH, delimiter=config.DELIMITER)
    elif data_format == "xlsx":
        df = pd.read_excel(config.LOCAL_FILE_PATH)
    elif data_format == "nc":
        with open(config.LOCAL_FILE_PATH, "rb") as f:
            nc_data = f.read()
        df = export_pypsa_outputs_to_df(nc_data)
    else:
        raise ValueError(f"Unsupported data format: {data_format}")

    df = clean_raw_data_for_bq(df, convert_to_str=False)
    df = preprocess_dataframe(df)

    if data_format == "nc":

        df_hourly = df[df["time_resolution"] == "hourly"].copy()
        df_yearly = df[df["time_resolution"] == "yearly"].copy()

        t_hourly = async_upload_and_load(
            df_to_upload=df_hourly,
            table_name=f"{config.BIGQUERY_TABLE_NAME}_hourly",
            object_name=f"{config.LANDING_OBJECT_NAME}_hourly",
        )
        t_yearly = async_upload_and_load(
            df_to_upload=df_yearly,
            table_name=f"{config.BIGQUERY_TABLE_NAME}_yearly",
            object_name=f"{config.LANDING_OBJECT_NAME}_yearly",
        )

        threads = [t_hourly, t_yearly]
        for t in threads:
            t.join()

    else:

        t = async_upload_and_load(
            df_to_upload=df, table_name=config.BIGQUERY_TABLE_NAME, object_name=config.LANDING_OBJECT_NAME
        )
        t.join()


if __name__ == "__main__":
    main()
