import os
import sys
import logging
import time
from pathlib import Path

# Add the Upload directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

import config
from analyst_uploader import main as upload_single_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_file_stable(file_path: Path, stability_period: int = 5) -> bool:
    """
    Check if a file is stable (not being written to) by monitoring its size.
    
    Args:
        file_path (Path): Path to the file to check
        stability_period (int): Time in seconds to wait for file stability
        
    Returns:
        bool: True if file is stable, False otherwise
    """
    try:
        if not file_path.exists():
            return False
            
        initial_size = file_path.stat().st_size
        initial_mtime = file_path.stat().st_mtime
        
        # Wait for stability period
        time.sleep(stability_period)
        
        if not file_path.exists():
            return False
            
        final_size = file_path.stat().st_size
        final_mtime = file_path.stat().st_mtime
        
        # File is stable if size and modification time haven't changed
        is_stable = (initial_size == final_size) and (initial_mtime == final_mtime)
        
        if not is_stable:
            logger.info(f"File {file_path.name} is still being written to. Skipping for now.")
        
        return is_stable
        
    except (OSError, IOError) as e:
        logger.warning(f"Error checking file stability for {file_path}: {e}")
        return False

def is_file_ready_for_upload(file_path: Path, use_stability_check: bool = True) -> bool:
    """
    Check if a file is ready for upload using file stability detection.
    
    Args:
        file_path (Path): Path to the file to check
        use_stability_check (bool): Whether to check file stability
        
    Returns:
        bool: True if file is ready for upload, False otherwise
    """
    if not file_path.exists():
        return False
        
    # Check file size (skip empty files)
    if file_path.stat().st_size == 0:
        logger.warning(f"File {file_path.name} is empty. Skipping.")
        return False
    
    # Check file stability
    if use_stability_check:
        if not is_file_stable(file_path):
            return False
        logger.info(f"File {file_path.name} is stable and ready for upload")
    
    return True

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

def batch_upload_from_directory(
    directory_path: str, 
    file_pattern: str = "*.csv",
    use_stability_check: bool = True,
    max_wait_time: int = 300  # 5 minutes max wait
):
    """
    Upload all fully processed CSV files from a directory to GCS and BigQuery.
    Uses file stability detection to ensure files are completely written before upload.
    
    Args:
        directory_path (str): Path to the directory containing CSV files
        file_pattern (str): Pattern to match files (default: "*.csv")
        use_stability_check (bool): Whether to check file stability (default: True)
        max_wait_time (int): Maximum time to wait for files to become ready (seconds)
    """
    directory = Path(directory_path)
    if not directory.exists():
        raise ValueError(f"Directory {directory_path} does not exist")

    csv_files = list(directory.glob(file_pattern))
    if not csv_files:
        logger.warning(f"No {file_pattern} files found in {directory_path}")
        return

    logger.info(f"Found {len(csv_files)} files to check for readiness")
    
    # Filter files that are ready for upload
    ready_files = []
    wait_start_time = time.time()
    
    while time.time() - wait_start_time < max_wait_time:
        ready_files = []
        
        for file_path in csv_files:
            if is_file_ready_for_upload(file_path, use_stability_check):
                ready_files.append(file_path)
        
        if ready_files:
            break
            
        if time.time() - wait_start_time < max_wait_time:
            logger.info(f"Waiting for files to be ready... ({len(ready_files)}/{len(csv_files)} ready)")
            time.sleep(10)  # Wait 10 seconds before checking again
    
    if not ready_files:
        logger.warning("No files are ready for upload after waiting period")
        return
    
    logger.info(f"Found {len(ready_files)} files ready for upload")
    successful_uploads = []
    
    for file_path in ready_files:
        try:
            logger.info(f"\n--- Processing file: {file_path} ---")
            update_config_for_file(file_path)
            upload_single_file()
            logger.info(f"Successfully processed {file_path}")
            successful_uploads.append(file_path)
            
            # File processed successfully - no cleanup needed
                    
        except Exception as e:
            logger.error(f"Error processing {file_path}: {str(e)}")
            continue
    
    logger.info(f"\n=== Batch Upload Summary ===")
    logger.info(f"Total files found: {len(csv_files)}")
    logger.info(f"Files ready for upload: {len(ready_files)}")
    logger.info(f"Successfully uploaded: {len(successful_uploads)}")
    
    if len(successful_uploads) < len(ready_files):
        failed_files = [f for f in ready_files if f not in successful_uploads]
        logger.warning(f"Failed uploads: {[str(f) for f in failed_files]}")

def start_background_monitoring(directory_path: str, check_interval: int = 10, max_parallel_uploads: int = 3):
    """
    Start continuous monitoring in a background thread. 
    Use this to run uploads in parallel with your data processing.
    
    Args:
        directory_path (str): Directory to monitor
        check_interval (int): How often to check for new files (seconds)
        max_parallel_uploads (int): Max concurrent uploads
        
    Returns:
        threading.Thread: The monitoring thread (for stopping if needed)
    """
    import threading
    
    def run_monitoring():
        try:
            monitor_directory_continuously(
                directory_path=directory_path,
                check_interval=check_interval,
                max_parallel_uploads=max_parallel_uploads
            )
        except Exception as e:
            logger.error(f"Background monitoring failed: {e}")
    
    monitoring_thread = threading.Thread(target=run_monitoring, daemon=True)
    monitoring_thread.start()
    logger.info(f"Started background monitoring of {directory_path}")
    return monitoring_thread

def upload_single_csv_file(file_path: Path) -> bool:
    """
    Upload a single CSV file to GCS and BigQuery.
    
    Args:
        file_path (Path): Path to the CSV file to upload
        
    Returns:
        bool: True if upload successful, False otherwise
    """
    try:
        logger.info(f"--- Uploading file: {file_path} ---")
        update_config_for_file(str(file_path))
        upload_single_file()
        logger.info(f"Successfully uploaded {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error uploading {file_path}: {str(e)}")
        return False

def monitor_directory_continuously(
    directory_path: str,
    check_interval: int = 10,  # Shorter interval for responsiveness
    file_pattern: str = "*.csv",
    max_parallel_uploads: int = 3  # Limit concurrent uploads
):
    """
    Continuously monitor a directory for new files and upload them as soon as ready.
    Enables parallel processing: upload files while new ones are being created.
    
    Args:
        directory_path (str): Path to monitor
        check_interval (int): Time between checks in seconds (default: 10)
        file_pattern (str): Pattern to match files (default: "*.csv")
        max_parallel_uploads (int): Maximum number of files to upload concurrently
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor
    
    logger.info(f"Starting continuous monitoring of {directory_path}")
    logger.info(f"Check interval: {check_interval} seconds")
    logger.info(f"Max parallel uploads: {max_parallel_uploads}")
    
    processed_files = set()
    currently_uploading = set()
    upload_executor = ThreadPoolExecutor(max_workers=max_parallel_uploads)
    
    def handle_upload_completion(file_path: Path, future):
        """Callback when upload completes"""
        currently_uploading.discard(file_path)
        if future.result():
            processed_files.add(file_path)
            logger.info(f"Completed upload: {file_path}")
        else:
            logger.error(f"Failed upload: {file_path}")
    
    try:
        while True:
            directory = Path(directory_path)
            if directory.exists():
                current_files = set(directory.glob(file_pattern))
                # Files that are new and not currently being uploaded
                new_ready_files = current_files - processed_files - currently_uploading
                
                if new_ready_files:
                    logger.info(f"Checking {len(new_ready_files)} new files for readiness")
                    
                    # Check each new file for readiness and start upload if ready
                    for file_path in new_ready_files:
                        if is_file_ready_for_upload(file_path, use_stability_check=True):
                            logger.info(f"File ready for upload: {file_path}")
                            currently_uploading.add(file_path)
                            
                            # Submit upload to thread pool
                            future = upload_executor.submit(upload_single_csv_file, file_path)
                            future.add_done_callback(
                                lambda f, fp=file_path: handle_upload_completion(fp, f)
                            )
                            
                            logger.info(f"Started upload: {file_path} (Active uploads: {len(currently_uploading)})")
            
            # Log status periodically
            if len(currently_uploading) > 0 or len(processed_files) > 0:
                logger.info(f"Status - Processed: {len(processed_files)}, Uploading: {len(currently_uploading)}")
            
            time.sleep(check_interval)
            
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
        upload_executor.shutdown(wait=True)
    except Exception as e:
        logger.error(f"Error in continuous monitoring: {e}")
        upload_executor.shutdown(wait=True)
        raise

if __name__ == "__main__":
    # For parallel processing (upload files while new ones are being created):
    monitor_directory_continuously(
        directory_path="/home/jy/tza-pypsa/Output/hourly",
        check_interval=30,  # Check every 30 seconds for responsiveness
        file_pattern="*.csv",
        max_parallel_uploads=3  # Upload up to 3 files simultaneously
    )
    
    # For one-time batch upload (alternative approach):
    # batch_upload_from_directory("/home/jy/tza-pypsa/Output/hourly")