#!/bin/bash
#
# Build and push AgentCore Runtime images (ARM64, required by AWS Bedrock
# AgentCore Runtime) to ECR.
#
# Usage: ./deployment/agentcore-runtime/build_and_push.sh [--env-file FILE] [orchestrator|health_agent|diagnosis_agent]
#
# Run from the repository root. Builds all 3 agent images (or just one, if
# named as an argument) using the Dockerfiles in this directory, then pushes
# them to ECR. After pushing, register/update the runtime(s) with:
#   python3 scripts/deploy_to_agentcore_boto3.py --profile <your-profile>
#
# Team image tag: images are tagged "${TEAM_ID}" (from the env file or the
# environment) instead of "latest", so a team's rebuild never overwrites the
# shared ":latest" image other teams/the default deployment may still use.
# TEAM_ID is required - source the env file first or export it manually.
#
# --env-file FILE: load TEAM_ID/AWS_ACCOUNT_ID/AWS_REGION from FILE instead of
# the default .agentcore.env - use this to point at a team-specific file (e.g.
# .agentcore.env.team01) without touching the original.

set -e

ENV_FILE=".agentcore.env"
AGENT_FILTER=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        *)
            AGENT_FILTER="$1"
            shift
            ;;
    esac
done

if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1091
    set -a; source "$ENV_FILE"; set +a
fi

if [ -z "$TEAM_ID" ]; then
    echo "Error: TEAM_ID is not set. Add TEAM_ID=<yourteam> to $ENV_FILE or export it." >&2
    exit 1
fi
ACCOUNT_ID="${AWS_ACCOUNT_ID:-450410489798}"
REGION="${AWS_REGION:-us-east-1}"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
DOCKERFILE_DIR="deployment/agentcore-runtime"
TAG="$TEAM_ID"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}================================================================================${NC}"
echo -e "${BLUE}Building + Pushing ARM64 AgentCore Runtime Images${NC}"
echo -e "${BLUE}================================================================================${NC}"

if [ ! -f "${DOCKERFILE_DIR}/orchestrator.Dockerfile" ]; then
    echo -e "${YELLOW}Error: run this script from the repository root.${NC}"
    exit 1
fi

declare -a IMAGES=("orchestrator" "health_agent:health-agent" "diagnosis_agent:diagnosis-agent")

if [ -n "$AGENT_FILTER" ]; then
    declare -a FILTERED=()
    for IMAGE_SPEC in "${IMAGES[@]}"; do
        DOCKERFILE_NAME="${IMAGE_SPEC%:*}"
        if [ "$DOCKERFILE_NAME" = "$AGENT_FILTER" ]; then
            FILTERED+=("$IMAGE_SPEC")
        fi
    done
    if [ ${#FILTERED[@]} -eq 0 ]; then
        echo -e "${YELLOW}Error: unknown agent '${AGENT_FILTER}'. Expected one of: orchestrator, health_agent, diagnosis_agent${NC}"
        exit 1
    fi
    IMAGES=("${FILTERED[@]}")
fi

BUILT_IMAGES=()
FAILED_IMAGES=()

for IMAGE_SPEC in "${IMAGES[@]}"; do
    DOCKERFILE_NAME="${IMAGE_SPEC%:*}"
    ECR_NAME="${IMAGE_SPEC##*:}"
    if [ "$ECR_NAME" = "$DOCKERFILE_NAME" ]; then
        ECR_NAME="$DOCKERFILE_NAME"
    fi
    DOCKERFILE="${DOCKERFILE_DIR}/${DOCKERFILE_NAME}.Dockerfile"

    echo ""
    echo -e "${YELLOW}Building: ${ECR_NAME} (${DOCKERFILE})${NC}"
    if docker buildx build \
        --platform linux/arm64 \
        -f "$DOCKERFILE" \
        -t "${ECR_NAME}:arm64" \
        --load \
        .; then
        docker tag "${ECR_NAME}:arm64" "${REGISTRY}/${ECR_NAME}:${TAG}"
        BUILT_IMAGES+=("$ECR_NAME")
        echo -e "${GREEN}Built and tagged: ${REGISTRY}/${ECR_NAME}:${TAG}${NC}"
    else
        FAILED_IMAGES+=("$ECR_NAME")
        echo -e "${YELLOW}Build failed: ${ECR_NAME}${NC}"
    fi
done

if [ ${#FAILED_IMAGES[@]} -gt 0 ]; then
    echo -e "${YELLOW}Failed to build: ${FAILED_IMAGES[*]}${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Logging in to ECR...${NC}"
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"

for IMAGE in "${BUILT_IMAGES[@]}"; do
    echo -e "${YELLOW}Pushing: ${IMAGE}${NC}"
    docker push "${REGISTRY}/${IMAGE}:${TAG}"
    echo -e "${GREEN}Pushed: ${REGISTRY}/${IMAGE}:${TAG}${NC}"
done

echo ""
echo -e "${GREEN}All images built and pushed with tag :${TAG}.${NC}"
echo "Next: python3 scripts/deploy_to_agentcore_boto3.py --profile StandardAccess-${ACCOUNT_ID}"
