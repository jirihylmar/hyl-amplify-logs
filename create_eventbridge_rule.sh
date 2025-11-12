#!/bin/bash
# create_eventbridge_rule.sh - Script to create the EventBridge rule manually

# Set variables
ENVIRONMENT="inftes"
AWS_PROFILE="HylmarJ"
AWS_REGION="eu-west-1"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --profile $AWS_PROFILE --query Account --output text)
RULE_NAME="amplifylogs-orchestration-intite-eb1-${ENVIRONMENT}-${AWS_ACCOUNT_ID}-cf"
EVENTBRIDGE_ROLE_NAME="amplifylogs-orchestration-intite-ir2-${ENVIRONMENT}-${AWS_ACCOUNT_ID}-cf"

# Get the State Machine ARN from the stack outputs
STATE_MACHINE_ARN=$(aws cloudformation describe-stacks \
  --stack-name amplifylogs-stack \
  --profile $AWS_PROFILE \
  --region $AWS_REGION \
  --query "Stacks[0].Outputs[?OutputKey=='StateMachineArn'].OutputValue" \
  --output text)

if [ -z "$STATE_MACHINE_ARN" ]; then
  echo "Error: Could not find State Machine ARN. Make sure the stack deployed successfully."
  exit 1
fi

echo "Found State Machine ARN: $STATE_MACHINE_ARN"

# Create the IAM role for EventBridge
echo "Creating IAM role for EventBridge..."

# Create temporary files for the trust policy and role policy
TRUST_POLICY_FILE=$(mktemp)
ROLE_POLICY_FILE=$(mktemp)

cat > $TRUST_POLICY_FILE << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "events.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

cat > $ROLE_POLICY_FILE << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "states:StartExecution",
      "Resource": "${STATE_MACHINE_ARN}"
    }
  ]
}
EOF

# Check if the role already exists
ROLE_EXISTS=$(aws iam get-role --role-name $EVENTBRIDGE_ROLE_NAME --profile $AWS_PROFILE 2>/dev/null || echo "false")

if [ "$ROLE_EXISTS" == "false" ]; then
  # Create the role
  aws iam create-role \
    --role-name $EVENTBRIDGE_ROLE_NAME \
    --assume-role-policy-document file://$TRUST_POLICY_FILE \
    --profile $AWS_PROFILE

  # Add tags to the role
  aws iam tag-role \
    --role-name $EVENTBRIDGE_ROLE_NAME \
    --tags \
      Key=Project,Value=amplifylogs \
      Key=Owner,Value=HylmarJ \
      Key=CostCenter,Value=cc-amplify-001 \
      Key=Environment,Value=$ENVIRONMENT \
    --profile $AWS_PROFILE

  # Attach the policy to the role
  aws iam put-role-policy \
    --role-name $EVENTBRIDGE_ROLE_NAME \
    --policy-name StepFunctionsExecution \
    --policy-document file://$ROLE_POLICY_FILE \
    --profile $AWS_PROFILE
else
  echo "Role $EVENTBRIDGE_ROLE_NAME already exists, updating policy..."
  # Update the policy
  aws iam put-role-policy \
    --role-name $EVENTBRIDGE_ROLE_NAME \
    --policy-name StepFunctionsExecution \
    --policy-document file://$ROLE_POLICY_FILE \
    --profile $AWS_PROFILE
fi

# Wait for role to propagate
echo "Waiting for role to propagate..."
sleep 10

# Get the role ARN
ROLE_ARN=$(aws iam get-role \
  --role-name $EVENTBRIDGE_ROLE_NAME \
  --profile $AWS_PROFILE \
  --query "Role.Arn" \
  --output text)

echo "Role ARN: $ROLE_ARN"

# Create a JSON file with the target configuration
TARGET_FILE=$(mktemp)

cat > $TARGET_FILE << EOF
[
  {
    "Id": "AmplifyLogsWorkflow",
    "Arn": "${STATE_MACHINE_ARN}",
    "RoleArn": "${ROLE_ARN}",
    "Input": "{\\"config\\": {\\"applications\\": [{\\"profile\\": \\"HylmarJ\\", \\"region\\": \\"eu-west-1\\", \\"appId\\": \\"d3hgg9jtwyuijn\\", \\"domainName\\": \\"danse.tech\\", \\"appName\\": \\"danse_tech\\"}, {\\"profile\\": \\"JiHy__vsb__299\\", \\"region\\": \\"eu-central-1\\", \\"appId\\": \\"dziu0wvy5r9bx\\", \\"domainName\\": \\"main.dziu0wvy5r9bx.amplifyapp.com\\", \\"appName\\": \\"digital_horizon\\"}], \\"s3\\": {\\"bucket\\": \\"amplifylogs-logging-intite-ss2-inftes-182059100462\\", \\"prefix\\": \\"\\"}, \\"timeChunkSize\\": {\\"days\\": 14}, \\"logRetention\\": {\\"days\\": 365}}}"
  }
]
EOF

# Check if the rule already exists
RULE_EXISTS=$(aws events describe-rule --name $RULE_NAME --profile $AWS_PROFILE --region $AWS_REGION 2>/dev/null || echo "false")

if [ "$RULE_EXISTS" == "false" ]; then
  # Create the EventBridge rule
  echo "Creating EventBridge rule..."
  aws events put-rule \
    --name $RULE_NAME \
    --schedule-expression "cron(0 1 ? * MON *)" \
    --state ENABLED \
    --description "Weekly trigger for Amplify Logs processing" \
    --tags Key=Project,Value=amplifylogs Key=Owner,Value=HylmarJ Key=CostCenter,Value=cc-amplify-001 Key=Environment,Value=$ENVIRONMENT \
    --profile $AWS_PROFILE \
    --region $AWS_REGION
else
  echo "Rule $RULE_NAME already exists, updating..."
  aws events put-rule \
    --name $RULE_NAME \
    --schedule-expression "cron(0 1 ? * MON *)" \
    --state ENABLED \
    --description "Weekly trigger for Amplify Logs processing" \
    --profile $AWS_PROFILE \
    --region $AWS_REGION
fi

# Add the target to the rule
echo "Adding target to rule..."
aws events put-targets \
  --rule $RULE_NAME \
  --targets file://$TARGET_FILE \
  --profile $AWS_PROFILE \
  --region $AWS_REGION

# Clean up temporary files
rm -f $TRUST_POLICY_FILE $ROLE_POLICY_FILE $TARGET_FILE

echo "EventBridge rule created successfully!"