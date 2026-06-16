# Week 2 Day 5-7: Step-by-Step Implementation

**Goal:** Build production-grade 3-container architecture with Orchestrator + Agent services.

**Architecture:**
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Local (Docker Compose)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 1. ORCHESTRATOR (port 8000)                                          │   │
│  │    FastAPI + LangGraph                                              │   │
│  │    POST /process                                                    │   │
│  │    Calls agent services via HTTP                                    │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│              ┌──────────────────┴──────────────────┐                       │
│              ▼                                     ▼                       │
│  ┌─────────────────────────┐         ┌─────────────────────────┐          │
│  │ 2. HEALTH AGENT (:8001) │         │ 3. DIAGNOSIS AGENT      │          │
│  │                         │         │    (:8002)              │          │
│  │    POST /analyze        │         │    POST /diagnose       │          │
│  │    └── GatewayClient    │         │    └── GatewayClient    │          │
│  │        └── schedule_    │         │        └── get_spare_   │          │
│  │           maintenance   │         │           parts         │          │
│  │                         │         │        └── create_work_ │          │
│  │                         │         │           order         │          │
│  └─────────────────────────┘         └─────────────────────────┘          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                          AgentCore Gateway → MCP Tools (AWS)
```

**Prerequisite:** Day 1-4 complete (gateway + tools working, `test_agentcore_gateway_starter.py` passes).

---

## Directory Structure

```
project-root/
│
├── src/                              # SHARED CODE (copied into containers)
│   ├── agents/                       # Agent LOGIC (updated for Week 2 Day 5-7)
│   │   ├── base_agent.py
│   │   ├── health_agent.py           # ✅ Pure classification, NO tools
│   │   └── diagnosis_agent.py        # ✅ 4-step process with tool execution
│   │
│   ├── graph/                        # LangGraph workflow
│   │   └── workflow.py               # ⚠️ Phase 2 version (for reference)
│   │
│   ├── gateway/                      # GatewayClient
│   │   ├── __init__.py
│   │   ├── client.py
│   │   └── exceptions.py
│   │
│   └── services/                     # CONTAINER ENTRY POINTS (Week 2 Day 5-7)
│       ├── orchestrator/             # Container 1 (Port 8000)
│       │   ├── app.py                # ✅ LangGraph 4-node workflow
│       │   ├── Dockerfile
│       │   └── requirements.txt
│       │
│       ├── health_agent/             # Container 2 (Port 8001)
│       │   ├── app.py                # ✅ FastAPI wrapper
│       │   ├── Dockerfile
│       │   └── requirements.txt
│       │
│       └── diagnosis_agent/          # Container 3 (Port 8002)
│           ├── app.py                # ✅ FastAPI wrapper with MCP tools
│           ├── Dockerfile
│           └── requirements.txt
│
├── docker-compose.yml
└── .agentcore.env                    # Secrets (gitignored)
```

---

## Step 1: Create GatewayClient Module ✅ DONE

**What:** A shared Python module that handles Cognito tokens and gateway calls.

**Files created:**
```
src/gateway/
├── __init__.py
├── client.py
└── exceptions.py
```

**Checkpoint:** 
```bash
python -c "from src.gateway.client import GatewayClient; print('Import OK')"
```

---

## Step 2: Test GatewayClient Standalone

**What:** Verify GatewayClient can get token and call tools without any agent.

**Test:**
```bash
python -c "
from src.gateway.client import GatewayClient
g = GatewayClient()
tools = g.list_tools()
print(f'Found {len(tools)} tools')
for t in tools:
    print(f'  - {t[\"name\"]}')
"
```

**Expected:** Lists 3 tools (get-spare-parts, schedule-maintenance, create-work-order).

**Checkpoint:** Call one tool:
```bash
python -c "
from src.gateway.client import GatewayClient
g = GatewayClient()
result = g.call_tool('get_spare_parts', {'part_type': 'bearing'})
print(result)
"
```

---

## Step 3: Create Agent Services (FastAPI)

**What:** Create FastAPI wrapper for each agent.

**Files to create:**
```
services/
├── health_agent/
│   ├── app.py              # FastAPI app with POST /analyze
│   ├── Dockerfile
│   └── requirements.txt
└── diagnosis_agent/
    ├── app.py              # FastAPI app with POST /diagnose
    ├── Dockerfile
    └── requirements.txt
```

**Each agent service:**
- FastAPI app with single POST endpoint
- Imports GatewayClient for tool calls
- Returns JSON response

**Checkpoint:** Run one agent standalone:
```bash
cd services/diagnosis_agent
uvicorn app:app --port 8002 --reload
# Test: curl -X POST http://localhost:8002/diagnose -H "Content-Type: application/json" -d '{"device_id": "device-001", ...}'
```

---

## Step 4: Create Orchestrator Service (LangGraph)

**What:** Orchestrator that runs LangGraph workflow and calls agent services via HTTP.

**Files to create:**
```
services/
└── orchestrator/
    ├── app.py              # FastAPI app with POST /process
    ├── workflow.py         # LangGraph workflow definition
    ├── Dockerfile
    └── requirements.txt
```

**Orchestrator:**
- Receives device data via POST /process
- Runs LangGraph workflow
- Calls agent services via HTTP (not direct imports)
- Aggregates results and returns

**Checkpoint:** Run orchestrator with mock agents:
```bash
cd services/orchestrator
uvicorn app:app --port 8000 --reload
```

---

## Step 5: Create Docker Compose

**What:** Run all 3 services together locally.

**File to create:**
```
docker-compose.yml
```

**Services:**
- `orchestrator` (port 8000)
- `health-agent` (port 8001)
- `diagnosis-agent` (port 8002)

**Checkpoint:**
```bash
docker-compose up --build
# Test: curl -X POST http://localhost:8000/process -H "Content-Type: application/json" -d @data/generated/device-001.json
```

---

## Step 6: Test Full Workflow (Multi-Container)

**What:** Verify end-to-end flow through all containers.

**Test flow:**
1. POST device data to Orchestrator (:8000)
2. Orchestrator calls HealthAgent (:8001) → returns health analysis
3. Orchestrator calls DiagnosisAgent (:8002) → calls MCP tools → returns diagnosis
4. Orchestrator returns aggregated result

**Checkpoint:**
```bash
# With docker-compose running
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"device_id": "device-001", "temperature": 98, "vibration_level": "high"}'
```

**Expected:** JSON response with workflow result, tool calls logged in agent containers.

---

## Step 7: Error Handling & Retries

**What:** Handle failures gracefully across services.

**Scenarios:**
1. Agent service down → Orchestrator retries with backoff
2. MCP tool timeout → GatewayClient retries
3. Token expired → GatewayClient auto-refresh

**Add to Orchestrator:**
- HTTP client with timeout and retry config
- Circuit breaker for agent calls (optional)

---

## Step 8: Add Logging & Observability

**What:** Consistent logging across all services.

**Add to each service:**
- Structured JSON logging
- Request ID propagation (trace across services)
- Log tool calls, HTTP calls, decisions

**Example log:**
```json
{"timestamp": "...", "service": "diagnosis-agent", "request_id": "abc123", "event": "tool_call", "tool": "get_spare_parts", "duration_ms": 245}
```

---

## Step 9: Prepare for AgentCore Runtime

**What:** Ensure containers are ready for AWS deployment.

**Checklist:**
- [ ] Each Dockerfile builds successfully
- [ ] Environment variables documented
- [ ] Health check endpoints (/health)
- [ ] No hardcoded localhost URLs (use env vars)
- [ ] .env.example file with all required vars

---

## Step 10: Documentation & Cleanup

**What:** Document the architecture and deployment.

**Tasks:**
- [ ] Update README with multi-container setup
- [ ] Add docker-compose usage guide
- [ ] Document environment variables
- [ ] Add API endpoint documentation

---

## Quick Reference

### Environment Variables Required

```bash
# Shared (all services that call MCP tools)
COGNITO_APP_CLIENT_ID=...
COGNITO_APP_CLIENT_SECRET=...
COGNITO_TOKEN_ENDPOINT=...
COGNITO_SCOPE=agentcore/invoke
GATEWAY_URL=...

# Orchestrator only
HEALTH_AGENT_URL=http://health-agent:8001
DIAGNOSIS_AGENT_URL=http://diagnosis-agent:8002

# For Azure OpenAI (agents that use LLM)
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT_NAME=...
```

### Service Endpoints

| Service | Port | Endpoint | Method |
|---------|------|----------|--------|
| Orchestrator | 8000 | /process | POST |
| HealthAgent | 8001 | /analyze | POST |
| DiagnosisAgent | 8002 | /diagnose | POST |

### Tool Names (Gateway Format)

| Short Name | Gateway Full Name |
|------------|-------------------|
| `get_spare_parts` | `get-spare-parts___get_spare_parts` |
| `schedule_maintenance` | `schedule-maintenance___schedule_maintenance` |
| `create_work_order` | `create-work-order___create_work_order` |

GatewayClient's `resolve_tool_name()` handles this mapping.

---

## Progress Tracker

| Step | Status | Notes |
|------|--------|-------|
| 1. Create GatewayClient | ✅ | Created (src/gateway/) |
| 2. Test GatewayClient | ⬜ | |
| 3. Create Agent Services | ✅ | Created in src/services/{orchestrator,health_agent,diagnosis_agent}/ |
| 4. Create Orchestrator | ✅ | LangGraph 4-node workflow with HTTP calls |
| 5. Docker Compose | ⬜ | Ready to create |
| 6. Test Full Workflow | ⬜ | |
| 7. Error Handling | ✅ | Included in services |
| 8. Logging | ✅ | Structured logging in all services |
| 9. Prep for Runtime | ✅ | Dockerfiles + environment variables documented |
| 10. Documentation | ✅ | Updated (this file) |

---

## File Structure (Final)

```
project-root/
│
├── src/                              # SHARED CODE (copied into containers)
│   ├── agents/                       # Agent LOGIC (existing)
│   │   ├── base_agent.py
│   │   ├── health_agent.py
│   │   └── diagnosis_agent.py
│   ├── graph/                        # LangGraph workflow (existing)
│   │   └── workflow.py
│   └── gateway/                      # GatewayClient (created)
│       ├── __init__.py
│       ├── client.py
│       └── exceptions.py
│
├── services/                         # CONTAINER ENTRY POINTS
│   ├── orchestrator/
│   │   ├── app.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── health_agent/
│   │   ├── app.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── diagnosis_agent/
│       ├── app.py
│       ├── Dockerfile
│       └── requirements.txt
│
├── docker-compose.yml
├── .env.example
└── .agentcore.env                    # Secrets (gitignored)
```

---

## Phase 3.1 Enhancement: Dashboard Intelligence & Agent Tracking

**Status:** ✅ COMPLETE (June 12, 2026)

### What Was Added

**Feature 1: Recommendation Fields**
- Rich dashboard recommendations for operations teams
- Action-specific guidance (immediate_actions, predicted_failure_date, etc.)
- Generated by DiagnosisAgent for all health classifications

**Feature 2: Multi-Agent Tracking**
- New endpoints to see which agents/tools were invoked
- `/agents-trace/{device_id}` - device request history
- `/agents-summary` - aggregate statistics

### Files Modified

```
src/agents/diagnosis_agent.py
  ✅ Added _build_recommendations() method
  ✅ Added _get_parts_for_anomaly() helper
  
src/services/diagnosis_agent/app.py
  ✅ Updated DiagnosisAgentResponse schema
  
src/graph/workflow.py
  ✅ Added recommendation fields to WorkflowState
  ✅ Updated _diagnosis_agent_node() to extract recommendations
  ✅ Added agent/tool tracking to state
  
src/services/orchestrator/app.py
  ✅ Updated OrchestratorResponse schema with recommendation fields
  ✅ Added tracking fields (agents_used, mcp_tools_used)
  ✅ Added /agents-trace/{device_id} endpoint
  ✅ Added /agents-summary endpoint
```

### New Response Fields

All endpoints now return:

```json
{
  "insights": "Analysis reasoning (LLM-based or Rule-Based prefix indicating source)",
  "immediate_actions": ["array", "of", "actionable", "steps"],
  "predicted_failure_date": "2026-06-12T17:14:17.291542 or null",
  "recommendation_details": "Detailed maintenance explanation",
  "agents_used": ["HealthAgent", "DiagnosisAgent"],
  "mcp_tools_used": ["create-work-order"]
}
```

### New Endpoints

#### GET /agents-trace/{device_id}

Returns request history for a specific device:

```bash
curl http://localhost:8000/agents-trace/pump-004
```

Response shows which agents and tools were used in each analysis.

#### GET /agents-summary

Aggregates statistics across all devices:

```bash
curl http://localhost:8000/agents-summary
```

Response shows:
- Routing patterns (health_only vs full_diagnosis)
- Which agents are typically invoked
- Which MCP tools are used
- Action distribution

### Testing Commands

```bash
# Test recommendation fields for critical device
curl http://localhost:8000/devices/pump-004 | jq '.recommendation_details'

# Test agent tracking
curl http://localhost:8000/agents-trace/pump-004 | jq '.requests[0].agents_used'

# Test summary statistics
curl http://localhost:8000/agents-summary | jq '.devices[0].routing_paths'
```

### Verified Scenarios

✅ **Critical Device** - URGENT_REPAIR with immediate actions
✅ **Warning Device** - SCHEDULE_MAINTENANCE with 14-day timeline  
✅ **Healthy Device** - MONITOR_ONLY with cost optimization (HealthAgent only)

---

*For detailed Phase 3.1 changes, see [PHASE_3_1_UPDATES.md](docs/PHASE_3_1_UPDATES.md)*
