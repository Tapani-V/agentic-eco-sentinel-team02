#!/bin/bash
# Push create-work-order Docker image to ECR (Step 5e)
# Usage: bash scripts/push_create_work_order_to_ecr.sh [--env-file FILE] [--region REGION] [--profile PROFILE] [--repo-name NAME] [--image-tag TAG]
#
# --env-file FILE: load TEAM_ID/AWS_REGION/AWS_PROFILE from FILE (e.g.
# .agentcore.env.team01) as defaults - explicit flags below still win over it.
# The image tag defaults to "${TEAM_ID}" (instead of "latest") so pushing for
# one team never overwrites another team's image in the shared
# "create-work-order" ECR repo - same convention as
# deployment/agentcore-runtime/build_and_push.sh. Without --env-file/TEAM_ID,
# behavior is unchanged (repo "create-work-order", tag "latest").

set -e

ENV_FILE=""
CLI_REGION=""
CLI_PROFILE=""
CLI_REPO_NAME=""
CLI_IMAGE_TAG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --region) CLI_REGION="$2"; shift 2 ;;
    --profile) CLI_PROFILE="$2"; shift 2 ;;
    --repo-name) CLI_REPO_NAME="$2"; shift 2 ;;
    --image-tag) CLI_IMAGE_TAG="$2"; shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

if [ -n "$ENV_FILE" ]; then
  if [ ! -f "$ENV_FILE" ]; then
    echo "Environment file not found: $ENV_FILE" >&2
    exit 1
  fi
  # shellcheck disable=SC1091
  set -a; source "$ENV_FILE"; set +a
fi

AWS_REGION="${CLI_REGION:-${AWS_REGION:-us-east-1}}"
PROFILE="${CLI_PROFILE:-${AWS_PROFILE:-}}"
REPO_NAME="${CLI_REPO_NAME:-create-work-order}"
IMAGE_TAG="${CLI_IMAGE_TAG:-${TEAM_ID:-latest}}"

PROFILE_ARGS=()
if [ -n "$PROFILE" ]; then
  PROFILE_ARGS=(--profile "$PROFILE")
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$AWS_REGION" "${PROFILE_ARGS[@]}")
ECR_URL="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO_NAME:$IMAGE_TAG"

# 1. Create ECR repo if it doesn't exist
aws ecr describe-repositories --repository-names "$REPO_NAME" --region "$AWS_REGION" "${PROFILE_ARGS[@]}" >/dev/null 2>&1 || \
  aws ecr create-repository --repository-name "$REPO_NAME" --region "$AWS_REGION" "${PROFILE_ARGS[@]}"

echo "ECR repository ensured: $REPO_NAME (region: $AWS_REGION)"

# 2. Authenticate Docker to ECR
aws ecr get-login-password --region "$AWS_REGION" "${PROFILE_ARGS[@]}" | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

echo "Docker authenticated to ECR."

# 3. Tag the image (build it first: docker build -t create-work-order:latest src/ecs_tasks/create_work_order/)

docker tag create-work-order:latest "$ECR_URL"

echo "Image tagged: $ECR_URL"

# 4. Push the image

docker push "$ECR_URL"

echo "Image pushed to: $ECR_URL"
echo "Use this image URL with deploy_create_work_order_apprunner.sh: $ECR_URL"
