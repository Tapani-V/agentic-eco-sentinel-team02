# Deployed API Endpoints

**Status**: ✅ Deployed  
**Date**: 2026-07-24  
**Deployment Method**: boto3 (Lambda + API Gateway)

---

## 🌐 Active Endpoints

### Orchestrator Lambda + API Gateway

**Endpoint URL** (Use this for Dashboard):
```
https://mn6y8y0u26.execute-api.us-east-1.amazonaws.com/prod/orchestrate
```

**Lambda Function Name**:
```
orchestrator-handler-450410489798
```

**API Gateway ID**:
```
mn6y8y0u26
```

**Stage**:
```
prod
```

**Region**:
```
us-east-1
```

---

## 📋 Test Command

```bash
curl -X POST https://mn6y8y0u26.execute-api.us-east-1.amazonaws.com/prod/orchestrate \
  -H 'Content-Type: application/json' \
  -d '{"device_id":"motor-004","equipment_type":"MOTOR","current_reading":{}}'
```

---

## 🌐 Additional GET Routes (added 2026-07-24)

The dashboard needs more than single-device POST analysis - it needs to list
all fleet devices and fetch/summarize individual devices without supplying a
reading. These routes were added as GET children of `/orchestrate` (wired to
the same Lambda + same OrchestratorAgent runtime, via `scripts/add_devices_api_routes.py`):

```bash
# List all device IDs
curl https://mn6y8y0u26.execute-api.us-east-1.amazonaws.com/prod/orchestrate/devices

# Fetch latest reading for a device and run the full analysis workflow
curl https://mn6y8y0u26.execute-api.us-east-1.amazonaws.com/prod/orchestrate/devices/motor-004

# Device summary/history stats (no live analysis)
curl https://mn6y8y0u26.execute-api.us-east-1.amazonaws.com/prod/orchestrate/devices/motor-004/summary

# Orchestrator health check
curl https://mn6y8y0u26.execute-api.us-east-1.amazonaws.com/prod/orchestrate/health
```

How it works: the Lambda (`functions/lambda_orchestrator_handler.py`) stays a
thin bridge - it translates the HTTP method/path into an `action` payload
(`list_devices` | `get_device` | `get_device_summary` | `health`) and forwards
it to the OrchestratorAgent running in AgentCore Runtime. The orchestrator
agent itself (`src/services/orchestrator/handler.py`) owns the actual business
logic - it reads device sensor data directly from the
`agentic-ai-poc-synthetic-data` S3 bucket via `DeviceLoader` (same class used
by the original local FastAPI orchestrator), then for `get_device` runs the
same HealthAgent → DiagnosisAgent workflow used by `POST /orchestrate`.

This required:
- An inline S3 read-only policy (`SyntheticDataS3ReadAccess`) added to
  `AgentCoreExecutionRole` (scoped to the `agentic-ai-poc-synthetic-data` bucket)
- `SYNTHETIC_DATA_BUCKET` / `SYNTHETIC_DATA_PREFIX` env vars added to the
  orchestrator's AgentCore deployment config
  (`scripts/deploy_to_agentcore_boto3.py`)

---

## 🔧 Next Steps

### 1. Update Dashboard Configuration

Edit `src/dashboard/config.py` line 49:

**Change from**:
```python
ORCHESTRATOR_URL: str = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000")
```

**Change to**:
```python
ORCHESTRATOR_URL: str = os.getenv("ORCHESTRATOR_URL", "https://mn6y8y0u26.execute-api.us-east-1.amazonaws.com/prod/orchestrate")
```

### 2. Or Set Environment Variable

```bash
export ORCHESTRATOR_URL="https://mn6y8y0u26.execute-api.us-east-1.amazonaws.com/prod/orchestrate"
```

### 3. Test Dashboard End-to-End

```bash
# Start dashboard
python3 -m uvicorn main:app --host 0.0.0.0 --port 8080

# In another terminal, test endpoints
curl http://localhost:8080/api/fleet-summary
curl http://localhost:8080/api/work-orders
```

---

## 📊 Architecture Flow

```
Dashboard (http://localhost:8080)
    ↓ (uses ORCHESTRATOR_URL)
    ↓
API Gateway Endpoint
    https://mn6y8y0u26.execute-api.us-east-1.amazonaws.com/prod/orchestrate
    ↓
Lambda Function
    orchestrator-handler-450410489798
    ↓
AgentCore Orchestrator Runtime
    ↓
HealthAgent / DiagnosisAgent
    ↓
MCP Tools
```

---

## 🔐 Security Notes

- ✅ HTTPS (encrypted)
- ✅ CORS enabled (allows cross-origin from Dashboard)
- ✅ OAuth2 authentication (Cognito) - used by DiagnosisAgent to call MCP Gateway tools
- ✅ No API key required on API Gateway (uses service credentials internally)
- ✅ Exposed routes: `POST /orchestrate`, `GET /orchestrate/health`,
  `GET /orchestrate/devices`, `GET /orchestrate/devices/{device_id}`,
  `GET /orchestrate/devices/{device_id}/summary`

---

## 📝 Deployment Details

**Method**: boto3 (direct AWS API calls)  
**Script**: `scripts/deploy_lambda_api_gateway_boto3.py`  
**Handler**: `functions/lambda_orchestrator_handler.py`  
**Config**: `.agentcore.env` (Cognito credentials)  

**Lambda Configuration**:
- Runtime: Python 3.10
- Memory: 512 MB
- Timeout: 120 seconds
- Role: `agentic-ai-lambda-execution-role`

**API Gateway Configuration**:
- Type: REST API
- Endpoint Type: Regional
- Methods: POST/OPTIONS on `/orchestrate`; GET/OPTIONS on
  `/orchestrate/health`, `/orchestrate/devices`, `/orchestrate/devices/{device_id}`,
  `/orchestrate/devices/{device_id}/summary` (added via `scripts/add_devices_api_routes.py`)
- Stage: prod

**AgentCore Runtime Images**: all three (`orchestrator`, `health-agent`,
`diagnosis-agent`) must be built with `docker buildx build --platform linux/arm64`
(NOT plain `docker build`) and must use the `bedrock_agentcore.runtime.BedrockAgentCoreApp`
SDK pattern in `agentcore_entrypoint.py` (HTTP `/invocations` + `/ping` on port
8080) - a stdin-based custom entry point does NOT work with AgentCore Runtime's
actual invocation protocol.

---

## ✅ Verification Checklist

- [x] Lambda function created
- [x] API Gateway created
- [x] /orchestrate endpoint wired
- [x] CORS headers configured
- [x] Endpoint accessible
- [x] Dashboard updated with new endpoint
- [x] Dashboard tested end-to-end
- [x] CloudWatch logs verified
- [x] AgentCore images rebuilt for linux/arm64 via docker buildx
- [x] agentcore_entrypoint.py fixed to use BedrockAgentCoreApp (HTTP protocol,
      not stdin) - see `docs/PHASE_4_AGENTCORE_DEPLOYMENT.md` for details
- [x] GET /orchestrate/devices, /devices/{id}, /devices/{id}/summary, /health
      routes added and wired to OrchestratorAgent action dispatch
- [x] HealthAgent double-wrapping bug fixed (was causing every device to
      always report "healthy" with zero anomalies)
- [x] Orchestrator's tool_results/mcp_tools_used forwarding bug fixed (was
      causing dashboard work orders/maintenance/spare parts to always show 0)

---

## 🚀 Deployment History

| Date | Endpoint | Status | Notes |
|------|----------|--------|-------|
| 2026-07-24 | https://mn6y8y0u26.execute-api.us-east-1.amazonaws.com/prod/orchestrate | ✅ Active | Initial deployment with boto3 |
| 2026-07-24 | (same, ARM64 rebuild) | ✅ Active | Rebuilt orchestrator/health-agent/diagnosis-agent as linux/arm64 via docker buildx (previous images were amd64, incompatible with AgentCore Runtime) |
| 2026-07-24 | (same, entrypoint fix) | ✅ Active | Rewrote agentcore_entrypoint.py to use BedrockAgentCoreApp HTTP protocol instead of a stdin-based script that AgentCore Runtime could never actually invoke |
| 2026-07-24 | /orchestrate/devices, /devices/{id}, /devices/{id}/summary, /health | ✅ Active | Added GET routes so dashboard can list/fetch/summarize fleet devices without a locally-run orchestrator |
| 2026-07-24 | (health-agent fix) | ✅ Active | Fixed double-wrapped current_reading bug causing HealthAgent to always report "healthy"/0 anomalies |
| 2026-07-24 | (orchestrator fix) | ✅ Active | Fixed missing tool_results / mismatched mcp_tools_used fields so dashboard's work orders/maintenance/spare parts counts reflect real MCP tool call results |

