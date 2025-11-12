#!/usr/bin/env python3
"""
AWS Amplify Logs Downloader

This script downloads AWS Amplify access logs for multiple applications over specified date ranges.
It handles automatic chunking of date ranges and uploading to S3.

Example usage:
    python3 amplify_logs.py --profile JiHy__vsb__299 --region eu-central-1 --app-id d3f9qt4fnd0v \
        --domain-name booking.classicskischool.cz --app-name booking_classicskischool_cz \
        --start-date 2025-02-01 --end-date 2025-03-23
"""

import argparse
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
import requests
import boto3
from typing import Dict, List, Tuple, Optional, Union, Any
import sys
import traceback

# Create logs directory if it doesn't exist
script_dir = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.join(script_dir, "logs")
os.makedirs(log_dir, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(log_dir, 'amplify_logs.log'))
    ]
)
logger = logging.getLogger(__name__)

# Fixed output directory path
FIXED_OUTPUT_DIR = Path('/home/hylmarj/_scratch')
# Fixed S3 sync profile - ALWAYS use HylmarJ
S3_PROFILE = "HylmarJ"
# Hardcoded S3 bucket
S3_BUCKET = "amplifylogs-logging-intite-ss1-inftes-182059100462"
# S3 prefix (empty string)
S3_PREFIX = ""


class AmplifyLogDownloader:
    """
    Class for downloading AWS Amplify logs and uploading to S3
    """
    
    def __init__(self, app_config: Dict, chunk_size_days: int = 14):
        """
        Initialize the log downloader
        
        Args:
            app_config: Application configuration
            chunk_size_days: Size of time chunks in days (default: 14)
        """
        self.app = app_config
        self.chunk_size_days = chunk_size_days
        self.stats = {
            'total_chunks': 0,
            'successful_chunks': 0,
            'failed_chunks': 0,
            'empty_logs_chunks': 0,
            'upload_failures': 0,
            'failed_ranges': []
        }
        
        logger.info(f"Initialized downloader for {self.app['appName']}")
        logger.info(f"S3 uploads enabled to bucket: {S3_BUCKET}")
    
    def get_amplify_logs(self, start_time: datetime, end_time: datetime) -> Union[str, Dict, None]:
        """
        Run AWS Amplify CLI command to get access logs for a specific time range
        
        Args:
            start_time: Start time for log retrieval
            end_time: End time for log retrieval
            
        Returns:
            Log content as string, response dictionary, "REDUCE_RANGE" signal, or None on failure
        """
        command = [
            "aws", "amplify", "generate-access-logs",
            "--profile", self.app['profile'],
            "--region", self.app['region'],
            "--app-id", self.app['appId'],
            "--domain-name", self.app['domainName'],
            "--start-time", start_time.isoformat(timespec='seconds'),
            "--end-time", end_time.isoformat(timespec='seconds'),
            "--no-paginate"
        ]
        
        try:
            logger.info(f"Fetching logs for {self.app['appName']} from {start_time} to {end_time}")
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            
            if result.stdout:
                response = json.loads(result.stdout)
                if 'logUrl' in response:
                    logger.info(f"Got log URL for {self.app['appName']} ({start_time} - {end_time})")
                    log_url = response['logUrl']
                    
                    log_content = requests.get(log_url)
                    if log_content.status_code == 200:
                        content_size = len(log_content.text)
                        logger.info(f"Got log content ({content_size} bytes)")
                        
                        # Return content even if it's empty (0 bytes)
                        # Empty logs are still successful downloads, just with no data
                        return log_content.text
                    else:
                        logger.error(f"Failed to download logs from URL: HTTP {log_content.status_code}")
                        return None
                return response
            
            logger.warning(f"Empty response when fetching logs for {self.app['appName']}")
            return None
        
        except subprocess.CalledProcessError as e:
            if "reduce time range" in e.stderr:
                logger.warning(f"AWS API requested to reduce time range for {self.app['appName']}")
                return "REDUCE_RANGE"
            logger.error(f"Error running command for {self.app['appName']} ({start_time} - {end_time}): {e.stderr}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error for {self.app['appName']}: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    def save_logs_locally(self, logs: Union[str, Dict], timestamp: datetime) -> Optional[Path]:
        """
        Save logs to local directory with the fixed path structure.
        Skip creating files if logs are empty.
        
        Args:
            logs: Log content (string or dictionary)
            timestamp: Timestamp for the logs
            
        Returns:
            Path to the saved log file or None if logs are empty and we skip creation
        """
        try:
            # Check if logs are empty
            is_empty = logs == "" if isinstance(logs, str) else False
            
            # If logs are empty, don't create any files
            if is_empty:
                logger.info(f"Logs are empty for {self.app['appName']} ({timestamp}), skipping file creation")
                return None
            
            # Only create directories and files if we have actual content
            base_path = FIXED_OUTPUT_DIR / f"type=amplify_logs" / f"app={self.app['appName']}"
            date_path = base_path / f"date_export={timestamp.strftime('%Y-%m-%d')}"
            date_path.mkdir(parents=True, exist_ok=True)
            
            log_file = date_path / f"log_{timestamp.strftime('%Y%m%d_%H%M%S')}"
            
            # Save the logs to file
            with open(log_file, 'w') as f:
                if isinstance(logs, str):
                    f.write(logs)
                else:
                    json.dump(logs, f, indent=2)
            
            logger.info(f"Saved logs ({os.path.getsize(log_file)} bytes) to {log_file}")
            return log_file
        except Exception as e:
            logger.error(f"Failed to save logs locally: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def upload_to_s3(self, local_file: Path, timestamp: datetime, delete_after_upload: bool = False) -> bool:
        """
        Upload logs to S3 bucket with AWS CLI to ensure correct profile is used
        
        Args:
            local_file: Path to local log file
            timestamp: Timestamp for the logs
            delete_after_upload: Whether to delete the local file after successful upload
            
        Returns:
            True if upload successful, False otherwise
        """
        # Construct S3 key
        s3_key = os.path.join(
            S3_PREFIX,
            "type=amplify_logs",
            f"app={self.app['appName']}",
            f"date_export={timestamp.strftime('%Y-%m-%d')}",
            f"log_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        )
        
        # Create S3 URI
        s3_uri = f"s3://{S3_BUCKET}/{s3_key}"
        
        # Use AWS CLI with explicit profile
        command = [
            "aws", "s3", "cp",
            str(local_file), s3_uri,
            "--profile", S3_PROFILE
        ]
        
        try:
            logger.info(f"Uploading {local_file} to {s3_uri} using profile {S3_PROFILE}")
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            
            logger.info(f"S3 upload command result: {result.stdout}")
            
            # Delete local file if requested
            if delete_after_upload:
                try:
                    os.remove(local_file)
                    logger.info(f"Deleted local file {local_file} after successful upload")
                except Exception as e:
                    logger.warning(f"Failed to delete local file {local_file}: {str(e)}")
            
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to upload to S3: {e.stderr}")
            self.stats['upload_failures'] += 1
            return False
        except Exception as e:
            logger.error(f"Unexpected error during S3 upload: {str(e)}")
            logger.error(traceback.format_exc())
            self.stats['upload_failures'] += 1
            return False
    
    def process_time_range(self, start_time: datetime, end_time: datetime, 
                          depth: int = 0, delete_after_upload: bool = False) -> Tuple[bool, bool]:
        """
        Process a time range with recursive retry using smaller chunks
        
        Args:
            start_time: Start time for log retrieval
            end_time: End time for log retrieval
            depth: Current recursion depth
            delete_after_upload: Whether to delete local files after successful S3 upload
            
        Returns:
            Tuple of (success, is_empty_logs)
        """
        if depth > 2:  # Limit recursion depth
            logger.warning(f"Max retry depth reached for {self.app['appName']} ({start_time} - {end_time})")
            return False, False
        
        hours_diff = (end_time - start_time).total_seconds() / 3600
        logger.info(f"Processing range (depth {depth}): {start_time} - {end_time} ({hours_diff:.1f} hours)")
        
        try:
            logs = self.get_amplify_logs(start_time, end_time)
            
            if logs == "REDUCE_RANGE":
                logger.info(f"Splitting time range into smaller chunks for {self.app['appName']}")
                
                # Split the range into two parts
                mid_time = start_time + (end_time - start_time) // 2
                
                # Process both halves
                success1, empty1 = self.process_time_range(start_time, mid_time, depth + 1, delete_after_upload)
                time.sleep(1)  # Add delay between requests
                success2, empty2 = self.process_time_range(mid_time, end_time, depth + 1, delete_after_upload)
                
                return (success1 or success2), (empty1 and empty2)
            
            elif logs is not None:  # logs can be an empty string, which is valid
                is_empty = logs == "" if isinstance(logs, str) else False
                
                if is_empty:
                    logger.info(f"Retrieved empty logs for {self.app['appName']} ({start_time} - {end_time})")
                    # Consider empty logs as success, but don't create files
                    return True, True
                else:
                    logger.info(f"Retrieved logs for {self.app['appName']} ({start_time} - {end_time}): {len(logs if isinstance(logs, str) else str(logs))} bytes")
                
                    # Save logs locally
                    local_file = self.save_logs_locally(logs, end_time)
                    
                    # Only attempt S3 upload if we have a file 
                    s3_success = True
                    if local_file:
                        s3_success = self.upload_to_s3(local_file, end_time, delete_after_upload)
                        logger.info(f"S3 upload success: {s3_success}")
                    
                    return s3_success, False
            else:
                logger.warning(f"No logs returned for {self.app['appName']} ({start_time} - {end_time})")
                return False, False
        except Exception as e:
            logger.error(f"Error in process_time_range: {str(e)}")
            logger.error(traceback.format_exc())
            return False, False
    
    def generate_time_ranges(self, start_date: datetime.date, end_date: datetime.date) -> List[Tuple[datetime, datetime]]:
        """
        Generate time ranges based on the configured chunk size
        
        Args:
            start_date: Start date for log retrieval
            end_date: End date for log retrieval
            
        Returns:
            List of (start_time, end_time) tuples
        """
        # Convert dates to datetime objects with time at midnight
        start_time = datetime.combine(start_date, datetime.min.time())
        # Use time with no microseconds for consistent testing
        end_time = datetime.combine(end_date, datetime.max.time().replace(microsecond=0))
        
        ranges = []
        current_start = start_time
        
        while current_start <= end_time:
            # Each chunk is exactly {chunk_size_days} days (or less for the final chunk)
            chunk_end = min(
                current_start + timedelta(days=self.chunk_size_days) - timedelta(seconds=1),
                end_time
            )
            ranges.append((current_start, chunk_end))
            current_start = chunk_end + timedelta(seconds=1)
        
        return ranges
    
    def download_logs(self, start_date: datetime.date, end_date: datetime.date, 
                     delete_after_upload: bool = False) -> Dict[str, Any]:
        """
        Process the application for the given date range
        
        Args:
            start_date: Start date for log retrieval
            end_date: End date for log retrieval
            delete_after_upload: Whether to delete local files after successful S3 upload
            
        Returns:
            Dictionary with statistics
        """
        app_stats = {
            'app_name': self.app['appName'],
            'total_chunks': 0,
            'successful_chunks': 0,
            'empty_logs_chunks': 0,
            'failed_chunks': 0,
            'failed_ranges': []
        }
        
        time_ranges = self.generate_time_ranges(start_date, end_date)
        app_stats['total_chunks'] = len(time_ranges)
        self.stats['total_chunks'] = app_stats['total_chunks']
        
        logger.info(f"Processing {self.app['appName']}: {len(time_ranges)} chunks from {start_date} to {end_date}")
        
        for i, (start_time, end_time) in enumerate(time_ranges, 1):
            logger.info(f"Processing chunk {i}/{len(time_ranges)} for {self.app['appName']}")
            
            success, is_empty = self.process_time_range(start_time, end_time, delete_after_upload=delete_after_upload)
            
            if success:
                app_stats['successful_chunks'] += 1
                self.stats['successful_chunks'] += 1
                
                if is_empty:
                    app_stats['empty_logs_chunks'] += 1
                    self.stats['empty_logs_chunks'] += 1
            else:
                app_stats['failed_chunks'] += 1
                self.stats['failed_chunks'] += 1
                app_stats['failed_ranges'].append((start_time, end_time))
                self.stats['failed_ranges'].append({
                    'app_name': self.app['appName'],
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat()
                })
            
            # Add delay between chunks
            time.sleep(1)
        
        logger.info(f"Completed processing application: {self.app['appName']}")
        return {
            'overall_stats': self.stats,
            'app_stats': app_stats
        }


def parse_date(date_str: str) -> datetime.date:
    """Parse date string in YYYY-MM-DD format"""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")


def main():
    parser = argparse.ArgumentParser(description='Download AWS Amplify logs for a specific time range')
    
    # Date range options
    date_group = parser.add_argument_group('Date Range')
    date_group.add_argument('--start-date', type=parse_date, required=True, help='Start date (YYYY-MM-DD)')
    date_group.add_argument('--end-date', type=parse_date, required=True, help='End date (YYYY-MM-DD)')
    
    # Output options
    output_group = parser.add_argument_group('Output')
    output_group.add_argument('--output-dir', type=Path, help='Base path for saving logs (ignored, using fixed path)')
    output_group.add_argument('--delete-after-upload', action='store_true',
                             help='Delete local log files after successful S3 upload')
    
    # Application parameters (required)
    app_group = parser.add_argument_group('Application Parameters')
    app_group.add_argument('--profile', type=str, required=True, help='AWS profile name for Amplify API')
    app_group.add_argument('--region', type=str, required=True, help='AWS region')
    app_group.add_argument('--app-id', type=str, required=True, help='Amplify app ID')
    app_group.add_argument('--domain-name', type=str, required=True, help='Domain name')
    app_group.add_argument('--app-name', type=str, required=True, help='Application name')
    
    # S3 options
    s3_group = parser.add_argument_group('S3 Settings')
    s3_group.add_argument('--s3-bucket', type=str, help='S3 bucket for logs (ignored, using hardcoded bucket)')
    s3_group.add_argument('--s3-prefix', type=str, help='S3 prefix for logs (ignored, using hardcoded prefix)')
    
    # Advanced options
    adv_group = parser.add_argument_group('Advanced')
    adv_group.add_argument('--chunk-size-days', type=int, default=14, help='Size of time chunks in days')
    
    args = parser.parse_args()
    
    # Ensure fixed output directory exists
    FIXED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Using fixed output directory: {FIXED_OUTPUT_DIR}")
    logger.info(f"Using hardcoded S3 bucket: {S3_BUCKET}")
    
    # Create application configuration
    app_config = {
        'profile': args.profile,
        'region': args.region,
        'appId': args.app_id,
        'domainName': args.domain_name,
        'appName': args.app_name
    }
    
    try:
        # Check AWS CLI executable
        aws_path = subprocess.run(["which", "aws"], capture_output=True, text=True).stdout.strip()
        if not aws_path:
            logger.warning("AWS CLI not found in PATH. Please ensure it's installed and in your PATH.")
        
        # Check S3 profile
        s3_profile_check = subprocess.run(["aws", "configure", "list", "--profile", S3_PROFILE], 
                                        capture_output=True, text=True)
        if s3_profile_check.returncode != 0:
            logger.warning(f"AWS S3 profile '{S3_PROFILE}' may not be properly configured.")
        
        # Initialize the downloader with the configuration
        downloader = AmplifyLogDownloader(
            app_config, 
            chunk_size_days=args.chunk_size_days
        )
        
        # Process the application
        results = downloader.download_logs(
            args.start_date, args.end_date, args.delete_after_upload
        )
        
        # Save results to file
        results_file = FIXED_OUTPUT_DIR / "amplify_logs_results.json"
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        # Print summary
        print("\nDownload Summary:")
        print(f"Application: {results['app_stats']['app_name']}")
        print(f"Total chunks attempted: {results['overall_stats']['total_chunks']}")
        print(f"Successful downloads: {results['overall_stats']['successful_chunks']} (including {results['overall_stats']['empty_logs_chunks']} with empty logs)")
        print(f"Failed chunks: {results['overall_stats']['failed_chunks']}")
        print(f"Upload failures: {results['overall_stats']['upload_failures']}")
        print(f"Delete after upload: {'Enabled' if args.delete_after_upload else 'Disabled'}")
        
        if results['overall_stats']['failed_ranges']:
            print("\nFailed time ranges:")
            for failed_range in results['overall_stats']['failed_ranges']:
                print(f"- {failed_range['app_name']}: {failed_range['start_time']} to {failed_range['end_time']}")
        
        print(f"\nDetailed results saved to {results_file}")
        print(f"\nLogs saved to: {FIXED_OUTPUT_DIR}/type=amplify_logs/app={args.app_name}/")
        
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        logger.error(traceback.format_exc())
        print(f"Error: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())