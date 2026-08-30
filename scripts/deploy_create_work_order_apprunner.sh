#!/bin/bash
# Deploy FastAPI MCP tool to AWS App Runner from ECR
# Usage: bash scripts/deploy_create_work_order_apprunner.sh [--region REGION] [--service-name NAME] [--env-file PATH] <ECR_IMAGE_URL> <ECR_PULL_ROLE_ARN> <PROFILE>

set -e

REGION="us-east-1"
SERVICE_NAME="create-work-order-apprunner"
ENV_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region) REGION="$2"; shift 2 ;;
    --service-name) SERVICE_NAME="$2"; shift 2 ;;
    --env-file) ENV_FILE="$2"; shift 2 ;;
    *) break ;;
  esac
done

if [ $# -ne 3 ]; then
  echo "Usage: $0 [--region REGION] [--service-name NAME] [--env-file PATH] <ECR_IMAGE_URL> <ECR_PULL_ROLE_ARN> <PROFILE>"
  exit 1
fi

ECR_IMAGE_URL="$1"
ECR_PULL_ROLE_ARN="$2"
PROFILE="$3"

SERVICE_ARN=$(aws apprunner create-service \
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
  --region "$REGION" \
  --profile "$PROFILE" \
  --query 'Service.ServiceArn' \
  --output text)

echo "App Runner service creation initiated: $SERVICE_ARN"
echo "Waiting for $SERVICE_NAME to become RUNNING..."

for _ in {1..90}; do
  STATUS=$(aws apprunner describe-service \
    --service-arn "$SERVICE_ARN" \
    --region "$REGION" \
    --profile "$PROFILE" \
    --query 'Service.Status' \
    --output text)

  if [[ "$STATUS" == "RUNNING" ]]; then
    SERVICE_URL=$(aws apprunner describe-service \
      --service-arn "$SERVICE_ARN" \
      --region "$REGION" \
      --profile "$PROFILE" \
      --query 'Service.ServiceUrl' \
      --output text)
    CREATE_WORK_ORDER_URL="https://$SERVICE_URL/work_order"
    echo "Service is RUNNING: $CREATE_WORK_ORDER_URL"

    if [[ -n "$ENV_FILE" ]]; then
      if [[ ! -f "$ENV_FILE" ]]; then
        echo "Environment file not found: $ENV_FILE" >&2
        exit 1
      fi
      if grep -q '^CREATE_WORK_ORDER_URL=' "$ENV_FILE"; then
        sed -i "s|^CREATE_WORK_ORDER_URL=.*|CREATE_WORK_ORDER_URL=$CREATE_WORK_ORDER_URL|" "$ENV_FILE"
      else
        printf '\nCREATE_WORK_ORDER_URL=%s\n' "$CREATE_WORK_ORDER_URL" >> "$ENV_FILE"
      fi
      echo "CREATE_WORK_ORDER_URL saved to $ENV_FILE"
    fi
    exit 0
  fi

  if [[ "$STATUS" == "CREATE_FAILED" || "$STATUS" == "DELETE_FAILED" ]]; then
    echo "App Runner service entered terminal failure state: $STATUS" >&2
    exit 1
  fi

  echo "Current status: $STATUS"
  sleep 10
done

echo "Timed out waiting for App Runner service to become RUNNING" >&2
exit 1
