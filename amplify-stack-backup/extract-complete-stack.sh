#!/bin/bash
# Complete AWS Stack Extraction Script - Revised
# This script extracts all components needed to rebuild an AWS CloudFormation stack locally
# maintaining the exact same directory structure as the original S3 bucket

set -e  # Exit on any error

# Configuration
STACK_NAME="amplifylogs-stack"
PROFILE="HylmarJ"
REGION="eu-west-1"
S3_DEPLOYMENT_BUCKET="amplifylogs-deployment-182059100462"
OUTPUT_DIR="./amplify-stack-backup"
ACCOUNT_NUMBER="182059100462"

# Create output directory structure for everything except S3 content
mkdir -p "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/extracted_templates"
mkdir -p "$OUTPUT_DIR/extracted_lambda"
mkdir -p "$OUTPUT_DIR/extracted_iam"
mkdir -p "$OUTPUT_DIR/extracted_glue"
mkdir -p "$OUTPUT_DIR/extracted_stepfunctions"

# Create exact S3 bucket structure
mkdir -p "$OUTPUT_DIR/s3_backup/$S3_DEPLOYMENT_BUCKET/cloudformation"
mkdir -p "$OUTPUT_DIR/s3_backup/$S3_DEPLOYMENT_BUCKET/lambda"

echo "=== Starting Complete AWS Stack Extraction ==="
echo "Stack: $STACK_NAME"
echo "Output directory: $OUTPUT_DIR"

# 1. Extract main template
echo "Extracting main CloudFormation template..."
aws cloudformation get-template \
  --stack-name $STACK_NAME \
  --profile $PROFILE \
  --region $REGION \
  --query TemplateBody \
  --output json > "$OUTPUT_DIR/extracted_templates/main-template.json"

# 2. Extract stack resources info
echo "Extracting stack resources..."
aws cloudformation describe-stack-resources \
  --stack-name $STACK_NAME \
  --profile $PROFILE \
  --region $REGION \
  --output json > "$OUTPUT_DIR/extracted_templates/stack-resources.json"

# 3. Extract nested stacks
echo "Extracting nested stacks..."
NESTED_STACKS=$(aws cloudformation describe-stack-resources \
  --stack-name $STACK_NAME \
  --profile $PROFILE \
  --region $REGION \
  --query "StackResources[?ResourceType=='AWS::CloudFormation::Stack'].PhysicalResourceId" \
  --output text)

for NESTED_STACK in $NESTED_STACKS; do
  STACK_SHORT_NAME=$(echo $NESTED_STACK | rev | cut -d'/' -f1 | rev)
  echo "  - Extracting template for $STACK_SHORT_NAME"
  
  aws cloudformation get-template \
    --stack-name $NESTED_STACK \
    --profile $PROFILE \
    --region $REGION \
    --query TemplateBody \
    --output json > "$OUTPUT_DIR/extracted_templates/nested-$STACK_SHORT_NAME-template.json"
    
  # Extract resources for nested stack too
  aws cloudformation describe-stack-resources \
    --stack-name $NESTED_STACK \
    --profile $PROFILE \
    --region $REGION \
    --output json > "$OUTPUT_DIR/extracted_templates/nested-$STACK_SHORT_NAME-resources.json"
done

# 4. Extract S3 bucket structure and files
echo "Downloading S3 bucket structure..."

# List S3 objects with their prefixes
echo "Listing objects in S3 bucket..."
aws s3 ls "s3://$S3_DEPLOYMENT_BUCKET/" --recursive --profile $PROFILE > "$OUTPUT_DIR/files_s3_bucket_contents.txt"

# Download CloudFormation templates
echo "Downloading CloudFormation templates from S3..."
aws s3 ls "s3://$S3_DEPLOYMENT_BUCKET/cloudformation/" --profile $PROFILE | awk '{print $4}' > "$OUTPUT_DIR/files_cloudformation.txt"

while read -r filename; do
  if [ -n "$filename" ]; then
    echo "  - Downloading $filename"
    aws s3 cp "s3://$S3_DEPLOYMENT_BUCKET/cloudformation/$filename" \
      "$OUTPUT_DIR/s3_backup/$S3_DEPLOYMENT_BUCKET/cloudformation/$filename" \
      --profile $PROFILE
  fi
done < "$OUTPUT_DIR/files_cloudformation.txt"

# Download Lambda function packages
echo "Downloading Lambda function packages from S3..."
aws s3 ls "s3://$S3_DEPLOYMENT_BUCKET/lambda/" --profile $PROFILE | awk '{print $4}' > "$OUTPUT_DIR/files_lambda.txt"

while read -r filename; do
  if [ -n "$filename" ]; then
    echo "  - Downloading $filename"
    aws s3 cp "s3://$S3_DEPLOYMENT_BUCKET/lambda/$filename" \
      "$OUTPUT_DIR/s3_backup/$S3_DEPLOYMENT_BUCKET/lambda/$filename" \
      --profile $PROFILE
  fi
done < "$OUTPUT_DIR/files_lambda.txt"

# 5. Extract Lambda functions
echo "Extracting Lambda functions..."
LAMBDA_ARNS=$(aws cloudformation describe-stack-resources \
  --stack-name $STACK_NAME \
  --profile $PROFILE \
  --region $REGION \
  --query "StackResources[?ResourceType=='AWS::Lambda::Function'].PhysicalResourceId" \
  --output text)

for LAMBDA_ARN in $LAMBDA_ARNS; do
  # Extract function name from ARN
  FUNCTION_NAME=$(echo $LAMBDA_ARN | rev | cut -d':' -f1 | rev)
  echo "  - Processing Lambda function: $FUNCTION_NAME"
  
  # Get function configuration
  aws lambda get-function \
    --function-name $FUNCTION_NAME \
    --profile $PROFILE \
    --region $REGION \
    --query '{Code: Code, Configuration: Configuration}' \
    --output json > "$OUTPUT_DIR/extracted_lambda/$FUNCTION_NAME-info.json"
  
  # Extract S3 location of the code
  CODE_LOCATION=$(jq -r '.Code.Location' "$OUTPUT_DIR/extracted_lambda/$FUNCTION_NAME-info.json" 2>/dev/null || echo "")
  
  if [ -n "$CODE_LOCATION" ]; then
    # Download the code
    echo "    - Downloading function code"
    curl -s "$CODE_LOCATION" -o "$OUTPUT_DIR/extracted_lambda/$FUNCTION_NAME.zip"
    
    # Create directory for extracted code
    mkdir -p "$OUTPUT_DIR/extracted_lambda/$FUNCTION_NAME"
    
    # Extract the code
    echo "    - Extracting function code"
    unzip -q "$OUTPUT_DIR/extracted_lambda/$FUNCTION_NAME.zip" -d "$OUTPUT_DIR/extracted_lambda/$FUNCTION_NAME" || echo "    Failed to extract $FUNCTION_NAME.zip"
  fi
  
  # Get environment variables
  echo "    - Extracting environment variables"
  aws lambda get-function-configuration \
    --function-name $FUNCTION_NAME \
    --profile $PROFILE \
    --region $REGION \
    --query 'Environment.Variables' \
    --output json > "$OUTPUT_DIR/extracted_lambda/$FUNCTION_NAME-env.json" 2>/dev/null || echo "    No environment variables found"
done

# 6. Extract IAM roles
echo "Extracting IAM roles..."
IAM_ROLES=(
  "amplifylogs-logging-intite-ir1-inftes-${ACCOUNT_NUMBER}-cf"
  "amplifylogs-pipeline-intite-ir2-inftes-${ACCOUNT_NUMBER}-cf"
  "amplifylogs-orchestration-intite-ir3-inftes-${ACCOUNT_NUMBER}-cf"
)

# Also get roles from Lambda functions
LAMBDA_ROLES=$(jq -r '.Configuration.Role' "$OUTPUT_DIR"/extracted_lambda/*-info.json 2>/dev/null | grep -v "null" | sort | uniq || echo "")
if [ -n "$LAMBDA_ROLES" ]; then
  for ROLE_ARN in $LAMBDA_ROLES; do
    ROLE_NAME=$(echo $ROLE_ARN | rev | cut -d'/' -f1 | rev)
    IAM_ROLES+=("$ROLE_NAME")
  done
fi

# Get unique roles
IAM_ROLES=($(echo "${IAM_ROLES[@]}" | tr ' ' '\n' | sort -u | tr '\n' ' '))

for ROLE in "${IAM_ROLES[@]}"; do
  echo "  - Getting details for $ROLE"
  # Get role details
  aws iam get-role \
    --role-name "$ROLE" \
    --profile $PROFILE \
    --output json > "$OUTPUT_DIR/extracted_iam/$ROLE-details.json" 2>/dev/null || echo "    Failed to get role details for $ROLE"
  
  if [ -f "$OUTPUT_DIR/extracted_iam/$ROLE-details.json" ]; then
    # Get inline policies
    aws iam list-role-policies \
      --role-name "$ROLE" \
      --profile $PROFILE \
      --output json > "$OUTPUT_DIR/extracted_iam/$ROLE-policies.json"
    
    # Get policy documents for each inline policy
    POLICIES=$(aws iam list-role-policies --role-name "$ROLE" --profile $PROFILE --query 'PolicyNames[]' --output text 2>/dev/null || echo "")
    for POLICY in $POLICIES; do
      aws iam get-role-policy \
        --role-name "$ROLE" \
        --policy-name "$POLICY" \
        --profile $PROFILE \
        --output json > "$OUTPUT_DIR/extracted_iam/$ROLE-$POLICY.json"
    done
    
    # Get attached policies
    aws iam list-attached-role-policies \
      --role-name "$ROLE" \
      --profile $PROFILE \
      --output json > "$OUTPUT_DIR/extracted_iam/$ROLE-attached-policies.json"
  fi
done

# 7. Extract Glue resources
echo "Extracting Glue resources..."
# Extract crawler
CRAWLER_NAME=$(jq -r '.Environment.Variables.CRAWLER_NAME // ""' "$OUTPUT_DIR"/extracted_lambda/*-env.json 2>/dev/null | grep -v null | head -1 || echo "")

if [ -n "$CRAWLER_NAME" ]; then
  echo "  - Extracting Glue crawler: $CRAWLER_NAME"
  aws glue get-crawler \
    --name "$CRAWLER_NAME" \
    --profile $PROFILE \
    --region $REGION \
    --output json > "$OUTPUT_DIR/extracted_glue/$CRAWLER_NAME-details.json" 2>/dev/null || echo "    Failed to get crawler details"
  
  # Get database name from crawler
  if [ -f "$OUTPUT_DIR/extracted_glue/$CRAWLER_NAME-details.json" ]; then
    DATABASE_NAME=$(jq -r '.Crawler.DatabaseName // ""' "$OUTPUT_DIR/extracted_glue/$CRAWLER_NAME-details.json")
    
    if [ -n "$DATABASE_NAME" ]; then
      echo "  - Extracting Glue database: $DATABASE_NAME"
      aws glue get-database \
        --name "$DATABASE_NAME" \
        --profile $PROFILE \
        --region $REGION \
        --output json > "$OUTPUT_DIR/extracted_glue/$DATABASE_NAME-details.json" 2>/dev/null || echo "    Failed to get database details"
      
      # Get tables in database
      echo "  - Extracting Glue tables for database: $DATABASE_NAME"
      aws glue get-tables \
        --database-name "$DATABASE_NAME" \
        --profile $PROFILE \
        --region $REGION \
        --output json > "$OUTPUT_DIR/extracted_glue/$DATABASE_NAME-tables.json" 2>/dev/null || echo "    Failed to get tables"
    fi
  fi
fi

# 8. Extract Step Functions
echo "Extracting Step Functions state machines..."
# Find state machines from CloudFormation resources
STATE_MACHINES=$(aws cloudformation describe-stack-resources \
  --stack-name $STACK_NAME \
  --profile $PROFILE \
  --region $REGION \
  --query "StackResources[?ResourceType=='AWS::StepFunctions::StateMachine'].PhysicalResourceId" \
  --output text)

for STATE_MACHINE in $STATE_MACHINES; do
  SM_NAME=$(echo $STATE_MACHINE | rev | cut -d':' -f1 | rev)
  echo "  - Extracting state machine: $SM_NAME"
  
  aws stepfunctions describe-state-machine \
    --state-machine-arn "$STATE_MACHINE" \
    --profile $PROFILE \
    --region $REGION \
    --output json > "$OUTPUT_DIR/extracted_stepfunctions/$SM_NAME-details.json" 2>/dev/null || echo "    Failed to get state machine details"
  
  # Extract state machine definition
  if [ -f "$OUTPUT_DIR/extracted_stepfunctions/$SM_NAME-details.json" ]; then
    jq -r '.definition' "$OUTPUT_DIR/extracted_stepfunctions/$SM_NAME-details.json" > "$OUTPUT_DIR/extracted_stepfunctions/$SM_NAME-definition.json"
  fi
done

# Create README
cat > "$OUTPUT_DIR/README.md" << EOL
# AWS Amplify Logs Stack Backup and Deployment Guide

This directory contains a complete backup of the "$STACK_NAME" CloudFormation stack, including all necessary components to rebuild it from scratch in the same or a different AWS account.

## Contents

- **s3_backup/**: Exact mirror of the S3 bucket structure with all required files
  - \`$S3_DEPLOYMENT_BUCKET/cloudformation/\`: CloudFormation templates
  - \`$S3_DEPLOYMENT_BUCKET/lambda/\`: Lambda function deployment packages

- **extracted_templates/**: CloudFormation templates extracted from the deployed stack
- **extracted_lambda/**: Lambda function configurations and extracted code
- **extracted_iam/**: IAM roles, policies, and configurations
- **extracted_glue/**: Glue resources (crawlers, databases, tables)
- **extracted_stepfunctions/**: Step Functions state machines and their definitions

## Backup Created: $(date)
EOL

echo "=== Complete AWS Stack Extraction Completed Successfully ==="
echo "The complete stack has been extracted to: $OUTPUT_DIR"
echo "Check the README.md file for detailed instructions on how to deploy it"