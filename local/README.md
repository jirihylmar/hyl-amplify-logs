# AWS Amplify Logs Downloader

A streamlined tool for downloading AWS Amplify access logs and storing them both locally and in S3.

Basic command

```bash
aws amplify generate-access-logs --start-time 2023-10-24 --end-time 2023-11-06 --domain-name danse.tech --app-id d3hgg9jtwyuijn --no-paginate
```

## Features

- **Simple to Use**: Single command-line interface for downloading Amplify logs
- **Automatic Chunking**: Handles large date ranges by breaking them into manageable chunks
- **Smart Retry**: Automatically reduces time range when AWS API asks for smaller chunks
- **S3 Integration**: Uploads logs to a pre-configured S3 bucket using a dedicated AWS profile
- **Skip Empty Files**: Avoids creating empty files when no logs are found
- **Detailed Logging**: Comprehensive logging for troubleshooting and auditing

## Setup

1. Ensure you have Python 3.6+ installed
2. Install required Python dependencies:
   ```bash
   pip install boto3 requests
   ```
3. Make sure AWS CLI is configured with appropriate profiles:
   ```bash
   aws configure --profile JiHy__vsb__299  # For API access
   aws configure --profile HylmarJ         # For S3 uploads
   ```
4. Place the script in your desired location (e.g., `/home/hylmarj/hyl-amplify-logs/local/amplify_logs.py`)

## Usage

```bash
python3 amplify_logs.py \
  --profile YOUR_API_PROFILE \
  --region AWS_REGION \
  --app-id AMPLIFY_APP_ID \
  --domain-name DOMAIN_NAME \
  --app-name APP_NAME \
  --start-date YYYY-MM-DD \
  --end-date YYYY-MM-DD
```

### Example

```bash
python3 /home/hylmarj/hyl-amplify-logs/local/action_amplify_download_logs.py \
  --profile HylmarJ \
  --region eu-west-1 \
  --app-id d3hgg9jtwyuijn \
  --domain-name danse.tech \
  --app-name danse_tech \
  --start-date 2024-12-09 \
  --end-date 2025-02-28 \
  --s3-bucket amplifylogs-logging-intite-ss1-inftes-182059100462

python3 /home/hylmarj/hyl-amplify-logs/local/amplify_logs.py \
  --profile JiHy__vsb__299 \
  --region eu-central-1 \
  --app-id d3f9qt4fnd0v \
  --domain-name booking.classicskischool.cz \
  --app-name booking_classicskischool_cz\
  --start-date 2025-02-01 \
  --end-date 2025-03-23 \
  --output-dir /home/hylmarj/hyl-amplify-logs/local/logs

python3 /home/hylmarj/hyl-amplify-logs/local/amplify_logs.py \
  --profile JiHy__vsb__299 \
  --region eu-central-1 \
  --app-id d267f060c4kfsk \
  --domain-name reviews.classicskischool.cz \
  --app-name reviews_classicskischool_cz\
  --start-date 2025-02-01 \
  --end-date 2025-03-23 \
  --output-dir /home/hylmarj/hyl-amplify-logs/local/logs

python3 /home/hylmarj/hyl-amplify-logs/local/amplify_logs.py \
  --profile JiHy__vsb__299 \
  --region eu-central-1 \
  --app-id dziu0wvy5r9bx \
  --domain-name digital-horizon.cz \
  --app-name digital_horizon_cz\
  --start-date 2024-12-01 \
  --end-date 2025-03-23 \
  --output-dir /home/hylmarj/hyl-amplify-logs/local/logs
```

### Command-line Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `--profile` | AWS profile for Amplify API | Yes |
| `--region` | AWS region | Yes |
| `--app-id` | Amplify app ID | Yes |
| `--domain-name` | Domain name | Yes |
| `--app-name` | Application name | Yes |
| `--start-date` | Start date (YYYY-MM-DD) | Yes |
| `--end-date` | End date (YYYY-MM-DD) | Yes |
| `--delete-after-upload` | Delete local files after S3 upload | No |
| `--chunk-size-days` | Size of time chunks in days (default: 14) | No |
| `--output-dir` | Ignored (using fixed output path) | No |
| `--s3-bucket` | Ignored (using hardcoded bucket) | No |
| `--s3-prefix` | Ignored (using hardcoded prefix) | No |

## Output Structure

### Local Storage

Logs are saved to a fixed local path with the following structure:

```
/home/hylmarj/_scratch/
└── type=amplify_logs/
    └── app=APP_NAME/
        └── date_export=YYYY-MM-DD/
            └── log_YYYYMMDD_HHMMSS
```

### S3 Storage

Logs are also uploaded to the hardcoded S3 bucket with the same structure:

```
s3://amplifylogs-logging-intite-ss1-inftes-182059100462/
└── type=amplify_logs/
    └── app=APP_NAME/
        └── date_export=YYYY-MM-DD/
            └── log_YYYYMMDD_HHMMSS
```

## Configuration Details

The script includes the following hardcoded configurations:

- **S3 Bucket**: `amplifylogs-logging-intite-ss1-inftes-182059100462`
- **S3 Profile**: `HylmarJ` (used for S3 uploads regardless of the API profile)
- **Local Output Directory**: `/home/hylmarj/_scratch/`

## Notes

- Empty logs are not saved to disk or uploaded to S3
- The script automatically handles AWS API rate limiting by splitting time ranges
- S3 uploads always use the `HylmarJ` profile regardless of which profile is specified for the API calls
- Maximum recursion depth is 2 for handling time range reductions