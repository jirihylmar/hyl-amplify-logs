import boto3
import json
import os
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda handler for triggering a Glue Crawler after logs have been uploaded to S3
    
    The event is expected to be the output from the Log Downloader Lambda or Step Functions
    
    Environment variables:
    - CRAWLER_NAME: Name of the Glue Crawler to trigger
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Get crawler name from environment
        crawler_name = os.environ.get('CRAWLER_NAME')
        if not crawler_name:
            logger.error("Missing CRAWLER_NAME environment variable")
            return {
                'statusCode': 500,
                'body': "Missing CRAWLER_NAME environment variable"
            }
        
        # Check if previous step was successful (if coming from Step Functions)
        status_code = event.get('statusCode')
        if status_code is not None and status_code != 200:
            logger.error(f"Previous step failed with status code {status_code}")
            return {
                'statusCode': status_code,
                'body': {
                    'message': "Skipping crawler trigger due to previous step failure",
                    'previousStatusCode': status_code,
                    'previousBody': event.get('body', {})
                }
            }
        
        # Check if any files were uploaded
        uploaded_files = []
        if 'body' in event and isinstance(event['body'], dict) and 'uploadedFiles' in event['body']:
            uploaded_files = event['body']['uploadedFiles']
        
        if not uploaded_files:
            logger.info("No files were uploaded, skipping crawler trigger")
            return {
                'statusCode': 200,
                'body': {
                    'message': "No files were uploaded, skipping crawler trigger",
                    'info': "This is normal if no logs were found for the specified time range"
                }
            }
        
        # Initialize Glue client
        region = os.environ.get('AWS_REGION', 'eu-west-1')
        glue_client = boto3.client('glue', region_name=region)
        
        # Check if the S3 path exists before triggering the crawler
        try:
            # Get bucket name from first uploaded file
            if uploaded_files:
                s3_bucket = event['body'].get('s3', {}).get('bucket')
                if not s3_bucket and 'body' in event and isinstance(event['body'], dict):
                    # Try to extract from event structure
                    s3_config = event['body'].get('s3', {})
                    if isinstance(s3_config, dict):
                        s3_bucket = s3_config.get('bucket')
                
                # If still no bucket, check for the original bucket in the configuration
                if not s3_bucket and 'config' in event and 's3' in event['config']:
                    s3_bucket = event['config']['s3'].get('bucket')
                
                # Final fallback - extract from the first file path assuming standard format
                if not s3_bucket and uploaded_files and isinstance(uploaded_files[0], str):
                    # This is a guess based on prior steps
                    s3_bucket = f"amplifylogs-logging-intite-ss2-{os.environ.get('ENVIRONMENT', 'inftes')}-{os.environ.get('ACCOUNT_NUMBER', '182059100462')}"
                    logger.warning(f"Unable to determine bucket name from event, using fallback: {s3_bucket}")
                
                if s3_bucket:
                    s3_client = boto3.client('s3', region_name=region)
                    
                    # Extract the folder path (type=amplify_logs/)
                    folder_path = "type=amplify_logs/"
                    
                    # Check if the folder exists
                    try:
                        response = s3_client.list_objects_v2(
                            Bucket=s3_bucket,
                            Prefix=folder_path,
                            MaxKeys=1
                        )
                        
                        if 'Contents' not in response or len(response['Contents']) == 0:
                            logger.warning(f"S3 path s3://{s3_bucket}/{folder_path} does not exist or is empty")
                            return {
                                'statusCode': 200,
                                'body': {
                                    'message': f"S3 path does not exist or is empty, skipping crawler",
                                    'path': f"s3://{s3_bucket}/{folder_path}"
                                }
                            }
                    except Exception as e:
                        logger.warning(f"Error checking S3 path: {str(e)}")
                        # Continue anyway, since we have uploaded files according to the event
            
        except Exception as e:
            logger.warning(f"Error checking S3 path existence: {str(e)}")
            # Continue with crawler triggering anyway
        
        # Check if crawler exists
        try:
            crawler_info = glue_client.get_crawler(
                Name=crawler_name
            )
            logger.info(f"Found crawler: {crawler_name}")
        except glue_client.exceptions.EntityNotFoundException:
            logger.error(f"Crawler not found: {crawler_name}")
            return {
                'statusCode': 404,
                'body': f"Crawler not found: {crawler_name}"
            }
        
        # Check if crawler is already running
        crawler_state = crawler_info['Crawler']['State']
        if crawler_state == 'RUNNING':
            logger.info(f"Crawler {crawler_name} is already running")
            return {
                'statusCode': 200,
                'body': {
                    'message': f"Crawler {crawler_name} is already running",
                    'crawlerState': crawler_state
                }
            }
        
        # Start the crawler
        logger.info(f"Starting crawler: {crawler_name}")
        glue_client.start_crawler(
            Name=crawler_name
        )
        
        return {
            'statusCode': 200,
            'body': {
                'message': f"Successfully triggered crawler: {crawler_name}",
                'crawlerName': crawler_name,
                'previousState': crawler_state,
                'uploadedFiles': uploaded_files
            }
        }
        
    except Exception as e:
        logger.error(f"Error triggering Glue Crawler: {str(e)}")
        return {
            'statusCode': 500,
            'body': f"Error triggering Glue Crawler: {str(e)}"
        }