
===============================================================================
                      BIGQUERY LARGE DATA UPLOAD SCRIPT
===============================================================================

This tool enables users to upload files from their local machine to Google Cloud Storage (GCS),
clean and preprocess the files, and load the cleaned data into BigQuery, complete with archive links
for traceability.

-------------------------------------------------------------------------------
SETUP REQUIREMENTS
-------------------------------------------------------------------------------

- Python 3.8 or higher installed locally.
- Google Cloud SDK authenticated:
    > gcloud auth application-default login
- Required Python packages installed:
    > pip install pandas google-cloud-storage google-cloud-bigquery pypsa


Optional but useful: Using Venv to automatically change GCP projects and
manage requirements.
-------------------------------------------------------------------------------
If you already already using a gcp project as a default (eg.analysis specific one)
then you will have to switch to tz-data-dev every time you use this script using:
> gcloud auth application-default login

If you don't want to go through this process every time you can use
an included bash script to enter a venv with the correct project setup:
Run these commands instead:

    > bash setup_venv_with_gcp_project.sh tz-data-prod ~/venvs/tz-data-prod-venv
    > source ~/venvs/tz-data-prod-venv/bin/activate



-------------------------------------------------------------------------------
GCP PERMISSIONS NEEDED
-------------------------------------------------------------------------------

- GCS Access:
    roles/storage.objectAdmin
- BigQuery Access:
    roles/bigquery.dataEditor
    roles/bigquery.jobUser

Confirm permissions:
    > gsutil ls gs://your-bucket-name
    > bq ls your-dataset-name

-------------------------------------------------------------------------------
CONFIGURATION - Edit 'config.py'
-------------------------------------------------------------------------------

Mandatory fields to update:

- LOCAL_FILE_PATH: Full local file path.
- RAW_OBJECT_NAME: Name for file when uploading to GCS raw bucket.
- LANDING_OBJECT_NAME: Name for file when uploading to GCS landing bucket.
- DATA_FORMAT: "csv" or "xlsx".
- DELIMITER: Delimiter if CSV (e.g., "," or ";").
- BIGQUERY_TABLE_NAME: Destination BigQuery table name.
- BIGQUERY_WRITE_METHOD: "WRITE_APPEND" or "WRITE_TRUNCATE".
- SKIP_ROWS: 1 if file has a header, 0 otherwise.
- CUSTOM_SCHEMA: Optional manual schema for BigQuery, else leave None.

If using NC file option:
- MARKET: geographical area of model
- PYPSA_RUN_ID: pypsa run id

-------------------------------------------------------------------------------
OPTIONAL - Preprocessing Data
-------------------------------------------------------------------------------

Inside 'config.py', modify the 'preprocess_dataframe(df)' function to apply any
custom transformations to your pandas DataFrame before uploading.

If no changes are needed, the default function will return the DataFrame unchanged.

-------------------------------------------------------------------------------
RUNNING THE SCRIPT
-------------------------------------------------------------------------------

In your terminal:

    > python analyst_uploader.py

This will:
- Upload the raw file into GCS bucket "raw_analyst_uploads/YYYY-MM-DD/filename".
- Clean and optionally preprocess the data.
- Upload the cleaned file into GCS bucket "landing_analyst_uploads/YYYY-MM-DD/filename".
- Load the cleaned file into BigQuery under the dataset "analyst_uploads".
- Automatically set archive_link fields.

-------------------------------------------------------------------------------
FOLDER STRUCTURE
-------------------------------------------------------------------------------

- Raw upload:    gs://raw_analyst_uploads/YYYY-MM-DD/yourfile.csv
- Cleaned upload: gs://landing_analyst_uploads/YYYY-MM-DD/yourfile.csv

-------------------------------------------------------------------------------
TROUBLESHOOTING
-------------------------------------------------------------------------------

- Cannot upload to GCS: Check your storage permissions.
- Cannot load to BigQuery: Check BigQuery permissions.
- Authentication errors:
    - Re-run 'gcloud auth application-default login'.
    - gcloud config list project should show project = tz-data-dev
    - gcloud auth list should show your tz email address
- Wrong delimiter or data format: Update 'DELIMITER' and 'DATA_FORMAT' in config.py.

-------------------------------------------------------------------------------
NOTE ABOUT NC FILES
-------------------------------------------------------------------------------
IF CSV OR XLSX FILES ARE SELECTED THIS CODE IS NOT OPINIONATED -- IT WILL UPLOAD YOUR FILE AS IS
IF NC FILES ARE SELECTED THIS CODE IS OPINIONATED and will transform your data.
IT HAS BEEN TESTED FOR SOME NC FILES BUT NOT ALL SO MAY NOT WORK FOR YOUR FILE
the nc file for visualisation -- SEE export_pypsa_outputs_to_df function and transform_nc_for_visualisation.py
it will create an hourly and yearly table from the nc file
make a branch and alter these functions to suit your needs

-------------------------------------------------------------------------------
SUMMARY
-------------------------------------------------------------------------------

1. Edit 'config.py'.
2. Customize 'preprocess_dataframe(df)' if needed.
3. Run the script:
    > python analyst_uploader.py
4. Data flows from local --> GCS raw bucket --> cleaned GCS landing bucket --> BigQuery.

===============================================================================
