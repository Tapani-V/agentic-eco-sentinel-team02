#!/bin/bash
# Deploy FastAPI MCP tool to AWS App Runner from ECR
# Usage: bash scripts/deploy_create_work_order_apprunner.sh [--region REGION] [--service-name NAME] <ECR_IMAGE_URL> <ECR_PULL_ROLE_ARN> <PROFILE>

set -e

REGION="us-east-1"
SERVICE_NAME="create-work-order-apprunner"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region) REGION="$2"; shift 2 ;;
    --service-name) SERVICE_NAME="$2"; shift 2 ;;
    *) break ;;
  esac
done

if [ $# -ne 3 ]; then
  echo "Usage: $0 [--region REGION] [--service-name NAME] <ECR_IMAGE_URL> <ECR_PULL_ROLE_ARN> <PROFILE>"
  exit 1
fi

ECR_IMAGE_URL="$1"
ECR_PULL_ROLE_ARN="$2"
PROFILE="$3"

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
