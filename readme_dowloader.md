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
mkdir -p src/local
mkdir -p src/lambda
mkdir -p src/cloudformation
mkdir -p src/athena
mkdir -p tests
mkdir -p docs/assistants

# Create Python package files
touch src/__init__.py
touch src/local/__init__.py
touch tests/__init__.py
```

4. Create a configuration file (`config.json`) based on the sample provided.

### Usage

#### Using configuration file:

```bash
# Make sure to run as a module to avoid import issues
python -m src.local.action_amplify_download_logs \
  --config-path config.json \
  --start-date 2023-10-01 \
  --end-date 2023-10-31 \
  --output-dir /path/to/logs
```

#### Using command line parameters for a single app:

```bash
python -m src.local.action_amplify_download_logs \
  --profile HylmarJ \
  --region eu-west-1 \
  --app-id d3hgg9jtwyuijn \
  --domain-name danse.tech \
  --app-name danse_tech \
  --start-date 2023-10-01 \
  --end-date 2023-10-31 \
  --s3-bucket amplifylogs-logging-intite-ss1-inftes-182059100462 \
  --output-dir /path/to/logs
```

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
├── app={app_name}/
│   └── type=amplify_logs/
│       └── date_export={YYYY-MM-DD}/
│           └── log_{YYYYMMDD_HHMMSS}
```

This structure enables efficient querying with AWS Athena.

## Testing

Run the unit tests:

```bash
# Run all tests
python -m unittest discover tests

# Run specific test class
python -m unittest tests.test_log_download.TestConfigLoader
python -m unittest tests.test_log_download.TestAmplifyLogDownloader
```

If you encounter import errors, make sure:
1. All directories have `__init__.py` files
2. You're running from the project root directory
3. You're using the `-m` flag to run as a module

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

## Troubleshooting

- **API Rate Limiting**: The script handles AWS API rate limiting by automatically reducing the time ranges
- **Failed Downloads**: Check the detailed error logs in `amplify_logs.log`
- **AWS Credentials**: Ensure the profiles have the correct permissions for Amplify and S3
