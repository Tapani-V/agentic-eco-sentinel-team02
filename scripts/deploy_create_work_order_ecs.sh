#!/bin/bash
# Step 5f+5g: Create ECS task definition and deploy service for create_work_order
# Usage: bash scripts/deploy_create_work_order_ecs.sh <ECR_IMAGE_URL>

set -e

AWS_REGION=us-east-1
CLUSTER_NAME=agentic-ai-poc-ecs
SERVICE_NAME=create-work-order-service
TASK_FAMILY=create-work-order-task
CONTAINER_NAME=create-work-order
ECR_IMAGE_URL="$1"

if [ -z "$ECR_IMAGE_URL" ]; then
  echo "Usage: $0 <ECR_IMAGE_URL>"
  echo "Example: $0 450410489798.dkr.ecr.us-east-1.amazonaws.com/create-work-order:latest"
  exit 1
fi

# 1. Register ECS task definition
cat > create_work_order_taskdef.json <<EOF
{
  "family": "$TASK_FAMILY",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [
    {
      "name": "$CONTAINER_NAME",
      "image": "$ECR_IMAGE_URL",
      "portMappings": [
        { "containerPort": 8000, "protocol": "tcp" }
      ],
      "essential": true
    }
  ]
}
EOF

echo "Registering ECS task definition..."
aws ecs register-task-definition --cli-input-json file://create_work_order_taskdef.json --region $AWS_REGION

echo "Task definition registered."

# 2. Create ECS cluster if not exists
aws ecs describe-clusters --clusters $CLUSTER_NAME --region $AWS_REGION | grep 'MISSING' >/dev/null 2>&1 && \
  aws ecs create-cluster --cluster-name $CLUSTER_NAME --region $AWS_REGION

echo "ECS cluster ensured: $CLUSTER_NAME"

# 3. Create or update ECS service
SERVICE_EXISTS=$(aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $AWS_REGION --query "services[0].status" --output text 2>/dev/null)
if [ "$SERVICE_EXISTS" = "ACTIVE" ]; then
  echo "Updating ECS service..."
  aws ecs update-service --cluster $CLUSTER_NAME --service $SERVICE_NAME --force-new-deployment --region $AWS_REGION
else
  echo "Creating ECS service..."
  aws ecs create-service \
    --cluster $CLUSTER_NAME \
    --service-name $SERVICE_NAME \
    --task-definition $TASK_FAMILY \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxxxx],securityGroups=[sg-xxxxxxx],assignPublicIp=ENABLED}" \
    --region $AWS_REGION
  echo "NOTE: Replace subnet-xxxxxxx and sg-xxxxxxx with your actual subnet and security group IDs."
fi

echo "ECS deployment script complete."
