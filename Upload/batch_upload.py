import os
import sys
import logging
from pathlib import Path

# Add the Upload directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

import config
from analyst_uploader import main as upload_single_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_config_for_file(file_path: str):
    """Update config variables for each file."""
    file_name = os.path.basename(file_path)
    name_without_ext = os.path.splitext(file_name)[0]
    
    config.DATA_FORMAT = "csv"
    config.LOCAL_FILE_PATH = str(file_path)
    config.RAW_OBJECT_NAME = name_without_ext
    config.LANDING_OBJECT_NAME = name_without_ext
    config.BIGQUERY_TABLE_NAME = name_without_ext  # Keep original case
    
    logger.info(f"Updating config for file: {file_name}")
    logger.info(f"LOCAL_FILE_PATH: {config.LOCAL_FILE_PATH}")
    logger.info(f"RAW_OBJECT_NAME: {config.RAW_OBJECT_NAME}")
    logger.info(f"LANDING_OBJECT_NAME: {config.LANDING_OBJECT_NAME}")
    logger.info(f"BIGQUERY_TABLE_NAME: {config.BIGQUERY_TABLE_NAME}")

def batch_upload_from_directory(directory_path: str, file_pattern: str = "*.csv"):
    """
    Upload all CSV files from a directory to GCS and BigQuery.
    
    Args:
        directory_path (str): Path to the directory containing CSV files
        file_pattern (str): Pattern to match files (default: "*.csv")
    """
    directory = Path(directory_path)
    if not directory.exists():
        raise ValueError(f"Directory {directory_path} does not exist")

    csv_files = list(directory.glob(file_pattern))
    if not csv_files:
        logger.warning(f"No {file_pattern} files found in {directory_path}")
        return

    logger.info(f"Found {len(csv_files)} files to process")
    
    for file_path in csv_files:
        try:
            logger.info(f"\n--- Processing file: {file_path} ---")
            update_config_for_file(file_path)
            upload_single_file()
            logger.info(f"Successfully processed {file_path}\n")
        except Exception as e:
            logger.error(f"Error processing {file_path}: {str(e)}")
            continue

if __name__ == "__main__":
    # Example usage
    output_directory = "/home/jy/tza-pypsa/Output/hourly"  # Change this to your Output folder path
    batch_upload_from_directory(output_directory) 