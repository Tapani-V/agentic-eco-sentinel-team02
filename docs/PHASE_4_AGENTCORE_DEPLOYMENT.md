# Phase 4: Bedrock AgentCore Runtime Deployment

**Status:** In Progress (Image Architecture Conversion)  
**Date:** 2026-07-10  
**Platform:** AWS Bedrock Agentic AI (AgentCore Runtime, Gateway, Memory)

---

## Overview

Phase 4 deploys agents from local Docker containers to **AWS Bedrock AgentCore Runtime**, a managed service for running containerized agents at scale.

### Key Differences from Phase 2-3

| Aspect | Phase 2-3 (Local) | Phase 4 (AgentCore) |
|--------|-------------------|-------------------|
| **Deployment** | docker-compose locally | Bedrock AgentCore Runtime |
| **Architecture** | x86_64 (amd64) | ARM64 (required) |
| **Image Build** | Standard Docker | Docker buildx (multi-platform) |
| **Image Location** | ECR (any arch) | ECR (must be arm64) |
| **Scaling** | Manual | Automatic (0-N instances) |
| **Networking** | Local docker network | AWS VPC / Public (configurable) |

---

## Prerequisites

### 1. Docker Buildx Setup

AgentCore Runtime requires **arm64 (ARM) architecture** images. Docker buildx enables cross-platform builds.

**Check if installed:**
```bash
docker buildx version
```

**Expected output:**
```
github.com/docker/buildx v0.28.0 b1281b81bba797b21d9eaf256e6a13eb14419836
✅ Docker buildx is available
```

If not installed, install via Docker Desktop or:
```bash
docker run --privileged --rm tonistiigi/binfmt --install all
docker buildx create --use
```

### 2. AWS Credentials

Requires SSO profile with Bedrock and ECR permissions:
```bash
export AWS_PROFILE=StandardAccess-450410489798
export AWS_REGION=us-east-1
```

### 3. ECR Authentication

Ensure Docker daemon can push to ECR:
```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 450410489798.dkr.ecr.us-east-1.amazonaws.com
```

---

## Image Architecture Requirement

### Why ARM64?

AgentCore Runtime runs on **AWS infrastructure optimized for arm64** (Graviton processors):
- Cost-effective
- High performance
- Industry standard for managed container services

### Image Build Process

**Option 1: Use build scripts (recommended - simpler)**

```bash
cd /home/skroy/AGENTIC_AI_POC_Phase3_1

# 1. Build all 3 images for ARM64
./scripts/build_arm64_images.sh

# 2. Push to ECR
source .agentcore.env
./scripts/push_arm64_images.sh

# 3. Deploy to AgentCore
python3 scripts/deploy_to_agentcore_boto3.py --profile "$AWS_PROFILE" --region us-east-1
```

**Option 2: Manual commands (if scripts unavailable)**

First, ensure ECR login:
```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 450410489798.dkr.ecr.us-east-1.amazonaws.com
```

Build and push each image:

```bash
# Orchestrator
docker buildx build --platform linux/arm64 \
  -f Dockerfile.orchestrator \
  -t 450410489798.dkr.ecr.us-east-1.amazonaws.com/orchestrator:latest \
  --push .

# Health Agent
docker buildx build --platform linux/arm64 \
  -f Dockerfile.health_agent \
  -t 450410489798.dkr.ecr.us-east-1.amazonaws.com/health-agent:latest \
  --push .

# Diagnosis Agent
docker buildx build --platform linux/arm64 \
  -f Dockerfile.diagnosis_agent \
  -t 450410489798.dkr.ecr.us-east-1.amazonaws.com/diagnosis-agent:latest \
  --push .
```

Then deploy:
```bash
python3 scripts/deploy_to_agentcore_boto3.py --profile StandardAccess-450410489798 --region us-east-1
```

---

## Deployment Checklist

## IAM Role and Policies

### AgentCore Execution Role

**Role Name:** `AgentCoreExecutionRole`  
**ARN:** `arn:aws:iam::450410489798:role/AgentCoreExecutionRole`  
**Created:** 2025-12-15 18:38:27 UTC

### Trust Policy

Allows these services to assume the role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": [
          "ecs-tasks.amazonaws.com",
          "bedrock-agentcore.amazonaws.com",
          "bedrock.amazonaws.com",
          "runtime-identity.bedrock-agentcore.amazonaws.com"
        ]
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

### Attached Policies

| Policy Name | Purpose |
|-------------|---------|
| `AgentCoreEvalPolicy` | Evaluation framework access |
| `AgentCoreFullAccess` | Full AgentCore API access |
| `AgentcoreIdentity` | Runtime identity management |
| `AgentCore_TransactionSearch` | Transaction/audit logging |
| `BedrockAccess` | Base Bedrock model access |
| `BedrockModelAccess` | Model invocation permissions |
| `ECRFullAccess` | ECR image pull/push |

### Key Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ECRAccess",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer"
      ],
      "Resource": "*"
    },
    {
      "Sid": "S3Access",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::agentic-ai-poc-synthetic-data",
        "arn:aws:s3:::agentic-ai-poc-synthetic-data/*"
      ]
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:450410489798:log-group:/aws/bedrock/agentcore/*"
    },
    {
      "Sid": "AgentCoreMemory",
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:BatchCreateMemoryRecords",
        "bedrock-agentcore:BatchDeleteMemoryRecords",
        "bedrock-agentcore:BatchGetMemoryRecords",
        "bedrock-agentcore:BatchUpdateMemoryRecords"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## Deployment Script

**Location:** `scripts/deploy_to_agentcore_boto3.py`  
**Type:** Standalone Python (no framework dependencies)

### How It Works

1. **Initialize boto3 clients:**
   - `bedrock-agentcore-control` - Runtime management
   - `iam` - Role verification
   - `sts` - Account identity

2. **For each agent:**
   - Validate configuration
   - Create AgentCore Runtime with:
     - ECR container URI (arm64 image)
     - IAM role ARN
     - Network configuration
     - Environment variables
     - Scaling config (min/max instances)

3. **Output:**
   - `agent_endpoints.json` - Runtime endpoints for dashboard

### Configuration

**Agent specs in script:**

```python
agents_config = {
    "orchestrator": {
        "type": "orchestrator",      # Always running
        "cpu": 256,                  # AWS fargate units
        "memory": 512,               # MB
        "timeout": 60,               # seconds
        "min_instances": 1,
        "max_instances": 5
    },
    "health_agent": {
        "type": "worker",            # On-demand
        "cpu": 256,
        "memory": 512,
        "timeout": 30,
        "min_instances": 0,
        "max_instances": 3
    },
    "diagnosis_agent": {
        "type": "worker",
        "cpu": 256,
        "memory": 512,
        "timeout": 60,
        "min_instances": 0,
        "max_instances": 3
    }
}
```

---

## Deployment Checklist

### Phase 4.1: Image Architecture Conversion ✅ IN PROGRESS

- [ ] **Rebuild orchestrator image (arm64)**
  ```bash
  docker buildx build --platform linux/arm64 -f Dockerfile.orchestrator \
    -t 450410489798.dkr.ecr.us-east-1.amazonaws.com/orchestrator:latest --push .
  ```
  Status: Building...

- [ ] **Rebuild health-agent image (arm64)**
  ```bash
  docker buildx build --platform linux/arm64 -f Dockerfile.health_agent \
    -t 450410489798.dkr.ecr.us-east-1.amazonaws.com/health-agent:latest --push .
  ```

- [ ] **Rebuild diagnosis-agent image (arm64)**
  ```bash
  docker buildx build --platform linux/arm64 -f Dockerfile.diagnosis_agent \
    -t 450410489798.dkr.ecr.us-east-1.amazonaws.com/diagnosis-agent:latest --push .
  ```

- [ ] Verify images in ECR (should show `linux/arm64` platform tag)

### Phase 4.2: Deploy to AgentCore Runtime

- [ ] Run deployment script:
  ```bash
  python3 scripts/deploy_to_agentcore_boto3.py \
    --profile StandardAccess-450410489798 \
    --region us-east-1
  ```

- [ ] Verify `agent_endpoints.json` created with valid runtime IDs

- [ ] Test health checks on deployed agents

- [ ] Verify S3 access still works (device loader test)

### Phase 4.3: Dashboard Integration

- [ ] Update dashboard to read `agent_endpoints.json`

- [ ] Redirect requests from localhost to AgentCore endpoints

- [ ] Test end-to-end workflow via dashboard

### Phase 4.4: Documentation & Git

- [ ] Update README with AgentCore deployment steps

- [ ] Document docker buildx requirement

- [ ] Commit: "Phase 4: Deploy agents to AgentCore Runtime
  - Convert images to arm64 using docker buildx
  - Create AgentCore Runtime runtimes via boto3
  - Use AgentCoreExecutionRole for permissions
  - Generate deployment endpoints"

---

## Troubleshooting

### Build Issue: "Architecture incompatible"

**Error:**
```
Architecture incompatible for uri '...'. Supported platforms: [arm64]
```

**Solution:**  
Rebuild images with `--platform linux/arm64` using docker buildx.

### Deploy Issue: "Role validation failed"

**Error:**
```
Role validation failed for 'arn:aws:iam::...'. Please verify trust policy allows assumption
```

**Solution:**  
Ensure `AgentCoreExecutionRole` has:
- Trust policy including `bedrock-agentcore.amazonaws.com`
- Inline policies: `AgentCoreFullAccess`, `ECRFullAccess`

### Build Timeout

**If buildx build takes >10min:**
- Buildx may be using emulation (slow)
- Consider using native arm64 builder or AWS CodeBuild

**Check builder platform:**
```bash
docker buildx inspect
```

### ECR Push Fails

**Ensure authenticated:**
```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  450410489798.dkr.ecr.us-east-1.amazonaws.com
```

---

## AWS Agentic AI Services

This deployment uses:

| Service | Purpose |
|---------|---------|
| **Bedrock AgentCore Runtime** | Managed containerized agent execution |
| **Bedrock AgentCore Gateway** | API gateway for agent invocation (future phase) |
| **Bedrock AgentCore Memory** | Persistent agent state and conversation history |
| **Bedrock Models** | Claude 3 via AgentCore |
| **S3** | Synthetic device data (agentic-ai-poc-synthetic-data bucket) |
| **CloudWatch** | Agent logs and metrics |

---

## References

- AWS Bedrock AgentCore Documentation: https://docs.aws.amazon.com/bedrock/
- Docker buildx Guide: https://docs.docker.com/build/architecture/
- ARM64/Graviton Info: https://aws.amazon.com/graviton/

---

## Next Steps

1. ✅ Complete arm64 image builds
2. ✅ Deploy agents to AgentCore Runtime
3. ⏳ Integrate AgentCore endpoints in dashboard
4. ⏳ Test end-to-end workflow
5. ⏳ Document AgentCore Gateway integration (Phase 5)
