#!/bin/bash
#
# Push ARM64 Docker Images to ECR
#
# Usage: ./scripts/push_arm64_images.sh
#
# This script pushes pre-built arm64 images to ECR

set -e

ACCOUNT_ID="450410489798"
REGION="us-east-1"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}================================================================================${NC}"
echo -e "${BLUE}📤 Pushing ARM64 Images to ECR${NC}"
echo -e "${BLUE}================================================================================${NC}"
echo ""

# Get AWS_PROFILE from environment or use default
AWS_PROFILE="${AWS_PROFILE:-StandardAccess-450410489798}"
export AWS_PROFILE

# Check ECR login
echo -e "${YELLOW}Checking ECR authentication...${NC}"
echo "Using AWS Profile: $AWS_PROFILE"
if ! docker info | grep -q "Username:"; then
    echo -e "${YELLOW}⚠️  Not authenticated to ECR. Logging in...${NC}"
    aws --profile "$AWS_PROFILE" ecr get-login-password --region "$REGION" | \
        docker login --username AWS --password-stdin "$REGISTRY"
    echo -e "${GREEN}✅ Logged in to ECR${NC}"
else
    echo -e "${GREEN}✅ Already authenticated to ECR${NC}"
fi

echo ""

IMAGES=("orchestrator" "health-agent" "diagnosis-agent")
FAILED=()
PUSHED=()

for IMAGE in "${IMAGES[@]}"; do
    echo -e "${BLUE}─────────────────────────────────────────────────────────────────────────────${NC}"
    echo -e "${YELLOW}📤 Pushing: ${IMAGE}${NC}"
    echo ""
    
    IMAGE_TAG="${REGISTRY}/${IMAGE}:latest"
    
    if docker push "$IMAGE_TAG"; then
        echo -e "${GREEN}✅ Successfully pushed: ${IMAGE}${NC}"
        PUSHED+=("$IMAGE")
    else
        echo -e "${YELLOW}❌ Failed to push: ${IMAGE}${NC}"
        FAILED+=("$IMAGE")
    fi
    echo ""
done

# Summary
echo -e "${BLUE}================================================================================${NC}"
echo -e "${BLUE}📊 PUSH SUMMARY${NC}"
echo -e "${BLUE}================================================================================${NC}"

if [ ${#PUSHED[@]} -gt 0 ]; then
    echo -e "${GREEN}✅ Successfully Pushed (${#PUSHED[@]}):${NC}"
    for img in "${PUSHED[@]}"; do
        echo "   • ${REGISTRY}/${img}:latest"
    done
fi

if [ ${#FAILED[@]} -gt 0 ]; then
    echo -e "${YELLOW}❌ Failed to Push (${#FAILED[@]}):${NC}"
    for img in "${FAILED[@]}"; do
        echo "   • ${REGISTRY}/${img}:latest"
    done
    exit 1
fi

echo ""
echo -e "${GREEN}✅ All images pushed successfully!${NC}"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "1. Verify in ECR: aws ecr describe-images --repository-name orchestrator --region ${REGION}"
echo "2. Deploy: python3 scripts/deploy_to_agentcore_boto3.py --profile StandardAccess-${ACCOUNT_ID}"
echo ""
