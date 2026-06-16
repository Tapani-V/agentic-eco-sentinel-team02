#!/bin/bash
# Deploy FastAPI MCP tool to AWS App Runner from ECR
# Usage: bash scripts/deploy_create_work_order_apprunner.sh <ECR_IMAGE_URL> <ECR_PULL_ROLE_ARN> <PROFILE>

set -e

if [ $# -ne 3 ]; then
  echo "Usage: $0 <ECR_IMAGE_URL> <ECR_PULL_ROLE_ARN> <PROFILE>"
  exit 1
fi

ECR_IMAGE_URL="$1"
ECR_PULL_ROLE_ARN="$2"
PROFILE="$3"

SERVICE_NAME="create-work-order-apprunner"
REGION="us-east-1"

aws apprunner create-service \
  --service-name "$SERVICE_NAME" \
  --source-configuration '{
    "ImageRepository": {
      "ImageIdentifier": "'$ECR_IMAGE_URL'",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "8000"
      }
    },
    "AuthenticationConfiguration": {
      "AccessRoleArn": "'$ECR_PULL_ROLE_ARN'"
    }
  }' \
  --region $REGION \
  --profile $PROFILE

echo "App Runner service creation initiated. Run the following to get the public URL:"
echo "aws apprunner list-services --region $REGION --profile $PROFILE"
echo "# Find the ServiceArn, then:"
echo "aws apprunner describe-service --service-arn <ServiceArn> --region $REGION --profile $PROFILE"
echo "# Look for ServiceUrl in the output."
