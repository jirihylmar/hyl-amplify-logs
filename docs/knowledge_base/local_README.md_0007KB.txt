=== File: local/README.md ===
=== Size: 7KB ===

# AWS Amplify Logs Downloader

This project automates the downloading and storage of AWS Amplify logs data. It provides local scripts for development/testing and will be extended to a full AWS serverless architecture.

## Local Development

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd hyl-amplify-logs
```

2. Ensure AWS CLI is configured with appropriate profiles:
```bash
aws configure --profile HylmarJ
# Configure additional profiles as needed
```

3. Set up the directory structure:
```bash
# Create necessary directories
mkdir -p local/logs
```

4. Create a configuration file (`config.json`) based on the sample provided.

### Usage

#### Direct script execution:

```bash
# Run the script directly with a configuration file
python3 /home/hylmarj/hyl-amplify-logs/local/action_amplify_download_logs.py \
  --config-path /home/hylmarj/hyl-amplify-logs/local/config.json \
  --start-date 2023-10-01 \
  --end-date 2023-10-02
```

The local directory structure will be:

```
/home/hylmarj/_scratch/
├── type=amplify_logs/
│   ├── app=danse_tech/
│   │   └── date_export=2023-10-01/
│   │       └── log_20231001_235959
│   └── app=digital_horizon/
│       └── date_export=2023-10-01/
│           └── log_20231001_235959
```

##### Command-line Options:

| Option | Description |
|--------|-------------|
| `--config-path` | Path to configuration JSON file |
| `--start-date` | Start date for log retrieval (YYYY-MM-DD) |
| `--end-date` | End date for log retrieval (YYYY-MM-DD) |
| `--output-dir` | Base path for saving logs (default: /home/hylmarj/_scratch/type=amplify_logs/) |
| `--delete-after-upload` | Delete local log files after successful S3 upload |
| `--profile` | AWS profile name (for single app mode) |
| `--region` | AWS region (for single app mode) |
| `--app-id` | Amplify app ID (for single app mode) |
| `--domain-name` | Domain name (for single app mode) |
| `--app-name` | Application name (for single app mode) |
| `--s3-bucket` | S3 bucket for logs (for single app mode) |
| `--s3-prefix` | S3 prefix for logs (for single app mode) |

### Configuration File Format

The configuration file follows this structure:

```json
{
  "applications": [
    {
      "profile": "HylmarJ",
      "region": "eu-west-1",
      "appId": "d3hgg9jtwyuijn",
      "domainName": "danse.tech",
      "appName": "danse_tech"
    },
    {
      "profile": "JiHy__vsb__299",
      "region": "eu-central-1",
      "appId": "dziu0wvy5r9bx",
      "domainName": "main.dziu0wvy5r9bx.amplifyapp.com",
      "appName": "digital_horizon"
    }
  ],
  "s3": {
    "bucket": "amplifylogs-logging-intite-ss1-inftes-182059100462",
    "prefix": ""
  },
  "schedule": {
    "frequency": "weekly",
    "dayOfWeek": "Monday",
    "timeOfDay": "01:00"
  },
  "logRetention": {
    "days": 365
  },
  "timeChunkSize": {
    "days": 14
  }
}
```

## Features

- **Multiple Applications**: Process logs for multiple Amplify applications in a single run
- **Automatic Chunking**: Handles large time ranges by breaking them into smaller chunks
- **Retry Logic**: Automatically retries with smaller chunks when AWS API limits are hit
- **S3 Integration**: Uploads logs to S3 with proper path structure for Athena queries
- **Detailed Logging**: Provides progress updates and comprehensive error handling

## S3 Path Structure

Logs are saved to S3 with the following path structure:

```
s3://bucket-name/
│   └── type=amplify_logs/
│       └── app={app_name}/
│           └── date_export={YYYY-MM-DD}/
│               └── log_{YYYYMMDD_HHMMSS}
```

This structure enables efficient querying with AWS Athena.

## Logging

Logs are written to the `local/logs/amplify_logs.log` file with detailed information about each operation. This includes:
- AWS API interactions
- Success/failure of log retrievals
- S3 upload status
- Processing statistics

## Troubleshooting

- **API Rate Limiting**: The script handles AWS API rate limiting by automatically reducing the time ranges
- **Failed Downloads**: Check the detailed error logs in `local/logs/amplify_logs.log`
- **AWS Credentials**: Ensure the profiles have the correct permissions for Amplify and S3
- **Path Issues**: If encountering import errors, verify you're running the script from the correct directory

## Phase 1 Implementation

This phase includes:
- Configuration management
- Local script for downloading logs
- S3 upload functionality 
- Comprehensive error handling
- Unit tests

Future phases will include:
- AWS Lambda functions
- Step Functions workflow
- CloudFormation templates
- Glue Crawler and Athena integration
action_amplify_download_logs.py \
  --config-path /home/hylmarj/hyl-amplify-logs/local/config.json \
  --start-date 2023-10-01 \
  --end-date 2023-10-31 \
  --output-dir /home/hylmarj/_scratch/type=amplify_logs/ \
  --delete-after-upload
```

#### Using command line parameters for a single app:

```bash
python3 /home/hylmarj/hyl-amplify-logs/local/action_amplify_download_logs.py \
  --profile HylmarJ \
  --region eu-west-1 \
  --app-id d3hgg9jtwyuijn \
  --domain-name danse.tech \
  --app-name danse_tech \
  --start-date 2025-01-05 \
  --end-date 2025-01-10 \
  --s3-bucket amplifylogs-logging-intite-ss1-inftes-182059100462 \
  --output-dir /home/hylmarj/_scratch/type=amplify_logs/ \
  --delete-after-upload
```

### Usage Examples

#### 1. Basic usage with default settings:

```bash
# Uses default output directory: /home/hylmarj/_scratch/
python3 /home/hylmarj/hyl-amplify-logs/local/action_amplify_download_logs.py \
  --config-path /home/hylmarj/hyl-amplify-logs/local/config.json \
  --start-date 2023-10-01 \
  --end-date 2023-10-10
```

#### 2. Single app with S3 upload and auto-delete:

```bash
# Downloads logs, uploads to S3, then deletes local files
python3 /home/hylmarj/hyl-amplify-logs/local/action_amplify_download_logs.py \
  --profile HylmarJ \
  --region eu-west-1 \
  --app-id d3hgg9jtwyuijn \
  --domain-name danse.tech \
  --app-name danse_tech \
  --start-date 2024-12-09 \
  --end-date 2025-02-28 \
  --s3-bucket amplifylogs-logging-intite-ss1-inftes-182059100462 \
  --delete-after-upload
```
