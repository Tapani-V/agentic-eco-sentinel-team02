#!/bin/bash
# Push create-work-order Docker image to ECR (Step 5e)
# Usage: bash scripts/push_create_work_order_to_ecr.sh [--region REGION] [--profile PROFILE] [--repo-name NAME]

set -e

AWS_REGION=us-east-1
PROFILE=""
REPO_NAME=create-work-order
IMAGE_TAG=latest

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region) AWS_REGION="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --repo-name) REPO_NAME="$2"; shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

PROFILE_ARGS=()
if [ -n "$PROFILE" ]; then
  PROFILE_ARGS=(--profile "$PROFILE")
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$AWS_REGION" "${PROFILE_ARGS[@]}")
ECR_URL="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO_NAME:$IMAGE_TAG"

# 1. Create ECR repo if it doesn't exist
aws ecr describe-repositories --repository-names $REPO_NAME --region $AWS_REGION "${PROFILE_ARGS[@]}" >/dev/null 2>&1 || \
  aws ecr create-repository --repository-name $REPO_NAME --region $AWS_REGION "${PROFILE_ARGS[@]}"

echo "ECR repository ensured: $REPO_NAME (region: $AWS_REGION)"

# 2. Authenticate Docker to ECR
aws ecr get-login-password --region $AWS_REGION "${PROFILE_ARGS[@]}" | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

echo "Docker authenticated to ECR."

# 3. Tag the image (build it first: docker build -t create-work-order:latest src/ecs_tasks/create_work_order/)

docker tag create-work-order:latest $ECR_URL

echo "Image tagged: $ECR_URL"

# 4. Push the image

docker push $ECR_URL

echo "Image pushed to: $ECR_URL"
