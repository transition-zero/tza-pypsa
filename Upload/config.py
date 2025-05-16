DATA_FORMAT = "csv"  # CHANGE if your file is xlsx
DELIMITER = ","  # CHANGE if delimiter of CSV is not a comma, keep as it is for xlsx
LOCAL_FILE_PATH =  "C:/Users/jy/Projects/tza-pypsa/India_C&I_hourly_testing.csv"  # Eg:"/Users/galib.ktransitionzero.org/Downloads/IEMOP_mnm_data.csv"
RAW_OBJECT_NAME = "India_C&I_hourly_testing_data"  # Eg:"IEMOP_mnm_data"
RAW_CONTENT_TYPE = "text/csv"  # CHANGE if your file is xlsx
LANDING_OBJECT_NAME = "India_C&I_hourly_testing_data"  # Eg: "IEMOP_mnm_data"
DATASET_ID = (
    "india_pypsa_outputs"  # Allowed values: "india_pypsa_outputs", "taiwan_pypsa_outputs", "japan_pypsa_outputs", "ASEAN_pysa_outputs"
)
BIGQUERY_TABLE_NAME = "India_greenfield_hourly_testing"  # Eg: "IEMOP_mnm_data"
BIGQUERY_WRITE_METHOD = (
    "WRITE_APPEND"  # CHANGE to "WRITE_TRUNCATE" to overwrite, "WRITE_APPEND" to append to existing data
)
SKIP_ROWS = 1  # Set to 1 if your CSV has a header row else set to 0 (set to 0 for XLSX files)
# If you want to use a custom schema, define it below (else set to None)
CUSTOM_SCHEMA = None  # Eg: [bigquery.SchemaField("column1", "STRING"), bigquery.SchemaField("column2", "INTEGER")]


def preprocess_dataframe(df):
    """
    Users can edit this function to perform any custom preprocessing on the DataFrame.
    Args:
        df (pd.DataFrame): The DataFrame loaded from GCS, after cleaning.
    Returns:
        pd.DataFrame: The processed DataFrame ready for upload.
    """
    # By default, return df unchanged
    return df
