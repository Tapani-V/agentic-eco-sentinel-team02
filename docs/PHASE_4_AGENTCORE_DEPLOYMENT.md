# Phase 4: Bedrock AgentCore Runtime Deployment

**Status:** ✅ Complete (deployed, tested end-to-end via dashboard)  
**Date:** 2026-07-10 (initial) / 2026-07-24 (invocation protocol + agent logic fixes)  
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

## Container Invocation Protocol (Critical - read this before debugging 502/500s)

**Building an ARM64 image and getting the AgentCore Runtime to show "Ready" is
NOT sufficient for the agent to actually work.** A container that just runs
`uvicorn app:app` (FastAPI, or any other HTTP framework/CLI script with its
own custom routes) will pass the initial deployment/health-status check but
will **never receive real invocations**, because AgentCore Runtime does not
talk to containers the way you might expect.

### How AgentCore Runtime actually invokes a container

AgentCore Runtime calls the container over plain HTTP, on a fixed contract:

- `POST /invocations` (port **8080**) - the actual invocation. AgentCore sends
  the JSON payload passed to `boto3.invoke_agent_runtime(payload=...)` as the
  request body, and expects the handler's return value back as the response.
- `GET /ping` (port **8080**) - health/readiness check, polled continuously.

This is a fixed, non-configurable protocol (comparable to how AWS Lambda has
its own Runtime API, or SageMaker inference containers expect `/invocations`
+ `/ping`). Writing your own FastAPI routes named differently, using a
different port, or - as was originally (incorrectly) done here - writing a
custom script that reads a JSON payload from **stdin** and prints JSON to
**stdout**, will never be called by AgentCore Runtime. The container will sit
there listening for stdin that never comes (or an HTTP request on the wrong
port), while AgentCore Runtime's HTTP calls to `/invocations` go unanswered,
resulting in the console showing "Ready" (the container started and passed
its own startup checks) but invocations failing with 502/500 errors.

### What was actually needed: `bedrock_agentcore.runtime.BedrockAgentCoreApp`

The `bedrock-agentcore` PyPI package (already in `requirements.txt`) ships an
SDK class, `BedrockAgentCoreApp`, that implements this exact contract for
you - it's a thin Starlette/uvicorn application that already defines the
`/invocations`, `/ping`, and `/ws` routes correctly, handles AgentCore-specific
headers/session/tracing plumbing, and serves on port 8080 by default. You
plug your own logic in via an `@app.entrypoint`-decorated function and call
`app.run()`:

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload):
    # payload is the JSON dict AgentCore POSTed to /invocations
    result = my_existing_lambda_style_handler(payload, context=None)
    return result   # becomes the HTTP response body

app.run()  # starts the correct HTTP server on port 8080
```

A working reference example (not part of this codebase's own agents, but a
confirmed-correct pattern) is
`reference/plant_Advisor/plant_agent_runtime/plant_workflow_memory.py`.

### The actual fix applied to this codebase

All three agents (`orchestrator`, `health-agent`, `diagnosis-agent`) already
had Lambda-style handler functions (`lambda_handler(event, context)` in
`src/services/<agent>/handler.py`) reused from an earlier Lambda-based
design. Rather than rewriting those handlers, `agentcore_entrypoint.py` (the
shared Docker `CMD` script for all three images) was rewritten to bridge
them into a `BedrockAgentCoreApp`:

1. Dynamically imports the handler module passed as a CLI arg (e.g.
   `src.services.health_agent.handler`)
2. Locates its `lambda_handler` (or `handler`) function
3. Creates a `BedrockAgentCoreApp()` and registers an `@app.entrypoint`
   function that calls that Lambda-style handler with the AgentCore payload
4. Calls `app.run(port=8080)` to start serving

The previous (broken) version of this same file instead read a JSON payload
from `sys.stdin.read()` and `print()`ed a JSON response - i.e. it assumed
AgentCore Runtime would pipe input/output like a CLI subprocess, which it
does not.

**Dockerfile changes required alongside this** (all three
`Dockerfile.orchestrator` / `Dockerfile.health_agent` / `Dockerfile.diagnosis_agent`):
- `EXPOSE 8080` (was 8000/8001/8002, matching old local docker-compose ports -
  irrelevant/wrong for AgentCore Runtime, which always expects 8080)
- `CMD [..., "--port", "8080"]` (same reason)
- `HEALTHCHECK` changed to `curl -f http://localhost:8080/ping` (was a fake
  `python -c "print('ok')"` check that didn't verify anything real)

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

### Phase 4.1: Image Architecture Conversion ✅ COMPLETE

- [x] **Rebuild orchestrator image (arm64)**
  ```bash
  docker buildx build --platform linux/arm64 -f Dockerfile.orchestrator \
    -t 450410489798.dkr.ecr.us-east-1.amazonaws.com/orchestrator:latest --push .
  ```

- [x] **Rebuild health-agent image (arm64)**
  ```bash
  docker buildx build --platform linux/arm64 -f Dockerfile.health_agent \
    -t 450410489798.dkr.ecr.us-east-1.amazonaws.com/health-agent:latest --push .
  ```

- [x] **Rebuild diagnosis-agent image (arm64)**
  ```bash
  docker buildx build --platform linux/arm64 -f Dockerfile.diagnosis_agent \
    -t 450410489798.dkr.ecr.us-east-1.amazonaws.com/diagnosis-agent:latest --push .
  ```

- [x] Verify images in ECR (linux/arm64 platform confirmed via successful AgentCore Runtime invocation)

- [x] **Fix invocation protocol** (critical, found 2026-07-24): the original
  `agentcore_entrypoint.py` read a JSON payload from stdin and printed a JSON
  response to stdout. This does NOT match how AgentCore Runtime actually
  invokes containers - it POSTs to `/invocations` and GETs `/ping` on port
  8080 (see `bedrock_agentcore.runtime.BedrockAgentCoreApp`). Rewrote the
  entrypoint to wrap each Lambda-style `lambda_handler(event, context)` in a
  `BedrockAgentCoreApp` with `@app.entrypoint`, and updated all three
  Dockerfiles to `EXPOSE 8080` / run on port 8080 with a `/ping` health check.
  Reference working example: `reference/plant_Advisor/plant_agent_runtime/plant_workflow_memory.py`.

### Phase 4.2: Deploy to AgentCore Runtime ✅ COMPLETE

- [x] Run deployment script:
  ```bash
  python3 scripts/deploy_to_agentcore_boto3.py \
    --profile StandardAccess-450410489798 \
    --region us-east-1
  ```

- [x] Verify `agent_endpoints.json` created with valid runtime IDs

- [x] Test health checks on deployed agents (`GET /orchestrate/health`)

- [x] Verify S3 access works (added `SyntheticDataS3ReadAccess` inline policy
  to `AgentCoreExecutionRole`, scoped to `agentic-ai-poc-synthetic-data` bucket;
  added `SYNTHETIC_DATA_BUCKET`/`SYNTHETIC_DATA_PREFIX` env vars in the deploy script)

### Phase 4.3: Dashboard Integration ✅ COMPLETE

- [x] Dashboard's `ORCHESTRATOR_URL` already points at the API Gateway endpoint by default

- [x] Added `GET /orchestrate/devices`, `/devices/{id}`, `/devices/{id}/summary`,
  `/health` routes (see `DEPLOYED_API_ENDPOINTS.md`) so the dashboard's fleet
  summary/device list features work without a locally-run orchestrator

- [x] Test end-to-end workflow via dashboard - verified fleet summary, work
  orders, maintenance schedules, and spare parts all populate with real data

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

### Agent shows "Ready" but returns 502/500 on invocation

**Symptom:** AWS console shows the AgentCore Runtime as "Ready", but invoking
it returns a 502, or a 500 with `"No handler function found in ..."` or similar.

**Root cause:** AgentCore Runtime invokes containers over HTTP (`POST
/invocations`, `GET /ping` on port 8080). A container that reads from stdin
instead (or listens on the wrong port) will never receive the invocation.

**Solution:** Use the `bedrock_agentcore.runtime.BedrockAgentCoreApp` SDK
pattern in the entrypoint script (see `agentcore_entrypoint.py`), and make
sure the Dockerfile `EXPOSE`s and the process actually serves on port 8080.
Don't build a custom stdin-based invocation loop.

### Dashboard shows all devices "healthy" / DiagnosisAgent has 0 invocations

**Root cause:** `src/services/health_agent/handler.py` was blindly wrapping
every `current_reading` in `{'readings': current_reading}`. When the reading
comes from `DeviceLoader` (S3), it's already shaped as `{"readings": {...}}`,
so the blind wrap double-nested it, and `HealthAgent._detect_anomalies()`
silently found zero anomalies every time (no errors - it just skips
non-dict-shaped sensor entries).

**Solution:** Only wrap if `'readings'` isn't already a key in the incoming
`current_reading` (see the handler for the exact normalization logic).

### Dashboard shows 0 work orders / maintenance schedules / spare parts

**Root cause:** The orchestrator's `_analyze_device()` (in
`src/services/orchestrator/handler.py`) never copied `DiagnosisAgent`'s
`tool_results` field into its response, and separately looked for a
`mcp_tools_used` key that `DiagnosisAgent` never actually returns. The MCP
tool calls (create-work-order, etc.) were succeeding the whole time - the
data was just being dropped during response aggregation.

**Solution:** Forward `tool_results` as-is, and derive `mcp_tools_used` from
`list(tool_results.keys())`.

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
3. ✅ Fix AgentCore invocation protocol (BedrockAgentCoreApp on port 8080)
4. ✅ Integrate AgentCore endpoints in dashboard (added GET /devices, /health routes)
5. ✅ Fix HealthAgent double-wrap and orchestrator tool_results forwarding bugs
6. ✅ Test end-to-end workflow via dashboard (fleet summary, work orders,
   maintenance schedules, spare parts all confirmed showing real data)
7. ⏳ Document AgentCore Gateway integration (Phase 5)
