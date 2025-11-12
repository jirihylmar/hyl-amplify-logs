import boto3
import json
import os
import logging
import tempfile
import shutil
import requests
import time
from botocore.exceptions import ClientError
from pathlib import Path
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda handler for downloading AWS Amplify logs and uploading to S3
    
    Expected event format:
    {
        "app": {
            "region": "eu-west-1",
            "appId": "d3hgg9jtwyuijn",
            "domainName": "danse.tech",
            "appName": "danse_tech"
        },
        "timeRange": {
            "startTime": "2023-10-01T00:00:00",
            "endTime": "2023-10-14T23:59:59"
        },
        "s3": {
            "bucket": "amplifylogs-logging-intite-ss2-inftes-182059100462",
            "prefix": ""
        }
    }
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Extract parameters
        app = event.get('app', {})
        time_range = event.get('timeRange', {})
        s3_config = event.get('s3', {})
        
        # Validate required parameters
        validate_parameters(app, time_range, s3_config)
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary directory: {temp_dir}")
        
        try:
            # Parse dates
            start_time = datetime.fromisoformat(time_range['startTime'].replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(time_range['endTime'].replace('Z', '+00:00'))
            
            # Ensure S3 bucket exists
            s3_client = boto3.client('s3', region_name=app['region'])
            try:
                s3_client.head_bucket(Bucket=s3_config['bucket'])
                logger.info(f"S3 bucket {s3_config['bucket']} exists")
            except Exception as e:
                logger.error(f"S3 bucket {s3_config['bucket']} does not exist or is not accessible: {str(e)}")
                return {
                    'statusCode': 500,
                    'body': f"S3 bucket {s3_config['bucket']} does not exist or is not accessible"
                }
            
            # Download logs using the Amplify API
            log_file_paths = download_amplify_logs(app, start_time, end_time, temp_dir)
            
            if not log_file_paths:
                logger.info(f"No logs found for {app['appName']} from {start_time} to {end_time}")
                return {
                    'statusCode': 200,
                    'body': {
                        'app': app['appName'],
                        'timeRange': time_range,
                        'message': 'No logs found for the specified time range',
                        'uploadedFiles': []
                    }
                }
            
            # Upload logs to S3
            uploaded_files = upload_logs_to_s3(s3_client, log_file_paths, temp_dir, s3_config)
            
            return {
                'statusCode': 200,
                'body': {
                    'app': app['appName'],
                    'timeRange': time_range,
                    'uploadedFiles': uploaded_files
                }
            }
            
        finally:
            # Clean up temporary directory
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")
            
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': f"Error: {str(e)}"
        }

def validate_parameters(app, time_range, s3_config):
    """Validate required parameters in the Lambda event"""
    if not app:
        raise ValueError("Missing 'app' configuration in event")
    
    required_app_keys = ['region', 'appId', 'domainName', 'appName']
    for key in required_app_keys:
        if key not in app:
            raise ValueError(f"Missing required app parameter: {key}")
    
    if not time_range:
        raise ValueError("Missing 'timeRange' configuration in event")
    
    required_time_keys = ['startTime', 'endTime']
    for key in required_time_keys:
        if key not in time_range:
            raise ValueError(f"Missing required time range parameter: {key}")
    
    if not s3_config:
        raise ValueError("Missing 's3' configuration in event")
    
    if 'bucket' not in s3_config:
        raise ValueError("Missing required S3 parameter: bucket")

def download_amplify_logs(app, start_time, end_time, temp_dir, max_retries=3, retry_delay=2):
    """
    Download logs from Amplify using the AWS SDK
    
    Args:
        app: Application configuration
        start_time: Start time for log retrieval
        end_time: End time for log retrieval
        temp_dir: Temporary directory for storing logs
        max_retries: Maximum number of retries for API calls
        retry_delay: Initial delay between retries (increases exponentially)
            
    Returns:
        List of log file paths
    """
    try:
        # Format date for output paths
        date_str = start_time.strftime('%Y-%m-%d')
        output_dir = os.path.join(
            temp_dir,
            f"type=amplify_logs/app={app['appName']}/date_export={date_str}"
        )
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize Amplify client
        amplify_client = boto3.client('amplify', region_name=app['region'])
        
        # Format dates for API
        start_date_param = start_time.isoformat(timespec='seconds')
        end_date_param = end_time.isoformat(timespec='seconds')
        
        # Construct log file path
        log_file_path = os.path.join(output_dir, f"log_{start_time.strftime('%Y%m%d_%H%M%S')}")
        
        # Call Amplify API to generate access logs
        logger.info(f"Generating access logs for {app['appName']} from {start_time} to {end_time}")
        
        for retry in range(max_retries):
            try:
                response = amplify_client.generate_access_logs(
                    appId=app['appId'],
                    domainName=app['domainName'],
                    startTime=start_date_param,
                    endTime=end_date_param
                )
                
                # Check if logUrl exists in the response
                if 'logUrl' in response:
                    logger.info(f"Successfully got log URL: {response['logUrl']}")
                    
                    # Download the log file from the URL
                    log_response = requests.get(response['logUrl'])
                    if log_response.status_code == 200:
                        # Write the log content to file
                        with open(log_file_path, 'w') as f:
                            f.write(log_response.text)
                        
                        logger.info(f"Successfully downloaded logs to {log_file_path}")
                        return [log_file_path]
                    else:
                        logger.error(f"Failed to download logs from URL: HTTP {log_response.status_code}")
                        if retry < max_retries - 1:
                            delay = retry_delay * (2 ** retry)
                            logger.info(f"Retrying in {delay} seconds... (Attempt {retry + 1}/{max_retries})")
                            time.sleep(delay)
                            continue
                        return []
                else:
                    logger.warning(f"No logUrl found in response: {response}")
                    
                    # Create an empty log file to indicate we processed this time range
                    with open(log_file_path, 'w') as f:
                        f.write(f"# No logs found for {app['appName']} from {start_time} to {end_time}\n")
                    
                    return [log_file_path]
                    
            except amplify_client.exceptions.BadRequestException as e:
                # Check if the error is due to too many records
                if "reduce time range" in str(e) or "Too many records" in str(e):
                    logger.warning(f"Too many records requested. Subdividing time range.")
                    return handle_large_time_range(app, start_time, end_time, temp_dir)
                else:
                    logger.error(f"Bad request error: {str(e)}")
                    if retry < max_retries - 1:
                        delay = retry_delay * (2 ** retry)
                        logger.info(f"Retrying in {delay} seconds... (Attempt {retry + 1}/{max_retries})")
                        time.sleep(delay)
                    else:
                        return []
                        
            except amplify_client.exceptions.ResourceNotFoundException as e:
                logger.error(f"Resource not found: {str(e)}")
                return []
                
            except Exception as e:
                logger.error(f"Error calling Amplify API: {str(e)}")
                if retry < max_retries - 1:
                    delay = retry_delay * (2 ** retry)
                    logger.info(f"Retrying in {delay} seconds... (Attempt {retry + 1}/{max_retries})")
                    time.sleep(delay)
                else:
                    return []
                    
        # If we get here, all retries failed
        logger.error(f"Failed to get logs after {max_retries} attempts")
        return []
        
    except Exception as e:
        logger.error(f"Unexpected error downloading logs: {str(e)}")
        return []

def handle_large_time_range(app, start_time, end_time, temp_dir, depth=0, max_depth=3):
    """
    Handle large time ranges by subdividing them
    
    Args:
        app: Application configuration
        start_time: Start time
        end_time: End time
        temp_dir: Temporary directory
        depth: Current recursion depth
        max_depth: Maximum recursion depth
            
    Returns:
        List of log file paths
    """
    if depth >= max_depth:
        logger.error(f"Maximum recursion depth ({max_depth}) reached for time range subdivision")
        return []
    
    # Calculate midpoint for subdivision
    time_diff = end_time - start_time
    mid_time = start_time + time_diff / 2
    logger.info(f"Subdividing time range at depth {depth}:")
    logger.info(f"  First half: {start_time} to {mid_time}")
    logger.info(f"  Second half: {mid_time} to {end_time}")
    
    all_paths = []
    
    # Process first half
    first_half = download_amplify_logs(app, start_time, mid_time, temp_dir)
    all_paths.extend(first_half)
    
    # Add delay between requests to avoid API rate limiting
    time.sleep(1)
    
    # Process second half
    second_half = download_amplify_logs(app, mid_time, end_time, temp_dir)
    all_paths.extend(second_half)
    
    return all_paths

def upload_logs_to_s3(s3_client, log_file_paths, temp_dir, s3_config, max_retries=3, retry_delay=2):
    """
    Upload downloaded log files to S3
    
    Args:
        s3_client: S3 client
        log_file_paths: List of log file paths
        temp_dir: Temporary directory
        s3_config: S3 configuration
        max_retries: Maximum number of retries for S3 operations
        retry_delay: Initial delay between retries (increases exponentially)
        
    Returns:
        List of S3 keys for uploaded files
    """
    uploaded_files = []
    
    try:
        for local_file_path in log_file_paths:
            # Skip files that don't exist (could happen if there was an error during download)
            if not os.path.exists(local_file_path):
                logger.warning(f"Skipping non-existent file: {local_file_path}")
                continue
                
            # Skip empty files
            if os.path.getsize(local_file_path) == 0:
                logger.warning(f"Skipping empty file: {local_file_path}")
                continue
            
            # Calculate S3 key (path within the bucket)
            relative_path = os.path.relpath(local_file_path, temp_dir)
            s3_key = os.path.join(s3_config.get('prefix', ''), relative_path)
            
            # Remove any leading slashes in the key
            s3_key = s3_key.lstrip('/')
            
            # Set content type based on file extension
            content_type = 'text/plain'
            if local_file_path.endswith('.json'):
                content_type = 'application/json'
            elif local_file_path.endswith('.csv'):
                content_type = 'text/csv'
            
            # Upload file to S3 with retry logic
            for retry in range(max_retries):
                try:
                    logger.info(f"Uploading {local_file_path} to s3://{s3_config['bucket']}/{s3_key}")
                    s3_client.upload_file(
                        local_file_path,
                        s3_config['bucket'],
                        s3_key,
                        ExtraArgs={
                            'ContentType': content_type,
                            'ServerSideEncryption': 'AES256'
                        }
                    )
                    
                    uploaded_files.append(s3_key)
                    logger.info(f"Successfully uploaded s3://{s3_config['bucket']}/{s3_key}")
                    break
                    
                except ClientError as e:
                    logger.error(f"S3 client error: {str(e)}")
                    if retry < max_retries - 1:
                        delay = retry_delay * (2 ** retry)
                        logger.info(f"Retrying in {delay} seconds... (Attempt {retry + 1}/{max_retries})")
                        time.sleep(delay)
                    else:
                        logger.error(f"Failed to upload {local_file_path} after {max_retries} attempts")
                        
                except Exception as e:
                    logger.error(f"Unexpected error uploading to S3: {str(e)}")
                    if retry < max_retries - 1:
                        delay = retry_delay * (2 ** retry)
                        logger.info(f"Retrying in {delay} seconds... (Attempt {retry + 1}/{max_retries})")
                        time.sleep(delay)
                    else:
                        logger.error(f"Failed to upload {local_file_path} after {max_retries} attempts")
        
        return uploaded_files
        
    except Exception as e:
        logger.error(f"Error in upload_logs_to_s3: {str(e)}")
        return uploaded_files
