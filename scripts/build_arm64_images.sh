#!/bin/bash
#
# Build ARM64 Docker Images for Bedrock AgentCore Runtime
#
# Usage: ./scripts/build_arm64_images.sh
#
# This script builds Docker images for linux/arm64 architecture
# (required by AWS Bedrock AgentCore Runtime)

set -e

ACCOUNT_ID="450410489798"
REGION="us-east-1"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================================================${NC}"
echo -e "${BLUE}🔨 Building ARM64 Docker Images for Bedrock AgentCore Runtime${NC}"
echo -e "${BLUE}================================================================================${NC}"
echo ""

# Verify we're in the right directory
if [ ! -f "Dockerfile.orchestrator" ]; then
    echo -e "${YELLOW}❌ Error: Dockerfile.orchestrator not found in current directory${NC}"
    exit 1
fi

# Array of images to build
declare -a IMAGES=(
    "orchestrator"
    "health_agent:Dockerfile.health_agent"
    "diagnosis_agent:Dockerfile.diagnosis_agent"
)

FAILED_IMAGES=()
BUILT_IMAGES=()

for IMAGE_SPEC in "${IMAGES[@]}"; do
    IMAGE_NAME="${IMAGE_SPEC%:*}"
    DOCKERFILE="${IMAGE_SPEC##*:}"
    
    # Default dockerfile if not specified
    if [ "$DOCKERFILE" = "$IMAGE_NAME" ]; then
        DOCKERFILE="Dockerfile.${IMAGE_NAME}"
    fi
    
    echo ""
    echo -e "${BLUE}─────────────────────────────────────────────────────────────────────────────${NC}"
    echo -e "${YELLOW}📦 Building: ${IMAGE_NAME}${NC}"
    echo -e "${BLUE}─────────────────────────────────────────────────────────────────────────────${NC}"
    echo "   Dockerfile: $DOCKERFILE"
    echo "   Platform: linux/arm64"
    echo "   Local Tag: ${IMAGE_NAME}:arm64"
    echo ""
    
    # Step 1: Build locally (load into docker, verbose)
    echo -e "${YELLOW}Step 1/2: Building image (no push)...${NC}"
    if docker buildx build \
        --platform linux/arm64 \
        -f "$DOCKERFILE" \
        -t "${IMAGE_NAME}:arm64" \
        --load \
        .; then
        echo -e "${GREEN}✅ Build successful!${NC}"
        BUILT_IMAGES+=("$IMAGE_NAME")
    else
        echo -e "${YELLOW}❌ Build failed!${NC}"
        FAILED_IMAGES+=("$IMAGE_NAME")
        continue
    fi
    
    # Step 2: Tag for ECR
    echo ""
    echo -e "${YELLOW}Step 2/2: Tagging for ECR...${NC}"
    docker tag "${IMAGE_NAME}:arm64" "${REGISTRY}/${IMAGE_NAME}:latest"
    echo -e "${GREEN}✅ Tagged as: ${REGISTRY}/${IMAGE_NAME}:latest${NC}"
    
    echo ""
done

# Summary
echo ""
echo -e "${BLUE}================================================================================${NC}"
echo -e "${BLUE}📊 BUILD SUMMARY${NC}"
echo -e "${BLUE}================================================================================${NC}"

if [ ${#BUILT_IMAGES[@]} -gt 0 ]; then
    echo -e "${GREEN}✅ Successfully Built (${#BUILT_IMAGES[@]}):${NC}"
    for img in "${BUILT_IMAGES[@]}"; do
        echo "   • $img:arm64"
    done
fi

if [ ${#FAILED_IMAGES[@]} -gt 0 ]; then
    echo -e "${YELLOW}❌ Failed to Build (${#FAILED_IMAGES[@]}):${NC}"
    for img in "${FAILED_IMAGES[@]}"; do
        echo "   • $img"
    done
    exit 1
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Next Step: Push images to ECR${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Ensure ECR login:"
echo "  aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${REGISTRY}"
echo ""
echo "Push images:"
for img in "${BUILT_IMAGES[@]}"; do
    echo "  docker push ${REGISTRY}/${img}:latest"
done
echo ""
echo "Or run: ./scripts/push_arm64_images.sh"
echo ""
