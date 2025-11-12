I'll adjust the architecture document to create more appropriate component categories for the Amplify logs project, removing the IoT-specific terminology.

# AMPLIFY LOGS ARCHITECTURE - System Design Document

## 1. Overview

This document outlines the architecture for an AWS-based system that automates the downloading and storage of AWS Amplify logs data. The solution uses AWS services including S3, Lambda, Step Functions, and EventBridge to create a scalable, reliable pipeline for log data collection.

## 2. System Architecture

### 2.1 High-Level Architecture

The system follows a serverless architecture pattern with these key components:

1. **EventBridge** - Schedules weekly log download jobs
2. **Step Functions** - Orchestrates the workflow and handles retry logic
3. **Lambda Functions** - Executes log downloads and processing
4. **S3 Bucket** - Central storage for log data
5. **Glue Crawler** - Updates Athena database schema
6. **Athena** - Enables SQL queries against log data

```
[EventBridge] --triggers--> [Step Function] --executes--> [Lambda Functions]
                                              |
                                              v
[Athena] <--queries-- [Glue Database] <--updated by-- [Glue Crawler] <--triggered by-- [S3 Bucket]
```

### 2.2 Component Details

#### 2.2.1 S3 Bucket Structure

The central S3 bucket will store logs with this structure:

```
s3://amplifylogs-logging-intite-ss1-inftes-182059100462/
├── type=amplify_logs/
│   └── app={app_name}/
│       └── date_export={YYYY-MM-DD}/
│           └── log_{YYYYMMDD_HHMMSS}
```

#### 2.2.2 Lambda Functions

**Log Downloader Lambda**
- Handles the download of AWS Amplify logs for specified apps and time ranges
- Implements retry logic with auto-scaling time ranges
- Saves logs to appropriate S3 paths
- Processes configuration from environment variables and input events

**Crawler Trigger Lambda**
- Triggered after successful log downloads
- Starts Glue Crawler to update Athena schema

#### 2.2.3 Step Function Workflow

The Step Function orchestrates the entire process:
1. Parse configuration
2. Calculate date ranges for log collection (using a sliding window approach)
3. Execute Log Downloader Lambda for each app/time range
4. Handle failures with appropriate retries
5. Trigger Glue Crawler after successful downloads

#### 2.2.4 EventBridge Rule

- Scheduled to run weekly
- Triggers the Step Function with configuration parameters

#### 2.2.5 Glue Crawler and Athena Integration

- Crawler updates the AWS Glue Data Catalog
- Athena queries use the schema defined in the Data Catalog
- Partition structure matches S3 path hierarchy

## 3. Configuration Structure

The system is configured via a JSON document:

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

## 4. Resource Naming Conventions

All resources will follow this naming pattern:
`amplifylogs-{component}-{privacy}-{service}{version}-{env}-{account}`

Where:
- `amplifylogs` - Project identifier
- `{component}` - Component category (logging, pipeline, orchestration, etc.)
- `{privacy}` - Privacy status (intite, extite)
- `{service}` - AWS service shortcode (ss, lm, sf, etc.)
- `{version}` - Version identifier (0, 1, 2)
- `{env}` - Environment (infdev, inftes, infpro)
- `{account}` - Account number (182059100462)

### Component Categories for Amplify Logs Project

- `logging` - Log collection and storage resources
- `pipeline` - Processing and transformation resources
- `orchestration` - Workflow management resources
- `monitoring` - System monitoring resources
- `analysis` - Analytics and querying resources

### Resource Examples

- S3 Bucket: `amplifylogs-logging-intite-ss1-inftes-182059100462`
- Log Downloader Lambda: `amplifylogs-logging-intite-lm1-inftes-182059100462`
- Crawler Trigger Lambda: `amplifylogs-pipeline-intite-lm1-inftes-182059100462`
- Step Function: `amplifylogs-orchestration-intite-sf1-inftes-182059100462`
- EventBridge Rule: `amplifylogs-orchestration-intite-eb1-inftes-182059100462`
- Glue Crawler: `amplifylogs-pipeline-intite-gl1-inftes-182059100462`
- Glue Database: `amplifylogs-analysis-intite-gd1-inftes-182059100462`
- IAM Role: `amplifylogs-logging-intite-ir1-inftes-182059100462`

## 5. AWS IAM Roles and Permissions

### 5.1 Lambda Execution Role

- S3 read/write permissions for the central log bucket
- CloudWatch Logs creation and management
- AWS Amplify access for log generation
- Cross-account role assumption (for multi-account scenarios)
- Glue Crawler start permission

### 5.2 Step Function Execution Role

- Invoke Lambda functions
- Manage workflow execution state
- CloudWatch Logs creation and management

### 5.3 Glue Crawler Role

- S3 read access to log bucket
- Glue Data Catalog read/write permissions

## 6. Error Handling and Resilience

### 6.1 Lambda Function Design

- Maximum timeout of 15 minutes
- Implements chunking strategy for logs:
  - Default chunk size: 14 days
  - Automatic subdivision of time ranges when API limits are hit
  - Maximum recursion depth of 3 levels for subdividing time ranges

### 6.2 Step Function Error Handling

- State-specific retry configurations
- Error notifications via SNS
- Parallel execution for multiple apps
- Map state for processing time chunks within each app

### 6.3 Monitoring and Alerts

- CloudWatch Alarms for:
  - Failed Step Function executions
  - Lambda timeouts
  - S3 storage thresholds
  - Glue Crawler failures
- S3 storage metrics with alerts at 80% of quota

## 7. Resource Tagging

All resources will be tagged with:
```json
{
  "Project": "amplifylogs",
  "Owner": "HylmarJ",
  "CostCenter": "cc-amplify-001",
  "Environment": "testing"
}
```

## 8. Resource Requirements

### 8.1 Lambda Configuration

- Memory: 1024 MB
- Timeout: 15 minutes
- Concurrent executions: Based on number of applications

### 8.2 S3 Storage Estimation

- Estimated log size: ~10MB per app per day
- Annual storage for 2 apps: ~7.3 GB

### 8.3 Athena Query Optimization

- Partitioning by app, log type, and date for efficient querying
- Compression of log files to reduce storage costs and improve query performance

## 9. Implementation Plan

### 9.1 Phase 1: Core Infrastructure

1. Set up S3 bucket with appropriate structure and lifecycle policies
2. Implement Log Downloader Lambda
3. Create basic Step Function workflow
4. Configure IAM roles and permissions

### 9.2 Phase 2: Automation and Integration

1. Implement EventBridge scheduled trigger
2. Add Glue Crawler configuration
3. Set up Athena integration
4. Implement cross-account access mechanism

### 9.3 Phase 3: Monitoring and Optimization

1. Configure CloudWatch Alarms
2. Implement cost monitoring and reporting
3. Optimize Lambda performance

## 10. Directory Structure

```
hyl-amplify-logs/
├── README.md
├── docs/
│   ├── architecture.md          # This document
│   └── assistants/
│       └── instructions_01.md   # Instructions for LLM code generation
├── src/
│   ├── athena/
│   │   └── ana___danse_tech__amplify_logs.sql
│   ├── cloudformation/
│   │   ├── main.yaml            # Main CloudFormation template
│   │   ├── crawler.yaml         # Glue Crawler resources
│   │   ├── lambda.yaml          # Lambda function resources
│   │   ├── s3.yaml              # S3 bucket configuration
│   │   └── step-functions.yaml  # Step Function workflow
│   ├── lambda/
│   │   ├── log_downloader/      # Log downloader Lambda function
│   │   └── crawler_trigger/     # Crawler trigger Lambda function
│   ├── stepfunctions/
│   │   └── workflow.asl.json    # Step Function workflow definition
│   └── local/
│       ├── action_amplify_download_logs.py
│       └── action_amplify_log_analysis.py
└── tests/
    ├── fixtures/                # Test fixtures
    └── unit/                    # Unit tests for components
```

## 11. AWS CloudFormation Resources

### 11.1 S3 Bucket (s3.yaml)

- S3 Bucket with versioning
- Lifecycle policies for log rotation
- Tags for cost tracking
- Server-side encryption

### 11.2 Lambda Functions (lambda.yaml)

- Log Downloader Lambda
- Crawler Trigger Lambda
- IAM Roles and Policies
- Environment variables for configuration

### 11.3 Step Functions (step-functions.yaml)

- State machine definition
- Error handling configurations
- IAM Roles and Policies

### 11.4 Glue Crawler (crawler.yaml)

- Glue Crawler configuration
- Database configuration
- IAM Roles and Policies

### 11.5 EventBridge Rule (main.yaml)

- Scheduled rule for triggering the workflow
- Target configuration for Step Functions

## 12. Appendix

### 12.1 Log Format Details

CSV log format with fields:
```
date,time,x-edge-location,sc-bytes,c-ip,cs-method,cs(Host),cs-uri-stem,sc-status,cs(Referer),cs(User-Agent),cs-uri-query,cs(Cookie),x-edge-result-type,x-edge-request-id,x-host-header,cs-protocol,cs-bytes,time-taken,x-forwarded-for,ssl-protocol,ssl-cipher,x-edge-response-result-type,cs-protocol-version,fle-status,fle-encrypted-fields,c-port,time-to-first-byte,x-edge-detailed-result-type,sc-content-type,sc-content-len,sc-range-start,sc-range-end
```

### 12.2 Lambda Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| CONFIG_JSON | JSON configuration string | N/A |
| BUCKET_NAME | S3 bucket name | amplifylogs-logging-intite-ss1-inftes-182059100462 |
| DEFAULT_CHUNK_SIZE_DAYS | Default time chunk size | 14 |
| LOG_LEVEL | Logging level | INFO |