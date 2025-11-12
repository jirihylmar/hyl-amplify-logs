# Instructions for LLM Code Generation - Amplify Logs Project

## Overview

These instructions will guide you through implementing the AWS Amplify Logs Architecture in a series of simple, manageable steps. The goal is to create a system that downloads AWS Amplify logs and stores them in S3 for analysis through Athena.

## Development Approach

We'll take an incremental approach:
1. Start with local development and testing
2. Progress to AWS infrastructure implementation
3. Complete the full serverless architecture

## Environment Setup

### Local Development Environment

Set up a basic local development environment without using virtual environments:

```
hyl-amplify-logs/
├── README.md
├── docs/
│   ├── architecture.md
│   └── assistants/
│       ├── instructions_01.md
│       └── instructions_02.md  # This file
├── src/
│   ├── local/
│   │   ├── action_amplify_download_logs.py  # Existing file
│   │   └── action_amplify_log_analysis.py   # Existing file
│   ├── lambda/
│   ├── cloudformation/
│   └── athena/
└── tests/
```

### Required AWS CLI Setup

Ensure AWS CLI is configured with appropriate profiles:
- HylmarJ (main account 182059100462)
- Any additional profiles for cross-account access

## Implementation Steps

### Phase 1: Enhance Local Scripts

1. **Refactor Existing Scripts**
   - Improve the existing `action_amplify_download_logs.py` to handle multiple apps
   - Add proper error handling and logging
   - Ensure it follows the same patterns we'll use in Lambda

2. **Add Configuration Loading**
   - Create a configuration reader for the JSON structure
   - Implement validation for the configuration

3. **Implement S3 Upload**
   - Add functionality to upload logs to S3 with the correct path structure:
     ```
     s3://amplifylogs-logging-intite-ss1-inftes-182059100462/type=amplify_logs/app={app_name}/date_export={YYYY-MM-DD}/log_{YYYYMMDD_HHMMSS}
     ```

### Phase 2: Lambda Function Implementation

1. **Log Downloader Lambda**
   - Create a simple adapter from your local script to run in Lambda
   - Add appropriate error handling and timeouts
   - Implement the chunking strategy for large time ranges

2. **Crawler Trigger Lambda**
   - Implement a simple Lambda that triggers the Glue Crawler
   - Add proper error handling and logging

### Phase 3: CloudFormation Templates

1. **S3 Bucket Template**
   - Create a template for the central log storage bucket
   - Add appropriate lifecycle policies and permissions

2. **Lambda Functions Template**
   - Create a template for both Lambda functions
   - Include IAM roles with the minimum required permissions

3. **Step Functions Template**
   - Create a Step Functions workflow that orchestrates the process
   - Implement retry logic and error handling

4. **Glue Resources Template**
   - Create Glue Crawler and database resources
   - Configure for Athena integration

5. **Main Template**
   - Create a master template that combines all resources
   - Add EventBridge rule for scheduling

### Phase 4: Testing

1. **Basic Unit Tests**
   - Test the configuration loader
   - Test the log downloading logic
   - Test the S3 upload functionality

2. **Athena Query Examples**
   - Create sample Athena queries for common analyses

## Detailed Implementation Guidelines

### Configuration Structure

The configuration JSON should match exactly the format in the architecture document:

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

### Lambda Function Structure

The Log Downloader Lambda should:
1. Accept an event with application details and time range
2. Download logs using the Amplify CLI or API
3. Upload logs to S3
4. Return status information

Example event structure:
```json
{
  "app": {
    "profile": "HylmarJ",
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
    "bucket": "amplifylogs-logging-intite-ss1-inftes-182059100462",
    "prefix": ""
  }
}
```

### Step Functions Workflow

The Step Function should:
1. Parse the configuration input
2. Calculate date ranges based on the current date and chunk size
3. Use the Map state to process each application
4. Use a nested Map state to process each time chunk
5. Trigger the Glue Crawler at the end

### Resource Naming

Follow the naming convention from the architecture document:
`amplifylogs-{component}-{privacy}-{service}{version}-{env}-{account}`

Component categories:
- `logging` - Log collection and storage resources
- `pipeline` - Processing and transformation resources
- `orchestration` - Workflow management resources
- `monitoring` - System monitoring resources
- `analysis` - Analytics and querying resources

## Important Considerations

1. **Lambda Timeouts**
   - Default chunk size: 14 days
   - Implement automatic subdivision when API limits are hit
   - Maximum recursion depth of 3 levels

2. **Error Handling**
   - Implement robust error handling at each level
   - Include detailed logging for troubleshooting
   - Use Step Functions retry mechanisms

3. **Resource Tagging**
   - Tag all resources with:
     - Project: amplifylogs
     - Owner: HylmarJ
     - CostCenter: cc-amplify-001
     - Environment: testing

## Example Implementation (First Lambda Function)

Start with this basic structure for the Lambda function:

```python
import boto3
import json
import os
import subprocess
import logging
from datetime import datetime, timedelta

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda handler for downloading Amplify logs and uploading to S3
    
    Expected event format:
    {
        "app": {
            "profile": "HylmarJ",
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
            "bucket": "amplifylogs-logging-intite-ss1-inftes-182059100462",
            "prefix": ""
        }
    }
    """
    # Implementation goes here
    pass
```

## Deliverables

For each phase, provide:
1. Complete Python or CloudFormation code with comments
2. Instructions for how to test
3. Any configuration files needed

Start with the basics and we'll build incrementally toward the full architecture.