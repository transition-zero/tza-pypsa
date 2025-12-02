# IMPORTANT
# IF CSV OR XLSX FILES ARE SELECTED THIS CODE IS NOT OPINIONATED -- IT WILL UPLOAD YOUR FILE AS IS
# IF NC FILES ARE SELECTED THIS CODE IS OPINIONATED and will transform your data.
# IT HAS BEEN TESTED FOR SOME NC FILES BUT NOT ALL SO MAY NOT WORK FOR YOUR FILE
# the nc file for visualisation -- SEE export_pypsa_outputs_to_df function and transform_nc_for_visualisation.py
# it will create an hourly and yearly table from the nc file
# make a branch and alter these functions to suit your needs

DATA_FORMAT = "csv"  # CHANGE if your file is xlsx
DELIMITER = ","  # CHANGE if delimiter of CSV is not a comma, keep as it is for xlsx
LOCAL_FILE_PATH = None  # Will be set by batch_upload.py
RAW_OBJECT_NAME = None  # Will be set by batch_upload.py
LANDING_OBJECT_NAME = None  # Will be set by batch_upload.py
DATASET_ID = "taiwan_pypsa_outputs"  # Eg: "japan_pypsa_outputs"
BIGQUERY_TABLE_NAME = None # Will be set by batch_upload.py
BIGQUERY_WRITE_METHOD = "WRITE_APPEND"  # CHANGE to "WRITE_TRUNCATE" to overwrite
SKIP_ROWS = 1  # Set to 1 if your CSV has a header row else set to 0
CUSTOM_SCHEMA = None  # Define custom schema if needed

# NC FILES ONLY. NO NEED TO FILL IF NOT NC FILES
MARKET = "PLEASE CHANGE TO YOUR COUNTRY"  # CHANGE to "ASEAN", "JAPAN", "TAIWAN" or "INDIA"
PYPSA_RUN_ID = "PLEASE CHANGE TO YOUR RUN ID"  # CHANGE to your pypsa run id


def preprocess_dataframe(df):
    """
    Users can edit this function to perform any custom preprocessing on the DataFrame.
    Args:
        df (pd.DataFrame): The DataFrame loaded from GCS, after cleaning.
    Returns:
        pd.DataFrame: The processed DataFrame ready for upload.
    """
    return df
