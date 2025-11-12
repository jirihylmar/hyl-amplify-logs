import json
import logging
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda handler for calculating time ranges based on configuration
    
    Expected event format:
    {
        "config": {
            "applications": [...],
            "s3": {...},
            "timeChunkSize": {
                "days": 14
            },
            "logRetention": {
                "days": 365
            }
        }
    }
    
    Returns:
    [
        {
            "startTime": "2023-01-01T00:00:00",
            "endTime": "2023-01-15T00:00:00"
        },
        ...
    ]
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Extract configuration
        config = event.get('config', {})
        if not config:
            raise ValueError("Missing config in event")
        
        # Get time chunk size
        chunk_size_days = config.get('timeChunkSize', {}).get('days', 14)
        logger.info(f"Using chunk size of {chunk_size_days} days")
        
        # Calculate end date (now)
        end_date = datetime.now()
        
        # Calculate start date based on log retention period
        retention_days = config.get('logRetention', {}).get('days', 365)
        start_date = end_date - timedelta(days=retention_days)
        
        logger.info(f"Calculating time ranges from {start_date.isoformat()} to {end_date.isoformat()}")
        
        # Generate time chunks
        time_ranges = generate_time_ranges(start_date, end_date, chunk_size_days)
        
        logger.info(f"Generated {len(time_ranges)} time ranges")
        
        return time_ranges
        
    except Exception as e:
        logger.error(f"Error calculating time ranges: {str(e)}")
        raise

def generate_time_ranges(start_date, end_date, chunk_size_days):
    """
    Generate time range chunks between start_date and end_date
    
    Args:
        start_date: Start date
        end_date: End date
        chunk_size_days: Size of each chunk in days
        
    Returns:
        List of time range dictionaries
    """
    time_ranges = []
    
    # Calculate chunk boundaries
    current_start = start_date
    while current_start < end_date:
        # Calculate chunk end time
        chunk_end = current_start + timedelta(days=chunk_size_days)
        
        # Ensure we don't go past the end date
        if chunk_end > end_date:
            chunk_end = end_date
        
        # Add time range to list
        time_ranges.append({
            'startTime': current_start.isoformat(),
            'endTime': chunk_end.isoformat()
        })
        
        # Move to next chunk
        current_start = chunk_end
    
    return time_ranges