# AgentCore Runtime Migration - Implementation Plan

**Branch**: `migration/agentcore`  
**Date**: July 9, 2026  
**Goal**: Migrate agents from local Docker to AWS Bedrock AgentCore Runtime while maintaining MCP tool connectivity

---

## Executive Summary

```
BEFORE (Local Docker):
  Dashboard (8080) → Orchestrator (8000) → HealthAgent (8001), DiagnosisAgent (8002)
                                              ↓
                                         GatewayClient → AgentCore Gateway → MCP Tools

AFTER (AWS AgentCore Runtime):
  Dashboard → API Gateway (HTTPS) → Lambda Wrapper → AgentCore Orchestrator Runtime
                                                         ↓
                                                    HealthAgent Runtime
                                                    DiagnosisAgent Runtime
                                                         ↓
                                                    GatewayClient (unchanged)
                                                         ↓
                                                    AgentCore Gateway → MCP Tools
  
  Data: Local JSON files → S3 bucket
```

---

## Prerequisites (Already Done ✅)

✅ AWS Account with AgentCore access  
✅ Cognito User Pool + App Client (existing)  
✅ AgentCore Gateway deployed (`gateway_info.json` exists)  
✅ GatewayClient with OAuth2 (working locally)  
✅ MCP tools registered (spare-parts in S3, others on Lambda/AppRunner)  
✅ Docker images built locally (Dockerfile.health_agent, Dockerfile.diagnosis_agent, Dockerfile.orchestrator)  
✅ `.agentcore.env` configured with AWS SSO profile

---

## Phase 1: Prepare for AgentCore Deployment

### Step 1.1: Understand AgentCore Runtime Deployment

**What**: AWS Bedrock AgentCore Runtime is a managed service where you:
1. Push Docker image to ECR
2. Create agent definition specifying image, resources, environment variables
3. AgentCore manages scaling, networking, health checks automatically

**Why**: Replaces local docker-compose containers with managed service

**Difference from Lambda**:
- Lambda: Stateless functions, 15-min timeout, ~3s cold start
- AgentCore Runtime: Always-on agents, longer operations, auto-restart

**Tool to use**: `bedrock-agentcore-starter-toolkit` (already installed in requirements.txt)

---

### Step 1.2: Organize Synthetic Data Migration

**Current state**:
```
/data/generated/
  ├── compressor-001.json
  ├── compressor-002.json
  ├── motor-001.json
  ├── pump-002.json
  └── ... (17 device files)

/data/mcp-tools/
  └── spare_parts_inventory.json (already in S3)
```

**Target state**:
```
S3 Bucket: agentic-ai-poc-synthetic-data/
  ├── devices/
  │   ├── compressor-001.json
  │   ├── compressor-002.json
  │   ├── motor-001.json
  │   ├── pump-002.json
  │   └── ... (17 device files)
  └── mcp-tools/
      └── spare_parts_inventory.json (already here)
```

**Why**:
- Agents on AWS need cloud storage access
- S3 is standard for data lake
- Allows concurrent agent access to same data
- No local file system in serverless

**Steps**:
1. Create S3 bucket: `agentic-ai-poc-synthetic-data`
2. Copy `/data/generated/*` to `s3://agentic-ai-poc-synthetic-data/devices/`
3. Verify spare parts already in S3
4. Update agent code: Load data from S3 instead of local files
5. Update `.agentcore.env` with S3 bucket name

---

### Step 1.3: State Management Strategy

**What state do agents need to persist?**

| State | Currently | Need to Persist? | New Location |
|-------|-----------|------------------|--------------|
| Device cache | In-memory dict | Maybe | DynamoDB or S3 |
| Execution history | In-memory list | No | CloudWatch logs |
| MCP tool results | In-memory | No | Return in response |
| Token cache | In-memory (GatewayClient) | No | GatewayClient handles |

**Recommendation for Phase 1 (MVP)**:
- **No persistent state** - agents are stateless
- Each invocation starts fresh
- Results returned immediately to caller
- If needed later: Add DynamoDB table `agentcore-agent-state`

**Why stateless for MVP**:
- Simpler deployment
- Agents stay independent and scalable
- State can be added later without architecture changes
- Dashboard maintains session state, not agents

---

## Phase 2: Prepare Agent Docker Images for AgentCore

### Step 2.1: Verify Current Dockerfiles

**What**: Check existing Dockerfiles work for AgentCore

**Current files**:
- `Dockerfile.health_agent`
- `Dockerfile.diagnosis_agent`
- `Dockerfile.orchestrator`

**Required for AgentCore**:
- Base image: Python 3.11 slim
- Expose port (8001, 8002, 8000)
- Install all dependencies
- Set ENTRYPOINT to start FastAPI server
- Include healthcheck endpoint

**Steps**:
1. Verify each Dockerfile has healthcheck endpoint (`GET /health`)
2. Ensure all environment variables can be passed (no hardcoded values)
3. Test locally: `docker build -f Dockerfile.health_agent -t health-agent:v1 .`
4. Test locally: `docker run -p 8001:8001 --env-file .agentcore.env health-agent:v1`
5. Verify agent starts and can call AgentCore Gateway

**Note**: Dockerfiles should NOT have `docker-compose` specific directives

---

### Step 2.2: Update Agent Code for S3 Data Loading

**What**: Replace local file reads with S3 reads

**Example - Before (local)**:
```python
# In health_agent or orchestrator
with open('data/generated/device-id.json') as f:
    device_data = json.load(f)
```

**Example - After (S3)**:
```python
import boto3

s3_client = boto3.client('s3')
response = s3_client.get_object(
    Bucket=os.getenv('SYNTHETIC_DATA_BUCKET'),
    Key=f"devices/{device_id}.json"
)
device_data = json.loads(response['Body'].read())
```

**Where to update**:
- `src/utils/device_loader.py` (if exists)
- `src/services/orchestrator/app.py` (device data loading)
- Any other place that reads from `/data/generated/`

**Steps**:
1. Identify all file read operations in agents
2. Create utility: `S3DataLoader` class
3. Replace file reads with S3 calls
4. Add retry logic for S3 failures
5. Cache loaded data in-memory (first 5 minutes of runtime only)

---

### Step 2.3: Update Environment Variables

**Current `.agentcore.env` contains**:
```
AWS_REGION=us-east-1
COGNITO_CLIENT_ID=...
COGNITO_CLIENT_SECRET=...
GATEWAY_URL=...
```

**Add for AgentCore**:
```
# S3 for synthetic data
SYNTHETIC_DATA_BUCKET=agentic-ai-poc-synthetic-data
SYNTHETIC_DATA_PREFIX=devices/

# Agent identification (for orchestrator to call them)
HEALTH_AGENT_ENDPOINT=<will be assigned by AgentCore>
DIAGNOSIS_AGENT_ENDPOINT=<will be assigned by AgentCore>
```

**Why**: Agents need to know where to find data and how to call each other

---

## Phase 3: Push Docker Images to AWS ECR ✅ (COMPLETED)

### Step 3.1: Create ECR Repositories ✅

**Status**: Repositories created
- `orchestrator` ✅
- `health-agent` ✅
- `diagnosis-agent` ✅

### Step 3.2: Configure Docker for Corporate Proxy SSL ✅

**Problem**: Docker daemon behind corporate firewall cannot verify ECR TLS certificates

**Solution**: Configure Docker daemon to trust certificate bundle

```bash
# 1. Create Docker CA directory for ECR registry
sudo mkdir -p /etc/docker/certs.d/450410489798.dkr.ecr.us-east-1.amazonaws.com

# 2. Copy certificate bundle to Docker's CA directory
sudo cp config/minimal_certificate_bundle.pem \
  /etc/docker/certs.d/450410489798.dkr.ecr.us-east-1.amazonaws.com/ca.crt

# 3. Restart Docker daemon
sudo systemctl restart docker
```

**Why**: Docker daemon (not just apps) needs to trust proxy certificates when pushing to ECR over HTTPS.

**Reference**: See [Docker & ECR Certificate Configuration](AGENTCORE_MIGRATION_PHASE2_SSL_CERTIFICATE_SOLUTION.md#docker--ecr-certificate-configuration) in SSL solution document

### Step 3.3: Authenticate Docker to ECR ✅

```bash
# Use AWS SSO profile for authentication
aws ecr get-login-password --region us-east-1 --profile StandardAccess-450410489798 | \
  docker login --username AWS --password-stdin 450410489798.dkr.ecr.us-east-1.amazonaws.com
```

**Result**: `Login Succeeded` message confirms Docker can now access ECR

### Step 3.4: Tag Docker Images for ECR ✅

```bash
# Orchestrator
docker tag agentic_ai_poc_phase3_1-orchestrator:latest \
  450410489798.dkr.ecr.us-east-1.amazonaws.com/orchestrator:latest

# Health Agent
docker tag agentic_ai_poc_phase3_1-health-agent:latest \
  450410489798.dkr.ecr.us-east-1.amazonaws.com/health-agent:latest

# Diagnosis Agent
docker tag agentic_ai_poc_phase3_1-diagnosis-agent:latest \
  450410489798.dkr.ecr.us-east-1.amazonaws.com/diagnosis-agent:latest
```

### Step 3.5: Push Images to ECR ✅

```bash
# Push Orchestrator
docker push 450410489798.dkr.ecr.us-east-1.amazonaws.com/orchestrator:latest

# Push Health Agent
docker push 450410489798.dkr.ecr.us-east-1.amazonaws.com/health-agent:latest

# Push Diagnosis Agent
docker push 450410489798.dkr.ecr.us-east-1.amazonaws.com/diagnosis-agent:latest
```

**Verify**: Check AWS ECR console → see 3 images with green checkmark (scan passed)

---

## Phase 4: Deploy Agents to AgentCore Runtime

### Step 4.1: Create Agent Definitions

**What**: Tell AgentCore how to run each agent

**For each agent, create definition** (can be JSON or created via script):

```json
{
  "agentName": "HealthAgent",
  "version": "1.0",
  "description": "Equipment health analysis agent",
  "containerImage": "450410489798.dkr.ecr.us-east-1.amazonaws.com/health-agent:latest",
  "resources": {
    "cpu": 256,      // 0.25 vCPU
    "memory": 512,   // 512 MB
    "timeout": 30    // seconds
  },
  "scaling": {
    "minInstances": 0,   // On-demand (scale to 0 when idle)
    "maxInstances": 10   // Scale up to 10 under load
  },
  "environment": {
    "PYTHONUNBUFFERED": "1",
    "LOG_LEVEL": "INFO",
    "AGENT_NAME": "HealthAgent",
    "AGENT_PORT": "8001",
    // Copy from .agentcore.env
    "AWS_REGION": "us-east-1",
    "COGNITO_CLIENT_ID": "...",
    "COGNITO_CLIENT_SECRET": "...",
    "GATEWAY_URL": "https://...",
    "SYNTHETIC_DATA_BUCKET": "agentic-ai-poc-synthetic-data"
  },
  "healthCheckEndpoint": "http://localhost:8001/health"
}
```

**Do this for**:
- HealthAgent (smaller: 256 CPU, 512 MB, timeout 30s)
- DiagnosisAgent (larger: 512 CPU, 1GB, timeout 60s)
- Orchestrator (medium: 256 CPU, 512 MB, timeout 60s)

---

### Step 4.2: Deploy Agents via bedrock-agentcore-starter-toolkit

**What**: Use toolkit to deploy agents to AgentCore

**Create script**: `scripts/deploy_agents_to_agentcore.py`

**Pseudocode**:
```python
from bedrock_agentcore_starter_toolkit.operations.agent.client import AgentClient

toolkit = AgentClient(region="us-east-1", profile="<your-sso-profile>")

# Deploy each agent
for agent_def in [health_agent_def, diagnosis_agent_def, orchestrator_def]:
    agent = toolkit.create_agent(agent_def)
    print(f"Deployed {agent['agentName']}")
    print(f"Endpoint: {agent['endpoint']}")  # Save this!
```

**Save agent endpoints** to file (`agent_endpoints.json`):
```json
{
  "HealthAgent": "https://...",
  "DiagnosisAgent": "https://...",
  "Orchestrator": "https://..."
}
```

---

### Step 4.3: Verify Agent Deployment

**What**: Test agents are running and accessible

**Steps**:
1. Call each agent's health endpoint via curl:
   ```bash
   curl https://<health-agent-endpoint>/health
   # Should return: {"status": "healthy"}
   ```

2. Check CloudWatch logs for each agent
3. Verify agents can reach AgentCore Gateway (check logs for token acquisition)

---

## Phase 5: Create Lambda Wrapper for Dashboard Integration

### Step 5.1: Design Lambda Handler

**What**: Lambda function that receives Dashboard requests and invokes AgentCore Orchestrator

**Flow**:
```
Dashboard → API Gateway (HTTPS POST /orchestrate)
           ↓
        Lambda Handler
           ├─ Validate request
           ├─ Call AgentCore Orchestrator endpoint
           ├─ Return execution ID (for polling)
           └─ Return results (if ready)
```

**Handler pseudocode**:
```python
import json
import requests
import os

ORCHESTRATOR_ENDPOINT = os.getenv("ORCHESTRATOR_ENDPOINT")

def lambda_handler(event, context):
    """Receive request from API Gateway, invoke AgentCore Orchestrator"""
    
    try:
        # Parse request
        body = json.loads(event['body'])
        device_id = body['device_id']
        equipment_type = body['equipment_type']
        current_reading = body['current_reading']
        
        # Invoke orchestrator agent
        response = requests.post(
            f"{ORCHESTRATOR_ENDPOINT}/process",
            json={
                "device_id": device_id,
                "equipment_type": equipment_type,
                "current_reading": current_reading
            },
            timeout=60
        )
        
        if response.status_code != 200:
            return {
                'statusCode': 503,
                'body': json.dumps({'error': 'Orchestrator unavailable'})
            }
        
        result = response.json()
        
        return {
            'statusCode': 200,
            'body': json.dumps(result),
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
```

**Deploy via SAM or boto3 Lambda client**

---

### Step 5.2: Create API Gateway

**What**: HTTP endpoint for Dashboard and curl

**Endpoint**: `https://api.yourdomain.com/v1/orchestrate` (POST)

**Request schema**:
```json
{
  "device_id": "pump-002",
  "equipment_type": "PUMP",
  "current_reading": {
    "readings": {
      "temperature": {"value": 85, "unit": "C", "normal_range": [20, 95]},
      "vibration": {"value": 4.2, "unit": "mm/s", "normal_range": [0, 3]},
      "pressure": {"value": 2.8, "unit": "bar", "normal_range": [2.0, 3.0]}
    }
  }
}
```

**Response schema**:
```json
{
  "device_id": "pump-002",
  "health_status": "warning",
  "diagnosis": "Pump pressure instability detected",
  "confidence": 0.92,
  "action": "SCHEDULE_MAINTENANCE",
  "tool_results": {
    "get-spare-parts": [...],
    "schedule-maintenance": {...}
  }
}
```

**Steps**:
1. Create REST API in API Gateway console
2. Create POST method on `/v1/orchestrate`
3. Attach Lambda as target
4. Deploy to stage: `prod`
5. Enable CORS (for dashboard browser)

---

## Phase 6: Update Dashboard for API Gateway Integration

### Step 6.1: Update API Endpoint

**Current**: `http://localhost:8000/devices` (local orchestrator)

**New**: `https://api.yourdomain.com/v1/orchestrate` (API Gateway)

**Changes**:
```javascript
// Before
const response = await fetch('http://localhost:8000/devices/process', {
  method: 'POST',
  body: JSON.stringify(data)
});

// After
const response = await fetch('https://api.yourdomain.com/v1/orchestrate', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer <api-key>'  // If using API key auth
  },
  body: JSON.stringify(data)
});
```

---

## Phase 7: Verify End-to-End Integration

### Step 7.1: Test via curl

```bash
# Test 1: Health check
curl https://api.yourdomain.com/v1/health

# Test 2: Process device
curl -X POST https://api.yourdomain.com/v1/orchestrate \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "pump-002",
    "equipment_type": "PUMP",
    "current_reading": {
      "readings": {
        "temperature": {"value": 90, "unit": "C", "normal_range": [20, 95]},
        "vibration": {"value": 5.0, "unit": "mm/s", "normal_range": [0, 3]}
      }
    }
  }'

# Expected response
{
  "device_id": "pump-002",
  "health_status": "warning",
  "diagnosis": "..."
}
```

### Step 7.2: Test via Dashboard

1. Update dashboard API endpoint to API Gateway URL
2. Load dashboard in browser
3. Verify data flows: Dashboard → API Gateway → Lambda → AgentCore Orchestrator
4. Check CloudWatch logs for errors

### Step 7.3: Test agent-to-agent communication

**Verify**:
- Orchestrator calls HealthAgent via endpoint
- HealthAgent calls DiagnosisAgent via endpoint
- All agents can reach AgentCore Gateway (tokens acquired successfully)
- MCP tools called and results returned

---

## Implementation Timeline

| Phase | Tasks | Duration | Tools |
|-------|-------|----------|-------|
| 1 | Understand AgentCore, plan data migration, state mgmt | 2 hours | None |
| 2 | Update Dockerfiles, agent code (S3 loading), env vars | 3 hours | VS Code |
| 3 | Create ECR repos, build/push images | 1 hour | Docker, AWS CLI |
| 4 | Deploy agents to AgentCore via toolkit | 2 hours | bedrock-agentcore-starter-toolkit |
| 5 | Create Lambda wrapper, API Gateway | 2 hours | AWS SAM or boto3 |
| 6 | Update dashboard endpoint | 1 hour | VS Code |
| 7 | End-to-end testing via curl and dashboard | 3 hours | curl, browser |
| **Total** | | **14 hours** | |

---

## Data Migration Checklist

- [x] Create S3 bucket: `agentic-ai-poc-synthetic-data` ✅ (July 10)
- [x] Upload `/data/generated/*.json` to `s3://agentic-ai-poc-synthetic-data/devices/` ✅ (17 files)
- [x] Verify spare parts already in S3 ✅ (existing in `agentic-ai-poc-3-1-mcp-tools`)
- [x] Update agent code to load from S3 (not local files) ✅ (July 10)
- [x] Update `.agentcore.env` with `SYNTHETIC_DATA_BUCKET` ✅ (July 10)
- [x] Test local: agents can read from S3 ✅ (17 devices loaded successfully)

**Phase 2.1 Complete**: DeviceLoader now reads from S3 instead of local files

---

## SSL Certificate Configuration (Corporate Proxy) ✅

**Status**: ✅ RESOLVED & AUTOMATED

- [x] Created certificate bundle: `config/minimal_certificate_bundle.pem` ✅ (228KB, 152 certs)
- [x] Updated `.agentcore.env` with `AWS_CA_BUNDLE` setting ✅ (auto-loads at app startup)
- [x] Updated `src/services/orchestrator/app.py` to load `.agentcore.env` ✅ (no manual export needed)
- [x] Tested: DeviceLoader works without manual environment export ✅
- [x] Verified: Graceful fallback for AgentCore Runtime (no cert bundle needed in AWS) ✅

**How it works locally**: 
- App startup loads `.agentcore.env` using python-dotenv
- `AWS_CA_BUNDLE=config/minimal_certificate_bundle.pem` is set automatically
- boto3 uses certificate bundle for SSL verification
- S3 access works through corporate proxy

**How it works in AgentCore Runtime**:
- `.agentcore.env` doesn't exist → AWS_CA_BUNDLE not set
- boto3 uses AWS system cert store (complete in AWS environment)
- Works automatically without any configuration

**No code changes needed** - works in both environments

See: [AGENTCORE_MIGRATION_PHASE2_SSL_CERTIFICATE_SOLUTION.md](AGENTCORE_MIGRATION_PHASE2_SSL_CERTIFICATE_SOLUTION.md)

---

## AgentCore Runtime Deployment Checklist

- [x] Verify Dockerfiles have healthcheck endpoints ✅
- [x] Build Docker images locally ✅
- [ ] Push images to ECR — Phase 3
- [ ] Create agent definitions (JSON) — Phase 4
- [ ] Deploy via bedrock-agentcore-starter-toolkit — Phase 4
- [ ] Save agent endpoints to `agent_endpoints.json` — Phase 4
- [ ] Verify agents healthy: `curl <agent-endpoint>/health` — Phase 4

**Status**: Ready for Phase 2.1 (Update DeviceLoader for S3)

---

## API Gateway + Lambda Integration Checklist

- [ ] Create Lambda function with handler
- [ ] Create API Gateway REST API
- [ ] Create POST `/v1/orchestrate` endpoint
- [ ] Attach Lambda to API Gateway
- [ ] Deploy to `prod` stage
- [ ] Test via curl
- [ ] Update dashboard endpoint

---

## Key Differences from Local Deployment

| Aspect | Local Docker | AgentCore Runtime |
|--------|--------------|------------------|
| Agent startup | Manual: `docker-compose up` | Automatic: AgentCore manages |
| Data location | Local `/data/generated/` | S3 bucket |
| Agent endpoints | `localhost:8001`, `localhost:8002` | CloudFormation outputs |
| Orchestrator access | Direct `localhost:8000` | Via API Gateway + Lambda |
| State persistence | In-memory dict | None (stateless MVP) |
| Scaling | Manual (container replicas) | Automatic (min/max instances) |
| Monitoring | Docker logs | CloudWatch logs |
| Authentication | None (local) | Cognito OAuth2 (via GatewayClient) |

---

## What Stays the Same

✅ **GatewayClient** - No changes needed (OAuth2, token refresh)
✅ **AgentCore Gateway** - Already deployed, no changes
✅ **MCP tools** - No changes (Lambda/AppRunner)
✅ **Cognito setup** - No changes
✅ **Agent business logic** - Minimal changes (just add S3 data loading)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Agents can't reach S3 | Critical | Add S3 IAM permissions to agent role |
| Lambda timeout (60s) | High | Increase to 120s if needed |
| AgentCore deployment fails | High | Test Docker images locally first |
| Token refresh fails | Medium | GatewayClient already has retry logic |
| Cold start slow | Low | Keep agents always-on (minInstances: 1) |

---

## Success Criteria

- ✅ All 3 agents deployed to AgentCore Runtime
- ✅ Agents can read synthetic data from S3
- ✅ Agents can call MCP tools via AgentCore Gateway
- ✅ API Gateway responds to curl requests in < 5 seconds
- ✅ Dashboard receives results correctly
- ✅ CloudWatch shows all invocations logged
- ✅ No changes to GatewayClient or agent business logic

---

## Next Steps

1. **Prepare S3**: Create bucket, upload synthetic data
2. **Update agent code**: Add S3 data loading (utility class)
3. **Build & push images**: Verify in ECR
4. **Deploy agents**: Use bedrock-agentcore-starter-toolkit
5. **Create Lambda + API Gateway**: Test with curl first
6. **Update dashboard**: Point to new API endpoint
7. **End-to-end testing**: Verify everything works

**Ready to start with Phase 1 & 2?**
