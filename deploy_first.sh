#!/bin/bash
# deploy.sh - Deployment script for AWS Amplify Logs project

# Exit on error
set -e

# Set variables
STACK_NAME="amplifylogs-stack"
ENVIRONMENT="inftes"
AWS_PROFILE="HylmarJ"
AWS_REGION="eu-west-1"
DEPLOYMENT_BUCKET="amplifylogs-deployment-182059100462"
S3_PREFIX="cloudformation"

# Get account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --profile $AWS_PROFILE --query Account --output text)

echo "Using AWS Account ID: $AWS_ACCOUNT_ID"

# Create build directory if it doesn't exist
mkdir -p build

# Upload templates to S3
echo "Uploading CloudFormation templates to S3..."
aws s3 cp src/cloudformation/ s3://$DEPLOYMENT_BUCKET/$S3_PREFIX/ \
  --recursive \
  --profile $AWS_PROFILE \
  --region $AWS_REGION

# Update Lambda code
echo "Updating Lambda functions code..."
zip -j build/log_downloader_lambda.zip src/lambda/log_downloader/lambda_function.py
zip -j build/crawler_trigger_lambda.zip src/lambda/crawler_trigger/lambda_function.py
zip -j build/calculate_time_ranges_lambda.zip src/lambda/calculate_time_ranges/lambda_function.py

# Upload Lambda code to S3
echo "Uploading Lambda code to S3..."
aws s3 cp build/log_downloader_lambda.zip s3://$DEPLOYMENT_BUCKET/lambda/ --profile $AWS_PROFILE --region $AWS_REGION
aws s3 cp build/crawler_trigger_lambda.zip s3://$DEPLOYMENT_BUCKET/lambda/ --profile $AWS_PROFILE --region $AWS_REGION
aws s3 cp build/calculate_time_ranges_lambda.zip s3://$DEPLOYMENT_BUCKET/lambda/ --profile $AWS_PROFILE --region $AWS_REGION

# Validate CloudFormation templates
echo "Validating CloudFormation templates..."
if ! aws cloudformation validate-template \
  --template-url https://$DEPLOYMENT_BUCKET.s3.$AWS_REGION.amazonaws.com/$S3_PREFIX/main.yaml \
  --profile $AWS_PROFILE \
  --region $AWS_REGION; then
    echo "Template validation failed. Aborting deployment."
    exit 1
fi

# First check if the logs bucket exists and create it if needed
LOGS_BUCKET_NAME="amplifylogs-logging-intite-ss2-${ENVIRONMENT}-${AWS_ACCOUNT_ID}"
if ! aws s3api head-bucket --bucket $LOGS_BUCKET_NAME --profile $AWS_PROFILE 2>/dev/null; then
    echo "Logs bucket $LOGS_BUCKET_NAME does not exist, setting CreateNewS3Bucket=true"
    CREATE_NEW_BUCKET=true
else
    echo "Logs bucket $LOGS_BUCKET_NAME already exists"
    CREATE_NEW_BUCKET=false
fi

# Function to check if stack is in ROLLBACK_COMPLETE state
function check_stack_rollback_state {
    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name $STACK_NAME --profile $AWS_PROFILE --region $AWS_REGION &> /dev/null; then
        # Get stack status
        STACK_STATUS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --profile $AWS_PROFILE --region $AWS_REGION --query "Stacks[0].StackStatus" --output text)
        
        # Check if stack is in ROLLBACK_COMPLETE state
        if [ "$STACK_STATUS" == "ROLLBACK_COMPLETE" ]; then
            echo "Stack $STACK_NAME is in ROLLBACK_COMPLETE state and must be deleted."
            read -p "Delete stack $STACK_NAME? (y/n) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                echo "Deleting stack $STACK_NAME..."
                aws cloudformation delete-stack --stack-name $STACK_NAME --profile $AWS_PROFILE --region $AWS_REGION
                
                echo "Waiting for stack deletion to complete..."
                aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --profile $AWS_PROFILE --region $AWS_REGION
                
                echo "Stack deletion complete."
                return 0  # Stack was deleted
            else
                echo "Aborting deployment."
                exit 1
            fi
        fi
    fi
    
    return 1  # Stack was not deleted
}

# Define deployment function for better error handling
function deploy_stack {
    # Check if stack is in ROLLBACK_COMPLETE state and delete it if needed
    check_stack_rollback_state
    
    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name $STACK_NAME --profile $AWS_PROFILE --region $AWS_REGION &> /dev/null; then
        echo "Stack $STACK_NAME exists, updating..."
        # Update the stack
        aws cloudformation update-stack \
          --stack-name $STACK_NAME \
          --template-url https://$DEPLOYMENT_BUCKET.s3.$AWS_REGION.amazonaws.com/$S3_PREFIX/main.yaml \
          --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
          --parameters \
              ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
              ParameterKey=AccountNumber,ParameterValue=$AWS_ACCOUNT_ID \
              ParameterKey=LogRetentionDays,ParameterValue=365 \
              ParameterKey=CreateNewS3Bucket,ParameterValue=$CREATE_NEW_BUCKET \
          --profile $AWS_PROFILE \
          --region $AWS_REGION

        # Wait for stack update to complete
        echo "Waiting for stack update to complete..."
        if ! aws cloudformation wait stack-update-complete --stack-name $STACK_NAME --profile $AWS_PROFILE --region $AWS_REGION; then
            echo "Stack update failed or rolled back."
            get_stack_errors
            return 1
        fi
    else
        echo "Stack $STACK_NAME does not exist, creating..."
        # Create the stack
        aws cloudformation create-stack \
          --stack-name $STACK_NAME \
          --template-url https://$DEPLOYMENT_BUCKET.s3.$AWS_REGION.amazonaws.com/$S3_PREFIX/main.yaml \
          --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
          --parameters \
              ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
              ParameterKey=AccountNumber,ParameterValue=$AWS_ACCOUNT_ID \
              ParameterKey=LogRetentionDays,ParameterValue=365 \
              ParameterKey=CreateNewS3Bucket,ParameterValue=$CREATE_NEW_BUCKET \
          --profile $AWS_PROFILE \
          --region $AWS_REGION

        # Wait for stack creation to complete
        echo "Waiting for stack creation to complete..."
        if ! aws cloudformation wait stack-create-complete --stack-name $STACK_NAME --profile $AWS_PROFILE --region $AWS_REGION; then
            echo "Stack creation failed or rolled back."
            get_stack_errors
            return 1
        fi
    fi
    
    return 0
}

# Function to get detailed error information
function get_stack_errors {
    echo "Getting detailed error information:"
    # Get failed events
    aws cloudformation describe-stack-events \
      --stack-name $STACK_NAME \
      --profile $AWS_PROFILE \
      --region $AWS_REGION \
      --query "StackEvents[?ResourceStatus=='CREATE_FAILED' || ResourceStatus=='UPDATE_FAILED' || ResourceStatus=='ROLLBACK_IN_PROGRESS'].{Resource:LogicalResourceId, Status:ResourceStatus, Reason:ResourceStatusReason}" \
      --output table
    
    # Get stack status
    STACK_STATUS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --profile $AWS_PROFILE --region $AWS_REGION --query "Stacks[0].StackStatus" --output text)
    echo "Current stack status: $STACK_STATUS"
}

# Execute deployment
if deploy_stack; then
    # Get stack status
    STACK_STATUS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --profile $AWS_PROFILE --region $AWS_REGION --query "Stacks[0].StackStatus" --output text)
    echo "Stack deployment successful! Status: $STACK_STATUS"
    
    # Get CloudFormation outputs
    echo "Stack outputs:"
    aws cloudformation describe-stacks --stack-name $STACK_NAME --profile $AWS_PROFILE --region $AWS_REGION --query "Stacks[0].Outputs" --output table
else
    echo "Stack deployment failed!"
fi