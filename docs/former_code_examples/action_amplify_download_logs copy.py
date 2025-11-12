'''
This Python script downloads AWS Amplify access logs over a specified date range. It:

Takes required parameters for AWS credentials, app details, and date range
Automatically splits long date ranges into 14-day chunks to handle AWS API limits
Recursively retries with smaller time chunks if AWS requests fail
Saves logs in an organized directory structure with timestamps
Provides progress updates and a final download summary

python3 /home/hylmarj/inicom/compyt/action_amplify_download_logs.py --profile AWS_PROFILE --region REGION --app-id APP_ID \
  --domain-name DOMAIN --start-date 2024-01-01 --end-date 2024-01-31 \
  [--base-path /custom/path/to/logs]

python3 /home/hylmarj/inicom/compyt/action_amplify_download_logs.py \
  --profile HylmarJ \
  --region eu-west-1 \
  --app-id d3hgg9jtwyuijn \
  --domain-name danse.tech \
  --start-date 2024-12-09 \
  --end-date 2025-03-26 \
  --base-path /home/hylmarj/_scratch/app=danse_tech/type=amplify_logs

  
python3 /home/hylmarj/inicom/compyt/action_amplify_download_logs.py \
  --profile JiHy__vsb__299 \
  --region eu-central-1 \
  --app-id dziu0wvy5r9bx \
  --domain-name main.dziu0wvy5r9bx.amplifyapp.com \
  --start-date 2024-12-09 \
  --end-date 2025-03-26 \
  --base-path /home/hylmarj/_scratch/app=digital_horizon/type=amplify_logs
'''

import subprocess
import json
from datetime import datetime, timedelta
import os
from pathlib import Path
import requests
import time
import argparse

def get_amplify_logs(profile, region, app_id, domain_name, start_time, end_time):
    """
    Run AWS Amplify CLI command to get access logs for a specific time range
    """
    command = [
        "aws", "amplify", "generate-access-logs",
        "--profile", profile,
        "--region", region,
        "--app-id", app_id,
        "--domain-name", domain_name,
        "--start-time", start_time.isoformat(timespec='seconds'),
        "--end-time", end_time.isoformat(timespec='seconds'),
        "--no-paginate"
    ]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        if result.stdout:
            response = json.loads(result.stdout)
            if 'logUrl' in response:
                print(f"Got log URL for period {start_time} - {end_time}")
                log_content = requests.get(response['logUrl'])
                if log_content.status_code == 200:
                    return log_content.text
            return response
        return None
    except subprocess.CalledProcessError as e:
        if "reduce time range" in e.stderr:
            return "REDUCE_RANGE"
        print(f"Error running command for period {start_time} - {end_time}")
        print(f"Error output: {e.stderr}")
        return None

def save_logs(logs, timestamp, base_path):
    """
    Save logs to local directory with specified path structure
    """
    date_path = base_path / f"date_export={timestamp.strftime('%Y-%m-%d')}"
    date_path.mkdir(parents=True, exist_ok=True)
    
    log_file = date_path / f"log_{timestamp.strftime('%Y%m%d_%H%M%S')}"
    with open(log_file, 'w') as f:
        if isinstance(logs, str):
            f.write(logs)
        else:
            json.dump(logs, f, indent=2)
    
    return log_file

def process_time_range(profile, region, app_id, domain_name, start_time, end_time, base_path, depth=0):
    """
    Process a time range with recursive retry using smaller chunks
    """
    if depth > 2:  # Limit recursion depth
        print(f"Max retry depth reached for {start_time} - {end_time}")
        return False
        
    hours_diff = (end_time - start_time).total_seconds() / 3600
    print(f"\nTrying range (depth {depth}): {start_time} - {end_time} ({hours_diff:.1f} hours)")
    
    logs = get_amplify_logs(profile, region, app_id, domain_name, start_time, end_time)
    
    if logs == "REDUCE_RANGE":
        print(f"Need to reduce range, splitting into smaller chunks...")
        
        # Split the range into two parts, maintaining exact timestamps
        mid_time = start_time + (end_time - start_time) // 2
        
        # Process both halves
        success1 = process_time_range(profile, region, app_id, domain_name, start_time, mid_time, base_path, depth + 1)
        time.sleep(1)  # Add delay between requests
        success2 = process_time_range(profile, region, app_id, domain_name, mid_time, end_time, base_path, depth + 1)
        
        return success1 or success2
    elif logs:
        log_file = save_logs(logs, end_time, base_path)
        print(f"Successfully saved logs to {log_file}")
        return True
    
    return False

def generate_time_ranges(start_date, end_date):
    """
    Generate initial 14-day chunks with precise timestamps
    """
    # Convert dates to datetime objects with time at midnight
    start_time = datetime.combine(start_date, datetime.min.time())
    end_time = datetime.combine(end_date, datetime.max.time())
    
    ranges = []
    current_start = start_time
    
    while current_start <= end_time:
        # Each chunk is exactly 14 days (or less for the final chunk)
        chunk_end = min(
            current_start + timedelta(days=14) - timedelta(seconds=1),
            end_time
        )
        ranges.append((current_start, chunk_end))
        current_start = chunk_end + timedelta(seconds=1)
    
    return ranges

def parse_date(date_str):
    """Parse date string in YYYY-MM-DD format"""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")

def main():
    parser = argparse.ArgumentParser(description='Download AWS Amplify logs for a specific time range')
    parser.add_argument('--profile', required=True, help='AWS profile name')
    parser.add_argument('--region', required=True, help='AWS region')
    parser.add_argument('--app-id', required=True, help='Amplify app ID')
    parser.add_argument('--domain-name', required=True, help='Domain name')
    parser.add_argument('--start-date', type=parse_date, required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=parse_date, required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--base-path', type=Path, default=Path(os.path.expanduser("~/_scratch/app=danse_tech/type=amplify_logs")),
                       help='Base path for saving logs (default: ~/scratch/app=danse_tech/type=amplify_logs)')
    
    args = parser.parse_args()
    
    time_ranges = generate_time_ranges(args.start_date, args.end_date)
    total_chunks = len(time_ranges)
    
    print(f"\nStarting download of {total_chunks} chunks")
    print(f"First chunk: {time_ranges[0][0]} - {time_ranges[0][1]}")
    print(f"Last chunk: {time_ranges[-1][0]} - {time_ranges[-1][1]}")
    print(f"Saving logs to: {args.base_path}")
    print("-" * 50)
    
    success_count = 0
    failed_ranges = []
    
    for i, (start_time, end_time) in enumerate(time_ranges, 1):
        print(f"\nProcessing chunk {i}/{total_chunks}")
        
        if process_time_range(args.profile, args.region, args.app_id, args.domain_name, start_time, end_time, args.base_path):
            success_count += 1
        else:
            failed_ranges.append((start_time, end_time))
        
        print("-" * 50)
        time.sleep(1)
    
    # Print summary
    print("\nDownload Summary:")
    print(f"Total chunks attempted: {total_chunks}")
    print(f"Successful downloads: {success_count}")
    print(f"Failed chunks: {len(failed_ranges)}")
    
    if failed_ranges:
        print("\nFailed time ranges:")
        for start, end in failed_ranges:
            print(f"- {start} to {end}")

if __name__ == "__main__":
    main()