# IMPORTTANT
# IF CSV OR XLSX FILES ARE SELECTED THIS CODE IS NOT OPINIONATED -- IT WILL UPLOAD YOUR FILE AS IS
# IF NC FILES ARE SELECTED THIS CODE IS OPINIONATED and will transform your data.
# IT HAS BEEN TESTED FOR SOME NC FILES BUT NOT ALL SO MAY NOT WORK FOR YOUR FILE
# the nc file for visualisation -- SEE export_pypsa_outputs_to_df function and transform_nc_for_visualisation.py
# it will create an hourly and yearly table from the nc file
# make a branch and alter these functions to suit your needs

DATA_FORMAT = "csv"  # CHANGE if your file is xlsx
DELIMITER = ","  # CHANGE if delimiter of CSV is not a comma, keep as it is for xlsx
LOCAL_FILE_PATH = "C:/Users/jy/Projects/tza-pypsa/japan_brownfield_yearly_016.csv"  # Eg:"/Users/galib.ktransitionzero.org/Downloads/IEMOP_mnm_data.csv"
RAW_OBJECT_NAME = "japan_brownfield_yearly_016"  # Eg:"IEMOP_mnm_data"
LANDING_OBJECT_NAME = "japan_brownfield_yearly_016"  # Eg: "IEMOP_mnm_data"
DATASET_ID = "japan_pypsa_outputs"  # Eg: "japan_pypsa_outputs". for full list see analyst_uploader.py
BIGQUERY_TABLE_NAME = "japan_brownfield_yearly_016"  # Eg: "IEMOP_mnm_data"
BIGQUERY_WRITE_METHOD = (
    "WRITE_APPEND"  # CHANGE to "WRITE_TRUNCATE" to overwrite, "WRITE_APPEND" to append to existing data
)
SKIP_ROWS = 1  # Set to 1 if your CSV has a header row else set to 0 (set to 0 for XLSX files)
# If you want to use a custom schema, define it below (else set to None)
CUSTOM_SCHEMA = None  # Eg: [bigquery.SchemaField("column1", "STRING"), bigquery.SchemaField("column2", "INTEGER")]

# NC FILES ONLY. NO NEED TO FILL IF NOT NC FILES
MARKET = "PLEASE CHANGE TO YOUR COUNTRY"  # CHANGE to "ASEAN", "JAPAN", "TAIWAN" or "INDIA"
PYPSA_RUN_ID = "PLEASE CHANGE TO YOUR RUN ID"  # CHANGE to your pypsa run id


def preprocess_dataframe(df):
    """
    Users can edit this function to perform any custom preprocessing on the DataFrame. This processing will
    NOT edit raw files, it will process between raw and landing. All changes applied to landing and BQ tables.
    Args:
        df (pd.DataFrame): The DataFrame loaded from GCS, after cleaning.
    Returns:
        pd.DataFrame: The processed DataFrame ready for upload.
    """
    # By default, return df unchanged
    # eg. df["model_metadata"] = "my metadata here"
    return df
