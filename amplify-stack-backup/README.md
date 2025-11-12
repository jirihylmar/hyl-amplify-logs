# AWS Amplify Logs Stack Backup and Deployment Guide

This directory contains a complete backup of the "amplifylogs-stack" CloudFormation stack, including all necessary components to rebuild it from scratch in the same or a different AWS account.

## Contents

- **s3_backup/**: Exact mirror of the S3 bucket structure with all required files
  - `amplifylogs-deployment-182059100462/cloudformation/`: CloudFormation templates
  - `amplifylogs-deployment-182059100462/lambda/`: Lambda function deployment packages

- **extracted_templates/**: CloudFormation templates extracted from the deployed stack
- **extracted_lambda/**: Lambda function configurations and extracted code
- **extracted_iam/**: IAM roles, policies, and configurations
- **extracted_glue/**: Glue resources (crawlers, databases, tables)
- **extracted_stepfunctions/**: Step Functions state machines and their definitions

## Backup Created: Fri Mar 28 13:12:29 CET 2025
