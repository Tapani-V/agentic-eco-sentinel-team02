#!/bin/bash
# Push create-work-order Docker image to ECR (Step 5e)
# Usage: bash scripts/push_create_work_order_to_ecr.sh

set -e

AWS_REGION=us-east-1
ACCOUNT_ID=450410489798
REPO_NAME=create-work-order
IMAGE_TAG=latest
ECR_URL="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO_NAME:$IMAGE_TAG"

# 1. Create ECR repo if it doesn't exist
aws ecr describe-repositories --repository-names $REPO_NAME --region $AWS_REGION >/dev/null 2>&1 || \
  aws ecr create-repository --repository-name $REPO_NAME --region $AWS_REGION

echo "ECR repository ensured: $REPO_NAME"

# 2. Authenticate Docker to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

echo "Docker authenticated to ECR."

# 3. Tag the image

docker tag create-work-order:latest $ECR_URL

echo "Image tagged: $ECR_URL"

# 4. Push the image

docker push $ECR_URL

echo "Image pushed to: $ECR_URL"
