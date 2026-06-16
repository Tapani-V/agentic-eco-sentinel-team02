# Week 2 Day 5-7: Agent Integration with MCP Tools

**Goal:** Build 3-container architecture with Orchestrator + Agent services calling AWS MCP tools via AgentCore Gateway.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [GatewayClient Module](#3-gatewayclient-module)
4. [Agent Workflow Design](#4-agent-workflow-design)
5. [Implementation Plan](#5-implementation-plan)
6. [File Structure](#6-file-structure)
7. [Testing Strategy](#7-testing-strategy)
8. [Migration to AgentCore Runtime](#8-migration-to-agentcore-runtime)
9. [Documentation & Testing Resources](#9-documentation--testing-resources)

---

## 0. Documentation & Testing Resources

**Quick Access to Implementation Guides:**

| Document | Purpose | For Whom |
|----------|---------|----------|
| [START_HERE.md](START_HERE.md) | Main entry point, quick overview | Everyone - start here! |
| [QUICK_REFERENCE_CARD.md](QUICK_REFERENCE_CARD.md) | One-page cheat sheet with all commands | Quick reference during testing |
| [DOCKER_E2E_QUICK_START.md](DOCKER_E2E_QUICK_START.md) | Step-by-step quick start guide | Getting services running fast |
| [WEEK2_DAY5_7_COMPLETE.md](WEEK2_DAY5_7_COMPLETE.md) | Comprehensive implementation guide | Full understanding of system |
| [IMPLEMENTATION_WEEK2_DAY5_7_DOCKER_E2E.md](IMPLEMENTATION_WEEK2_DAY5_7_DOCKER_E2E.md) | Technical implementation details | Developers implementing changes |
| [README_DOCKER_E2E_TESTING.md](README_DOCKER_E2E_TESTING.md) | Index and overview of all components | Project overview |
| [FINAL_DELIVERY_SUMMARY.md](FINAL_DELIVERY_SUMMARY.md) | Completion summary, what's included | Project managers, stakeholders |
| [COMPLETION_STATUS.txt](COMPLETION_STATUS.txt) | Checklist, status summary | Verification before deployment |

**Quick Start Commands:**
```bash
# One-command test (recommended)
bash run_e2e_tests.sh test

# Manual testing
python run_manual_e2e_test.py

# Preflight check
bash preflight_check.sh
```

---

## 1. Overview

### What's Already Done (Day 1-4)

| Component | Status | Location |
|-----------|--------|----------|
| MCP Tools deployed | ✅ | Lambda + App Runner |
| AgentCore Gateway | ✅ | AWS (gateway_info.json) |
| Cognito token flow | ✅ | setup_cognito_token_flow.py |
| Data-plane test | ✅ | test_agentcore_gateway_starter.py |
| Tool schemas | ✅ | tools/schemas/ |

### What We Build Now (Day 5-7)

| Component | Purpose |
|-----------|---------|
| GatewayClient | Shared module for token + tool calls |
| 3 Containers | Orchestrator + HealthAgent + DiagnosisAgent |
| Docker Compose | Run all services locally |
| End-to-end test | Full workflow with real tools |

### Design Principles

1. **3-container architecture** — Orchestrator + 2 Agent services
2. **Shared GatewayClient** — Copied into agent containers
3. **HTTP between containers** — Orchestrator calls agents via REST
4. **Keep deterministic rules** — No LLM for obvious cases (temperature > 95°C)
5. **LLM for ambiguity** — AI judgment when rules don't apply
6. **Same code for runtime** — Works locally (Docker Compose) and in AgentCore Runtime

---

## 1.5. Story: How It Works (Real-World Examples)

### Story 1: The Happy Path — Device is Fine

**Time: Tuesday, 10:00 AM**

**What happens:**
A water pump at the factory sends sensor data to the Orchestrator:
- Temperature: 72°C (normal)
- Flow rate: 850 L/min (normal)
- Vibration: 2.1 mm/s (normal)
- Pressure: 4.2 bar (normal)

**HealthAgent analyzes:**
- Checks all thresholds: ✓ All green
- Computes degradation score: 0.05 (very healthy)
- Detects anomalies: None
- **Returns: "healthy"**

**Router decides:**
- Sees "healthy" → **SKIP DiagnosisAgent** (no need to investigate)
- **Why skip?** Saves time and cost (no LLM, no tool calls, no overhead)

**Orchestrator returns to client:**
```
{
  "device_id": "pump-001",
  "status": "normal",
  "health_status": "healthy",
  "degradation_score": 0.05,
  "action": "none",
  "message": "Device operating normally. Continue monitoring."
}
```

**Result:** Device continues operating. No action needed. Total time: **80ms**

---

### Story 2: The Complex Path — Device Needs Help

**Time: Tuesday, 10:30 AM**

**What happens:**
A compressor sends suspicious sensor data:
- Temperature: 87°C (slightly high)
- Pressure: fluctuating between 5.5-6.2 bar (unstable)
- Vibration: 4.2 mm/s (high)
- Flow: normal

**Step 1: HealthAgent analyzes**
- Checks thresholds: ⚠️ Pressure anomaly detected, temp slightly high
- Computes degradation score: 0.35 (warning level)
- Detects anomalies: ["pressure_fluctuation", "temperature_elevated"]
- **Returns: "warning"**

**Step 2: Router decides**
- Sees "warning" → **CALL DiagnosisAgent** (investigate further)
- Passes: sensor_data + health_status + anomalies

**Step 3: DiagnosisAgent analyzes (Pattern Matching)**
- Loads compressor rules from knowledge base
- Tries to match patterns:
  - Rule 1: "pressure_fluctuation + vibration_high" → Valve wear (confidence: 0.88) ✓
  - Rule 2: "temp_high + pressure_high" → Cooler issue (confidence: 0.62)
  - Rule 3: "vibration_high + noise" → Bearing issue (confidence: 0.45)
- **Picks best match: Valve wear (0.88 confidence)**

**Step 4: Confidence Check**
- Rule confidence 0.88 >= 0.85 threshold
- **Decision: TRUST THE RULE** (no need for LLM)
- Rule says: recommended_action = "SCHEDULE_MAINTENANCE"

**Step 5: Execute Action**
- Action is "SCHEDULE_MAINTENANCE"
- **Calls MCP Tool #2: schedule-maintenance**
  - Input: {device_id: "comp-001", maintenance_type: "valve_inspection", scheduled_date: "2026-06-20"}
  - AWS Lambda processes request → writes to DynamoDB
  - **Returns: {maintenance_id: "MAINT-89456", status: "scheduled"}**

**Orchestrator returns to client:**
```
{
  "device_id": "comp-001",
  "status": "warning",
  "health_status": "warning",
  "diagnosis": "Compressor valve wear detected",
  "confidence": 0.88,
  "action_taken": "maintenance_scheduled",
  "maintenance_id": "MAINT-89456",
  "scheduled_date": "2026-06-20",
  "message": "Maintenance scheduled for June 20. Technician will inspect valve assembly."
}
```

**Result:** Maintenance is now scheduled. Technician gets notified. Total time: **200ms** (no LLM call needed)

---

### Story 3: The Ambiguous Path — Device Needs AI Judgment

**Time: Tuesday, 11:00 AM**

**What happens:**
A motor sends mixed sensor readings:
- Temperature: 84°C (slightly elevated)
- Vibration: 2.8 mm/s (borderline)
- Current draw: normal
- Sound: slightly higher than baseline

**Step 1: HealthAgent analyzes**
- Some metrics are borderline
- Degradation score: 0.42 (warning)
- Anomalies: ["temperature_elevated", "vibration_medium"]
- **Returns: "warning"**

**Step 2: Router decides**
- Sees "warning" → **CALL DiagnosisAgent**

**Step 3: DiagnosisAgent analyzes (Pattern Matching)**
- Tries to match patterns:
  - Rule 1: "temp_high + vibration_high + bearing_temp_high" → Bearing wear (confidence: 0.72)
  - Rule 2: "current_normal + temp_elevated" → Cooling issue (confidence: 0.65)
  - Rule 3: "vibration_medium + current_normal" → Possible sensor drift (confidence: 0.58)
- **Picks best match: Bearing wear (0.72 confidence)**

**Step 4: Confidence Check**
- Rule confidence 0.72 < 0.85 threshold
- **Decision: UNCERTAIN - CALL LLM** (need AI judgment)

**Step 5: LLM Enhancement**
- Calls Azure OpenAI with:
  - Sensor data
  - Rule suggestion (bearing wear)
  - Historical context
  - Anomalies detected
  
- **LLM returns:**
  ```
  "diagnosis": "Could be early bearing degradation OR sensor calibration issue",
  "confidence": 0.78,
  "recommended_action": "CHECK_PARTS_FIRST",
  "reasoning": "Temperature and vibration slightly elevated but current is normal. 
               If bearing is worn, parts would be needed. Better to verify 
               availability before scheduling maintenance."
  ```

**Step 6: Execute Action - CHECK_PARTS_FIRST**
- **Calls MCP Tool #1: get-spare-parts**
  - Input: {part_type: "motor_bearing"}
  - AWS Lambda queries S3 spare parts inventory
  - **Returns: {count: 2, parts: [{sku: "BEAR-001", in_stock: true}]}**

- **Parts are available!** → Continue to schedule
- **Calls MCP Tool #2: schedule-maintenance**
  - Input: {device_id: "motor-005", maintenance_type: "bearing_replacement", scheduled_date: "2026-06-18"}
  - AWS Lambda writes to DynamoDB
  - **Returns: {maintenance_id: "MAINT-89457", status: "scheduled"}**

**Orchestrator returns to client:**
```
{
  "device_id": "motor-005",
  "status": "warning",
  "health_status": "warning",
  "diagnosis": "Possible bearing degradation (enhanced by AI analysis)",
  "confidence": 0.78,
  "action_taken": "maintenance_scheduled_with_parts",
  "maintenance_id": "MAINT-89457",
  "scheduled_date": "2026-06-18",
  "parts_verified": {
    "motor_bearing": {
      "available": true,
      "count": 2,
      "sku": "BEAR-001"
    }
  },
  "message": "Maintenance scheduled for June 18. Spare bearing is in stock and ready."
}
```

**Result:** Maintenance is scheduled with parts confirmed. Technician knows parts are available. Total time: **450ms** (includes LLM call + 2 MCP tools)

---

### Story 4: The Emergency Path — Critical Device

**Time: Tuesday, 11:30 AM**

**What happens:**
A pump sends critical alerts:
- Temperature: **98°C** (way too high!)
- Vibration: **critical level**
- Pressure: fluctuating wildly
- Pump sounds abnormal

**Step 1: HealthAgent analyzes**
- Temperature > 95°C → **CRITICAL** threshold triggered
- Vibration = critical → **CRITICAL** threshold triggered
- Degradation score: **0.92** (severe)
- Anomalies: multiple critical issues
- **Returns: "critical"**

**Step 2: Router decides**
- Sees "critical" → **CALL DiagnosisAgent** (investigate urgently)

**Step 3: DiagnosisAgent analyzes**
- Matches against rules:
  - Pattern: "temp_very_high + vibration_critical + pressure_unstable" 
  - Diagnosis: "Pump cavitation with bearing failure" 
  - **Confidence: 0.96** (very obvious!)

**Step 4: Confidence Check**
- Rule confidence 0.96 >= 0.85
- **Decision: TRUST THE RULE** (no LLM needed, too obvious)
- Rule says: recommended_action = "URGENT_REPAIR"

**Step 5: Execute Action - URGENT_REPAIR**
- **Calls MCP Tool #3: create-work-order**
  - Input: 
    ```
    {
      work_order_type: "emergency_repair",
      priority: "critical",
      description: "Device pump-002: Pump cavitation with bearing failure. 
                    Temperature 98°C, vibration critical. 
                    IMMEDIATE SHUTDOWN AND REPAIR REQUIRED."
    }
    ```
  - AWS App Runner processes request immediately
  - **Returns: {work_order_id: "WO-12345", status: "urgent", assigned_to: "technician_team_1"}**

**Orchestrator returns to client:**
```
{
  "device_id": "pump-002",
  "status": "critical",
  "health_status": "critical",
  "diagnosis": "Pump cavitation with bearing failure",
  "confidence": 0.96,
  "action_taken": "work_order_created",
  "work_order_id": "WO-12345",
  "priority": "critical",
  "assigned_to": "technician_team_1",
  "message": "CRITICAL ALERT: Emergency work order created. 
             Technician team 1 assigned. Recommend immediate shutdown."
}
```

**Result:** 
- Emergency work order created in seconds
- Technician team notified automatically
- Device flagged for immediate attention
- Total time: **120ms** (no LLM, rule was obvious)

---

### Key Takeaways from Stories

| Story | Device Status | LLM Used? | Tool Called | Time | Result |
|-------|---------------|-----------|-------------|------|--------|
| **1: Happy Path** | Healthy | No | None | 80ms | No action, device continues |
| **2: Simple Issue** | Warning (valve) | No | schedule-maintenance | 200ms | Maintenance scheduled |
| **3: Ambiguous** | Warning (unclear) | Yes | get-spare-parts + schedule-maintenance | 450ms | Maintenance scheduled with confirmed parts |
| **4: Emergency** | Critical | No | create-work-order | 120ms | Urgent work order created, technician notified |

**Pattern:**
- ✅ LLM **NOT used** when rules are confident (saves time & cost)
- ✅ LLM **IS used** only when uncertain (adds accuracy)
- ✅ MCP tools called **only when action needed**
- ✅ Router skips DiagnosisAgent for healthy devices (cost optimization)

---

## 2. Architecture

### 3-Container Architecture (Local + AgentCore Runtime)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ORCHESTRATOR (Port 8000)                            │
│                      FastAPI + LangGraph Workflow                            │
│                                                                             │
│  Endpoints:                                                                 │
│  • POST /process → Receives sensor_data from client                         │
│  • Internally calls HealthAgent and DiagnosisAgent via HTTP                 │
│  • Returns final analysis + actions taken                                   │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ LangGraph Workflow (4 Nodes)                                         │  │
│  │                                                                      │  │
│  │  Node 1: health_agent_node                                           │  │
│  │  ├─ Calls HealthAgent service: POST http://health-agent:8001/analyze│  │
│  │  └─ Waits for response with health_status                           │  │
│  │                                                                      │  │
│  │  Node 2: router_node (Conditional)                                  │  │
│  │  ├─ Checks: if health_status == "healthy"?                          │  │
│  │  ├─ YES → Skip DiagnosisAgent, jump to aggregator                   │  │
│  │  └─ NO → Call DiagnosisAgent                                        │  │
│  │                                                                      │  │
│  │  Node 3: diagnosis_agent_node (Conditional, skipped if healthy)      │  │
│  │  ├─ Calls DiagnosisAgent service: POST http://diagnosis-agent:8002/  │  │
│  │  ├─ Passes: sensor_data + health_status + anomalies                 │  │
│  │  └─ Waits for response with diagnosis + actions taken               │  │
│  │                                                                      │  │
│  │  Node 4: aggregator_node                                             │  │
│  │  ├─ Combines results from all nodes                                  │  │
│  │  └─ Returns final response to client                                 │  │
│  │                                                                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
              │ HTTP Call                            │ HTTP Call
              ▼                                      ▼

┌──────────────────────────────┐    ┌──────────────────────────────┐
│  HEALTH AGENT (Port 8001)    │    │ DIAGNOSIS AGENT (Port 8002)  │
│  FastAPI Service             │    │ FastAPI Service              │
│                              │    │                              │
│ Endpoint:                    │    │ Endpoint:                    │
│ POST /analyze                │    │ POST /diagnose               │
│                              │    │                              │
│ Process:                     │    │ Process:                     │
│ 1. Receive sensor_data       │    │ 1. Receive sensor_data +     │
│ 2. Apply threshold rules     │    │    health_status + anomalies │
│ 3. Compute degradation_score │    │ 2. Match equipment patterns  │
│ 4. Detect anomalies          │    │ 3. If confident (≥0.85):     │
│ 5. Return health_status      │    │    Use rule's action         │
│                              │    │ 4. Else: Call LLM            │
│ Response:                    │    │ 5. Execute tool calls:       │
│ {                            │    │    • get-spare-parts         │
│   health_status,             │    │    • schedule-maintenance    │
│   degradation_score,         │    │    • create-work-order       │
│   anomalies                  │    │ 6. Return diagnosis + action │
│ }                            │    │                              │
│                              │    │ Response:                    │
│ NO AWS TOOLS CALLED          │    │ {                            │
│                              │    │   diagnosis,                 │
│                              │    │   confidence,                │
│                              │    │   action_taken,              │
│                              │    │   tool_results               │
│                              │    │ }                            │
│                              │    │                              │
│                              │    │ AWS TOOLS CALLED VIA         │
│                              │    │ GatewayClient (Cognito JWT)  │
│                              │    │                              │
└──────────────────────────────┘    └──────────────────────────────┘
                                              │
                                              │ HTTPS + JWT Bearer Token
                                              ▼
                        ┌────────────────────────────────────────┐
                        │   AgentCore Gateway (AWS)              │
                        │   Validates JWT + Routes to Tools      │
                        └────────────────────────────────────────┘
                                    │    │    │
                      ┌─────────────┴─┬──┴─┬──┴─────────────┐
                      ▼               ▼   ▼                 ▼
                  ┌─────────┐    ┌─────────────┐    ┌──────────────┐
                  │ Lambda  │    │ Lambda      │    │ App Runner   │
                  │ get-    │    │ schedule-   │    │ create-work- │
                  │ spare-  │    │ maintenance │    │ order        │
                  │ parts   │    │             │    │              │
                  └────┬────┘    └─────┬───────┘    └──────┬───────┘
                       │               │                   │
                       ▼               ▼                   ▼
                    ┌────────┐    ┌──────────┐         [API]
                    │  S3    │    │ DynamoDB │
                    │ (parts)│    │(maint.)  │
                    └────────┘    └──────────┘
```

### Tool Registration (Already Done)

| Tool Name (Gateway) | Backend | Input | Output |
|---------------------|---------|-------|--------|
| `get-spare-parts___get_spare_parts` | Lambda → S3 | `{part_type}` | `{parts[], count}` |
| `schedule-maintenance___schedule_maintenance` | Lambda → DynamoDB | `{device_id, maintenance_type, scheduled_date}` | `{maintenance_id, status}` |
| `create-work-order___create_work_order` | App Runner | `{work_order_type, priority, description}` | `{work_order_id, status}` |

---

## 3. GatewayClient Module

### Purpose

Single Python module that handles:
- Cognito token acquisition (`client_credentials` grant)
- Token caching (in-memory, per-process)
- Token refresh (before expiry)
- Gateway HTTP calls (`tools/list`, `tools/call`)
- Error handling (401/403 retry, timeouts)

### Interface

```python
# src/gateway/client.py

class GatewayClient:
    """
    Shared client for AgentCore Gateway tool calls.
    
    Usage:
        gateway = GatewayClient()
        
        # List available tools
        tools = gateway.list_tools()
        
        # Call a specific tool
        result = gateway.call_tool(
            "get-spare-parts___get_spare_parts",
            {"part_type": "bearing"}
        )
    """
    
    def __init__(self):
        """Load config from environment (.agentcore.env)."""
        
    def list_tools(self) -> List[dict]:
        """Get available tools from gateway."""
        
    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool and return the result."""
        
    def resolve_tool_name(self, short_name: str) -> str:
        """Resolve 'get_spare_parts' → 'get-spare-parts___get_spare_parts'."""
```

### Token Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     GatewayClient                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Agent calls: gateway.call_tool("...", {...})                   │
│                        │                                        │
│                        ▼                                        │
│              ┌─────────────────────┐                            │
│              │ Check token cache   │                            │
│              └──────────┬──────────┘                            │
│                         │                                       │
│           ┌─────────────┴─────────────┐                         │
│           │                           │                         │
│     Token valid?               Token missing/expired?           │
│           │                           │                         │
│           ▼                           ▼                         │
│     Use cached token         ┌─────────────────────┐            │
│           │                  │ POST /oauth2/token  │            │
│           │                  │ grant_type=         │            │
│           │                  │   client_credentials│            │
│           │                  │ scope=agentcore/    │            │
│           │                  │   invoke            │            │
│           │                  └──────────┬──────────┘            │
│           │                             │                       │
│           │                             ▼                       │
│           │                  ┌─────────────────────┐            │
│           │                  │ Cache new token     │            │
│           │                  │ + expiry timestamp  │            │
│           │                  └──────────┬──────────┘            │
│           │                             │                       │
│           └──────────────┬──────────────┘                       │
│                          │                                      │
│                          ▼                                      │
│              ┌─────────────────────┐                            │
│              │ POST gateway/mcp    │                            │
│              │ Authorization:      │                            │
│              │   Bearer <token>    │                            │
│              │ Body: {jsonrpc...}  │                            │
│              └──────────┬──────────┘                            │
│                         │                                       │
│           ┌─────────────┴─────────────┐                         │
│           │                           │                         │
│     Success (200)              401/403 Error                    │
│           │                           │                         │
│           ▼                           ▼                         │
│     Return result              Refresh token                    │
│                                Retry once                       │
│                                       │                         │
│                          ┌────────────┴────────────┐            │
│                          │                         │            │
│                    Success                   Still fails        │
│                          │                         │            │
│                          ▼                         ▼            │
│                    Return result          Raise GatewayError    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Proactive Token Refresh Strategy

Cognito access tokens are valid for **1 hour (3600 seconds)**. A single token cannot be extended — but GatewayClient requests a **new token before the current one expires**.

**Why proactive refresh?**

Without it, if a tool call starts at 10:59:58 and takes 3 seconds, the token would expire mid-request → 401 error.

By refreshing 5 minutes early:
- Always have a valid token with comfortable margin
- No mid-request failures
- Agent can run continuously for days/weeks

**Timeline Example:**

```
10:00 AM   Token A issued (expires 11:00 AM)
           │
           │  ← Using Token A for all gateway calls
           │
10:55 AM   GatewayClient checks: "Token A expires in 5 min, get new one"
           │
           │  → Request NEW Token B from Cognito
           │
10:55 AM   Token B issued (expires 11:55 AM)
           │
           │  ← Token A discarded, now using Token B
           │
11:50 AM   GatewayClient checks: "Token B expires in 5 min, get new one"
           │
           │  → Request NEW Token C from Cognito
           │
           ... continues indefinitely
```

**Implementation Pattern:**

```python
def _get_valid_token(self):
    now = time.time()
    
    # Refresh if token expires in less than 5 minutes (300 seconds)
    if self._token and self._token_expiry - now > 300:
        return self._token  # Still valid, reuse
    
    # Get fresh token from Cognito
    self._token, self._token_expiry = self._fetch_new_token()
    return self._token
```

---

### Configuration

GatewayClient reads from environment (`.agentcore.env` loaded via `python-dotenv`):

| Variable | Example | Purpose |
|----------|---------|---------|
| `COGNITO_APP_CLIENT_ID` | `abc123...` | OAuth client ID |
| `COGNITO_APP_CLIENT_SECRET` | `xyz789...` | OAuth client secret |
| `COGNITO_TOKEN_ENDPOINT` | `https://...amazoncognito.com/oauth2/token` | Token URL |
| `COGNITO_SCOPE` | `agentcore/invoke` | OAuth scope |
| `GATEWAY_URL` | `https://...gateway.bedrock-agentcore.../mcp` | Gateway endpoint |

---

## 4. Agent Workflow Design

### The Clear Story: 4-Step Process

**Step 1: HealthAgent** (Is the device healthy?)
- Reads sensors → Checks thresholds → Returns: `health_status` (healthy/warning/critical)

**Step 2: Router** (Should we investigate further?)
- If healthy → Done, no action needed
- If warning or critical → Investigate

**Step 3: DiagnosisAgent** (What's wrong & what do we do?)
- Matches sensor patterns to known equipment failures
- If confident (confidence ≥ 0.85) → Use rule's recommendation
- If uncertain (confidence < 0.85) → Ask LLM for clarification
- Based on final decision → Call appropriate tool

**Step 4: Tool Execution** (Take action)
- Create urgent work order, schedule maintenance, check parts availability, or defer action

---

### Decision Flow (Hybrid: Rules + LLM)

**AGENT 1: HealthAgent** — Threshold-Based State Classification
```
┌──────────────────────────────────────────────────────────────┐
│ HEALTH AGENT (Port 8001)                                     │
│ Input: sensor_data from device                               │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Read sensor values:                                         │
│  • temperature, vibration_level, pressure, flow, etc.        │
│                                                              │
│  Apply threshold rules:                                      │
│  ✓ IF temperature > 95°C → CRITICAL                          │
│  ✓ IF vibration_level = "critical" → CRITICAL                │
│  ✓ IF pressure > max_threshold → WARNING                     │
│  ✓ IF flow < min_threshold → WARNING                         │
│  ✓ IF all metrics normal → HEALTHY                           │
│                                                              │
│  Compute degradation_score (0.0 - 1.0)                      │
│  List anomalies detected                                     │
│                                                              │
│  OUTPUT:                                                     │
│  {                                                           │
│      "health_status": "healthy" | "warning" | "critical",    │
│      "degradation_score": 0.42,                              │
│      "anomalies": [...],                                     │
│      "timestamp": "2026-06-12T10:30:00"                      │
│  }                                                           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    RESPONSE TO ORCHESTRATOR
```

---

**AGENT 2: Router (in Orchestrator)** — Simple Gate
```
┌──────────────────────────────────────────────────────────────┐
│ ROUTER NODE (in Orchestrator/LangGraph)                      │
│ Input: health_status from HealthAgent                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Decision:                                                   │
│                                                              │
│  if health_status == "healthy":                              │
│     ↓                                                        │
│     → RETURN: "Device operating normally. No action needed." │
│     → SKIP DiagnosisAgent (cost optimization)                │
│                                                              │
│  else if health_status == "warning" or "critical":           │
│     ↓                                                        │
│     → CALL DiagnosisAgent                                    │
│     → PASS: sensor_data + health_status + anomalies          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
          │                              │
      SKIP             INVESTIGATE
          │                              │
          ▼                              ▼
      RETURN                      DIAGNOSIS AGENT
    (No Further                       (Next)
     Action)
```

---

**AGENT 3: DiagnosisAgent** — Root Cause Analysis + Action Orchestration
```
┌──────────────────────────────────────────────────────────────────────────────┐
│ DIAGNOSIS AGENT (Port 8002)                                                  │
│ Input: sensor_data + health_status + anomalies from HealthAgent              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 1: MATCH EQUIPMENT PATTERNS (Equipment-Specific Rules)                │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Load equipment-specific rule base                                      │ │
│  │ Example for PUMP: [                                                   │ │
│  │   {                                                                   │ │
│  │     pattern: "temp_high AND flow_low AND vibration_high",            │ │
│  │     diagnosis: "Pump cavitation with bearing wear",                  │ │
│  │     recommended_action: "URGENT_REPAIR",                            │ │
│  │     confidence: 0.92                                                 │ │
│  │   },                                                                 │ │
│  │   {                                                                 │ │
│  │     pattern: "pressure_fluctuation AND vibration_medium",           │ │
│  │     diagnosis: "Valve wear",                                        │ │
│  │     recommended_action: "SCHEDULE_MAINTENANCE",                     │ │
│  │     confidence: 0.85                                                │ │
│  │   }                                                                  │ │
│  │ ]                                                                   │ │
│  │                                                                     │ │
│  │ Compare sensor_data + anomalies against patterns                   │ │
│  │ Pick best match with highest confidence                            │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                             │                                             │
│                             ▼                                             │
│  STEP 2: CONFIDENCE CHECK                                                │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                                                                    │ │
│  │  if best_rule_confidence >= 0.85:                                 │ │
│  │      ✓ TRUST THE RULE                                             │ │
│  │      ✓ Use rule's recommended_action directly                     │ │
│  │      ✓ NO LLM NEEDED (cost saving)                                │ │
│  │      → Jump to STEP 4: Execute Action                             │ │
│  │                                                                    │ │
│  │  else:                                                             │ │
│  │      ✗ UNCERTAIN MATCH (confidence < 0.85)                        │ │
│  │      ✗ Call LLM for clarification                                 │ │
│  │      → Continue to STEP 3                                         │ │
│  │                                                                    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│     │                                      │                            │
│     │                                      │                            │
│ CONFIDENT                           UNCERTAIN                            │
│   │                                      │                              │
│   │◄──────────────────┬───────────────────│                             │
│                       │                   │                             │
│                       ▼                   ▼                             │
│                    STEP 4             STEP 3                            │
│                 (Execute)            (Call LLM)                         │
│                                                                         │
│  STEP 3: LLM ENHANCEMENT (Azure OpenAI)                               │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │ Call: llm.analyze(                                             │   │
│  │     device_id, equipment_type,                                 │   │
│  │     sensor_data, rule_suggestion, anomalies                    │   │
│  │ )                                                              │   │
│  │                                                                │   │
│  │ LLM returns:                                                   │   │
│  │ {                                                              │   │
│  │   "diagnosis": "Better explanation of issue",                 │   │
│  │   "confidence": 0.78,                                          │   │
│  │   "recommended_action": "CHECK_PARTS_FIRST" | "MONITOR_ONLY"  │   │
│  │   "reasoning": "Why LLM chose this action"                    │   │
│  │ }                                                              │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                             │                                           │
│                             ▼                                           │
│  STEP 4: EXECUTE ACTION (Call Gateway Tools)                           │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │                                                                │   │
│  │  Based on recommended_action:                                 │   │
│  │                                                                │   │
│  │  ┌─ ACTION: URGENT_REPAIR ────────────────────────────────┐   │   │
│  │  │ (High-confidence rule match, obvious failure)          │   │   │
│  │  │ Calls Tool 1: create-work-order                        │   │   │
│  │  │   Input: {priority: "critical", description: "..."}    │   │   │
│  │  │   Output: {work_order_id: "WO-12345"}                  │   │   │
│  │  │ Result: action_taken = "work_order_created"            │   │   │
│  │  └────────────────────────────────────────────────────────┘   │   │
│  │                                                                │   │
│  │  ┌─ ACTION: SCHEDULE_MAINTENANCE ─────────────────────────┐   │   │
│  │  │ (High-confidence rule, non-critical issue)             │   │   │
│  │  │ Calls Tool 2: schedule-maintenance                     │   │   │
│  │  │   Input: {device_id, maintenance_type, date}           │   │   │
│  │  │   Output: {maintenance_id: "MAINT-67890"}              │   │   │
│  │  │ Result: action_taken = "maintenance_scheduled"         │   │   │
│  │  └────────────────────────────────────────────────────────┘   │   │
│  │                                                                │   │
│  │  ┌─ ACTION: CHECK_PARTS_FIRST ───────────────────────────┐   │   │
│  │  │ (LLM recommends: verify parts before scheduling)       │   │   │
│  │  │                                                        │   │   │
│  │  │ Step 1: Call Tool 1: get-spare-parts                  │   │   │
│  │  │   Input: {part_type: "bearing"}                        │   │   │
│  │  │   Output: {count: 2, parts: [...]}                     │   │   │
│  │  │                                                        │   │   │
│  │  │ Step 2: Check result:                                  │   │   │
│  │  │   if parts_available:                                  │   │   │
│  │  │       Call Tool 2: schedule-maintenance                │   │   │
│  │  │       Result: action_taken = "maintenance_scheduled"   │   │   │
│  │  │   else:                                                │   │   │
│  │  │       Call Tool 3: create-work-order (escalate)        │   │   │
│  │  │       Result: action_taken = "work_order_created"      │   │   │
│  │  └────────────────────────────────────────────────────────┘   │   │
│  │                                                                │   │
│  │  ┌─ ACTION: MONITOR_ONLY ────────────────────────────────┐   │   │
│  │  │ (LLM: too uncertain, insufficient data)               │   │   │
│  │  │ NO TOOL CALLS                                          │   │   │
│  │  │ Returns: {                                             │   │   │
│  │  │   next_check_in_hours: 8,                              │   │   │
│  │  │   escalation_threshold: "if temp > 88°C",              │   │   │
│  │  │   reason: "Low confidence, continue monitoring"        │   │   │
│  │  │ }                                                      │   │   │
│  │  │ Result: action_taken = "monitoring_recommended"        │   │   │
│  │  └────────────────────────────────────────────────────────┘   │   │
│  │                                                                │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                             │                                           │
│                             ▼                                           │
│  OUTPUT to Orchestrator:                                               │
│  {                                                                     │
│      "device_id": "device-001",                                        │
│      "diagnosis": "Pump cavitation with bearing wear",                 │
│      "confidence": 0.92,                                               │
│      "health_status_input": "critical",                                │
│      "recommended_action": "URGENT_REPAIR",                            │
│      "action_taken": "work_order_created",                             │
│      "tool_results": {"work_order_id": "WO-12345"},                    │
│      "timestamp": "2026-06-12T10:30:15"                                │
│  }                                                                     │
│                                                                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

**ORCHESTRATOR WORKFLOW** — The Complete Picture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ORCHESTRATOR (Port 8000) - LangGraph Workflow                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Input: sensor_data = {device_id, equipment_type, temperature, ...}        │
│                                                                             │
│         ┌─────────────────────────────────────────────────────────────┐    │
│         │ NODE 1: Call HealthAgent                                    │    │
│         │ HTTP POST → http://health-agent:8001/analyze                │    │
│         │                                                             │    │
│         │ Returns:                                                    │    │
│         │ {                                                           │    │
│         │   health_status: "healthy" | "warning" | "critical",        │    │
│         │   degradation_score: 0.42,                                  │    │
│         │   anomalies: [...]                                          │    │
│         │ }                                                           │    │
│         └──────────────┬────────────────────────────────────────────┘    │
│                        │                                                   │
│                        ▼                                                   │
│         ┌──────────────────────────────────────────────────────────────┐  │
│         │ NODE 2: Router (Conditional Edge)                            │  │
│         │                                                              │  │
│         │ Check: health_status == "healthy"?                           │  │
│         └──────────────┬──────────────────────────┬───────────────────┘  │
│                        │                          │                       │
│                      YES                         NO                       │
│                        │                          │                       │
│              (Skip DiagnosisAgent)    (Investigate further)               │
│                        │                          │                       │
│                        ▼                          ▼                       │
│         ┌──────────────────────────────┐  ┌────────────────────────────┐  │
│         │ NODE 3A: Aggregator (Healthy)│  │ NODE 3B: Call DiagnosisAgent│  │
│         │                              │  │                            │  │
│         │ Return:                      │  │ HTTP POST →                │  │
│         │ {                            │  │   http://diagnosis-agent:  │  │
│         │   status: "normal",          │  │   8002/diagnose             │  │
│         │   action: "none"             │  │                            │  │
│         │ }                            │  │ Returns:                   │  │
│         │                              │  │ {                          │  │
│         │ ✓ No tools called            │  │   diagnosis: "...",        │  │
│         │ ✓ No maintenance scheduled   │  │   confidence: 0.92,        │  │
│         │                              │  │   recommended_action: "...",│  │
│         │                              │  │   action_taken: "...",     │  │
│         │                              │  │   tool_results: {...}      │  │
│         │                              │  │ }                          │  │
│         │                              │  │                            │  │
│         │                              │  │ ✓ May call AWS tools:      │  │
│         │                              │  │   - create-work-order      │  │
│         │                              │  │   - schedule-maintenance   │  │
│         │                              │  │   - get-spare-parts        │  │
│         └──────────────┬───────────────┘  └────────────┬───────────────┘  │
│                        │                               │                   │
│                        └───────────────┬────────────────┘                   │
│                                        │                                   │
│                                        ▼                                   │
│         ┌─────────────────────────────────────────────────────────────┐  │
│         │ NODE 4: Aggregator (Final Response)                         │  │
│         │                                                             │  │
│         │ Combine results from HealthAgent + optional DiagnosisAgent │  │
│         │ Return complete analysis + actions taken                    │  │
│         │                                                             │  │
│         │ OUTPUT:                                                     │  │
│         │ {                                                           │  │
│         │   device_id: "device-001",                                  │  │
│         │   health_status: "critical",                                │  │
│         │   diagnosis: "Pump cavitation",                             │  │
│         │   confidence: 0.92,                                         │  │
│         │   action_taken: "work_order_created",                       │  │
│         │   work_order_id: "WO-12345",                                │  │
│         │   timestamp: "2026-06-12T10:30:15"                          │  │
│         │ }                                                           │  │
│         └──────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Summary: Who Does What?

| Step | Agent | Input | Processing | Output | AWS Tools Called |
|------|-------|-------|------------|--------|------------------|
| 1 | **HealthAgent** | sensor_data | Threshold checks only | `health_status` | None |
| 2 | **Router** | `health_status` | Branch logic | Proceed to DiagnosisAgent or return | None |
| 3 | **DiagnosisAgent** | sensor_data + health_status | Rule matching + optional LLM | `diagnosis` + `recommended_action` + `action_taken` | `create-work-order`, `schedule-maintenance`, `get-spare-parts` (conditional) |
| 4 | **Aggregator** | All results | Combine + format | Final response | None |

### Agent Responsibilities

| Agent | Input | Output | Tools Used |
|-------|-------|--------|------------|
| **HealthAgent** | sensor_data | `health_status` {healthy/warning/critical}, `degradation_score`, `anomalies` | None |
| **Router** | `health_status` | Decision: skip or proceed to DiagnosisAgent | None |
| **DiagnosisAgent** | sensor_data + `health_status` + `anomalies` | `diagnosis`, `confidence`, `recommended_action`, `tool_result` | `get-spare-parts`, `schedule-maintenance`, `create-work-order` |

---

### Where Actions Come From: Rules vs LLM

**Action values** (`URGENT_REPAIR`, `SCHEDULE_MAINTENANCE`, `MONITOR_ONLY`, `CHECK_PARTS_FIRST`) come from **two sources**:

#### Source 1: Equipment-Specific Rules (High Confidence)
When rule confidence **≥ 0.85**, use the rule's built-in recommendation.

Example: PUMP cavitation pattern
```python
{
    "pattern": "temperature_high AND flow_low AND vibration_high",
    "diagnosis": "Pump cavitation with bearing wear",
    "confidence": 0.92,
    "severity": "high",
    "recommended_action": "URGENT_REPAIR",     # ← From rule
    "action_details": {
        "work_order_type": "emergency_repair",
        "priority": "critical",
        "parts_needed": ["bearing_assembly", "seal_kit"]
    }
}
```

#### Source 2: LLM Enhancement (Low Confidence)
When rule confidence **< 0.85**, call LLM to clarify. LLM returns:

```python
{
    "diagnosis": "Possible sensor drift or early bearing degradation",
    "reasoning": "Temperature slightly elevated but other metrics stable. Could be sensor malfunction or gradual wear.",
    "confidence_adjustment": 0.78,  # Updated confidence
    "recommended_action": "MONITOR_ONLY",      # ← From LLM
    "monitoring_details": {
        "check_frequency": "every_8_hours",
        "escalation_threshold": "if temp exceeds 88°C",
        "reason": "Verify if sensor or real issue before scheduling maintenance"
    }
}
```

---

### Possible Action Values

| Action | Source | Meaning | What Happens Next |
|--------|--------|---------|-------------------|
| `URGENT_REPAIR` | Rule (high conf) | Immediate action needed | Call `create-work-order` with priority=critical |
| `SCHEDULE_MAINTENANCE` | Rule (high conf) or LLM | Maintenance needed soon | Call `schedule-maintenance` for future date |
| `CHECK_PARTS_FIRST` | LLM | Verify parts before scheduling | Call `get-spare-parts`, then decide schedule/work-order |
| `MONITOR_ONLY` | LLM (low conf) | Defer action, watch closely | No tool call; log recommendation for later review |

---

### When Does Each Action Occur? (Real Scenarios)

**Scenario 1: URGENT_REPAIR** (High-confidence rule match)
```
Device: Motor with vibration_level = "critical" AND temperature > 95°C
↓
HealthAgent: health_status = "critical"
↓
Router: Call DiagnosisAgent
↓
DiagnosisAgent Rule Match: 
  - Pattern: motor_stator_failure (vibration + temp)
  - Confidence: 0.95 (obvious match)
  - recommended_action: "URGENT_REPAIR"
↓
DiagnosisAgent Output:
  action = "URGENT_REPAIR"
  → Call create-work-order(priority="critical", description="Motor stator failure - immediate repair needed")
↓
Result: Work order created immediately. No LLM needed (too obvious).
```

**Scenario 2: SCHEDULE_MAINTENANCE** (High-confidence rule, non-critical)
```
Device: Compressor with pressure_fluctuation AND minor_vibration, temp=82°C
↓
HealthAgent: health_status = "warning"
↓
Router: Call DiagnosisAgent
↓
DiagnosisAgent Rule Match:
  - Pattern: compressor_valve_wear (pressure + vibration correlation)
  - Confidence: 0.88
  - recommended_action: "SCHEDULE_MAINTENANCE"
↓
DiagnosisAgent Output:
  action = "SCHEDULE_MAINTENANCE"
  → Call schedule-maintenance(device_id="comp-001", maintenance_type="valve_inspection", scheduled_date="2026-06-20")
↓
Result: Maintenance scheduled for next week. No urgency.
```

**Scenario 3: CHECK_PARTS_FIRST** (LLM recommendation)
```
Device: Pump with temp=87°C, flow_low, vibration=medium (ambiguous pattern)
↓
HealthAgent: health_status = "warning"
↓
Router: Call DiagnosisAgent
↓
DiagnosisAgent Rule Match:
  - Pattern: bearing_wear (but also matches sensor_drift pattern)
  - Confidence: 0.72 < 0.85 (uncertain)
  - Trigger LLM
↓
LLM Analysis:
  "Could be bearing wear (needs replacement) OR sensor malfunction (false alarm).
   Recommend checking part availability first. If bearing is available, schedule replacement.
   If not available or parts don't fit, create urgent work order for diagnosis."
  recommended_action: "CHECK_PARTS_FIRST"
↓
DiagnosisAgent Output:
  action = "CHECK_PARTS_FIRST"
  → Call get-spare-parts(part_type="pump_bearing")
  → Response: count=2 (parts available)
  → Call schedule-maintenance(device_id="pump-005", maintenance_type="bearing_replacement", scheduled_date="2026-06-18")
↓
Result: Maintenance scheduled with parts confirmation. LLM helped disambiguate.
```

**Scenario 4: MONITOR_ONLY** (LLM defers action)
```
Device: Motor with temp=84°C, vibration=medium, pressure_normal (mixed signals)
↓
HealthAgent: health_status = "warning" (slight anomaly detected)
↓
Router: Call DiagnosisAgent
↓
DiagnosisAgent Rule Match:
  - Pattern: possible_cooling_issue OR early_degradation
  - Confidence: 0.68 < 0.85 (very uncertain)
  - Trigger LLM
↓
LLM Analysis:
  "Metrics are borderline. No clear pattern of failure.
   Possible causes: ambient temperature increase, sensor calibration drift, or very early degradation.
   Recommend: Continue monitoring for 48 hours. If temperature continues to rise, escalate to maintenance.
   Current reading likely transient."
  recommended_action: "MONITOR_ONLY"
↓
DiagnosisAgent Output:
  action = "MONITOR_ONLY"
  → NO tool call (no work order, no parts order, no maintenance scheduled)
  → Return monitoring recommendation: "Check device again in 8 hours"
↓
Result: Device continues operation. Orchestrator logs recommendation. Next check in 8 hours will reassess.
```

### Example: DiagnosisAgent Implementation with Action Routing

```python
class DiagnosisAgent:
    """
    Root cause analysis + tool orchestration for warning/critical devices.
    
    Only receives devices that HealthAgent marked as "warning" or "critical".
    Healthy devices are skipped by Router (cost optimization).
    """
    
    def __init__(self):
        self.gateway = GatewayClient()
        self.llm = AzureOpenAIClient()
        self.knowledge_base = load_equipment_rules()
    
    def process(self, device_data: dict) -> dict:
        """
        Main entry point.
        
        Args:
            device_data: {device_id, equipment_type, sensor_data, health_status, anomalies}
                        health_status is from HealthAgent ("warning" or "critical")
        
        Returns:
            {diagnosis, confidence, recommended_action, action_taken, tool_results}
        """
        device_id = device_data["device_id"]
        equipment_type = device_data["equipment_type"]
        sensor_data = device_data["sensor_data"]
        anomalies = device_data["anomalies"]
        health_status = device_data["health_status"]
        
        # 1. TRY EQUIPMENT-SPECIFIC RULES FIRST
        rule_result = self._match_equipment_patterns(equipment_type, sensor_data, anomalies)
        
        # rule_result = {
        #     "diagnosis": "...",
        #     "confidence": 0.85,
        #     "severity": "high",
        #     "recommended_action": "URGENT_REPAIR" | "SCHEDULE_MAINTENANCE" | "MONITOR_ONLY" | "CHECK_PARTS_FIRST",
        #     "action_details": {...}
        # }
        
        # 2. IF RULE CONFIDENT, USE IT DIRECTLY
        if rule_result["confidence"] >= 0.85:
            print(f"[DIAGNOSIS] Rule confidence {rule_result['confidence']:.2f} >= 0.85, trusting rule")
            action = rule_result["recommended_action"]
            diagnosis = rule_result["diagnosis"]
            confidence = rule_result["confidence"]
        
        # 3. IF RULE UNCERTAIN, CALL LLM FOR CLARIFICATION
        else:
            print(f"[DIAGNOSIS] Rule confidence {rule_result['confidence']:.2f} < 0.85, calling LLM")
            
            llm_result = self.llm.analyze(
                device_id=device_id,
                equipment_type=equipment_type,
                sensor_data=sensor_data,
                rule_suggestion=rule_result,  # Give LLM context of what rule suggested
                anomalies=anomalies
            )
            
            # LLM returns:
            # {
            #     "diagnosis": "Better explanation",
            #     "confidence": 0.78,
            #     "recommended_action": "CHECK_PARTS_FIRST" | "MONITOR_ONLY" | ...,
            #     "reasoning": "Why LLM chose this action"
            # }
            
            action = llm_result["recommended_action"]
            diagnosis = llm_result["diagnosis"]
            confidence = llm_result["confidence"]
        
        # 4. EXECUTE BASED ON RECOMMENDED ACTION
        tool_results = self._execute_action(device_id, action, rule_result, health_status)
        
        return {
            "device_id": device_id,
            "equipment_type": equipment_type,
            "diagnosis": diagnosis,
            "confidence": round(confidence, 2),
            "health_status_input": health_status,
            "recommended_action": action,
            "action_taken": tool_results["action_taken"],
            "tool_results": tool_results.get("results", {}),
            "timestamp": datetime.now().isoformat()
        }
    
    def _execute_action(self, device_id: str, action: str, rule_result: dict, health_status: str) -> dict:
        """
        Execute tool calls based on recommended action.
        
        Actions:
        - URGENT_REPAIR: Create critical work order immediately
        - SCHEDULE_MAINTENANCE: Schedule maintenance for future date
        - CHECK_PARTS_FIRST: Check availability, then schedule or escalate
        - MONITOR_ONLY: No tool call, just log recommendation
        """
        
        if action == "URGENT_REPAIR":
            print(f"[ACTION] URGENT_REPAIR for {device_id}")
            result = self.gateway.call_tool(
                "create-work-order___create_work_order",
                {
                    "work_order_type": "emergency_repair",
                    "priority": "critical",
                    "description": f"Device {device_id}: {rule_result['diagnosis']}. Immediate action required.",
                    "device_id": device_id
                }
            )
            return {
                "action_taken": "work_order_created",
                "results": {"work_order_id": result.get("work_order_id")}
            }
        
        elif action == "SCHEDULE_MAINTENANCE":
            print(f"[ACTION] SCHEDULE_MAINTENANCE for {device_id}")
            
            maintenance_type = rule_result.get("action_details", {}).get("maintenance_type", "inspection")
            scheduled_date = rule_result.get("action_details", {}).get("scheduled_date", 
                                                                        (datetime.now() + timedelta(days=7)).isoformat()[:10])
            
            result = self.gateway.call_tool(
                "schedule-maintenance___schedule_maintenance",
                {
                    "device_id": device_id,
                    "maintenance_type": maintenance_type,
                    "scheduled_date": scheduled_date,
                    "reason": rule_result["diagnosis"]
                }
            )
            return {
                "action_taken": "maintenance_scheduled",
                "results": {"maintenance_id": result.get("maintenance_id"), "scheduled_date": scheduled_date}
            }
        
        elif action == "CHECK_PARTS_FIRST":
            print(f"[ACTION] CHECK_PARTS_FIRST for {device_id}")
            
            parts_needed = rule_result.get("action_details", {}).get("parts_needed", [])
            if not parts_needed:
                parts_needed = ["diagnostic_required"]
            
            # Check each part
            parts_results = {}
            all_available = True
            
            for part_type in parts_needed:
                part_check = self.gateway.call_tool(
                    "get-spare-parts___get_spare_parts",
                    {"part_type": part_type}
                )
                parts_results[part_type] = {
                    "available": part_check.get("count", 0) > 0,
                    "count": part_check.get("count", 0)
                }
                if part_check.get("count", 0) == 0:
                    all_available = False
            
            # Decide next step based on parts availability
            if all_available:
                # Parts available → schedule maintenance
                print(f"[ACTION] Parts available, scheduling maintenance")
                result = self.gateway.call_tool(
                    "schedule-maintenance___schedule_maintenance",
                    {
                        "device_id": device_id,
                        "maintenance_type": rule_result.get("action_details", {}).get("maintenance_type", "repair"),
                        "scheduled_date": (datetime.now() + timedelta(days=3)).isoformat()[:10],
                        "reason": f"{rule_result['diagnosis']} (Parts verified available)"
                    }
                )
                return {
                    "action_taken": "maintenance_scheduled_with_parts",
                    "results": {
                        "maintenance_id": result.get("maintenance_id"),
                        "parts_verified": parts_results
                    }
                }
            else:
                # Parts unavailable → escalate to urgent work order
                print(f"[ACTION] Parts unavailable, creating urgent work order")
                result = self.gateway.call_tool(
                    "create-work-order___create_work_order",
                    {
                        "work_order_type": "emergency_repair",
                        "priority": "high",
                        "description": f"Device {device_id}: {rule_result['diagnosis']}. Required parts unavailable, need specialist.",
                        "device_id": device_id
                    }
                )
                return {
                    "action_taken": "work_order_created_parts_unavailable",
                    "results": {
                        "work_order_id": result.get("work_order_id"),
                        "parts_status": parts_results
                    }
                }
        
        elif action == "MONITOR_ONLY":
            print(f"[ACTION] MONITOR_ONLY for {device_id} - deferring action")
            
            # No tool call, just return monitoring recommendation
            return {
                "action_taken": "monitoring_recommended",
                "results": {
                    "next_check_in_hours": 8,
                    "escalation_threshold": "if condition worsens",
                    "reason": "Low confidence - insufficient data for action. Continue monitoring."
                }
            }
        
        else:
            print(f"[ACTION] Unknown action: {action}, defaulting to MONITOR_ONLY")
            return {
                "action_taken": "unknown_action_deferred",
                "results": {}
            }
    
    def _match_equipment_patterns(self, equipment_type: str, sensor_data: dict, anomalies: list) -> dict:
        """
        Match sensor patterns to equipment-specific rules.
        Returns best-matching rule with confidence score.
        """
        
        rules = self.knowledge_base.get(equipment_type, [])
        matches = []
        
        for rule in rules:
            confidence = self._calculate_rule_confidence(rule, sensor_data, anomalies)
            if confidence > 0.3:  # Only include rules with >30% match
                matches.append({
                    "diagnosis": rule["diagnosis"],
                    "confidence": confidence,
                    "severity": rule["severity"],
                    "recommended_action": rule["recommended_action"],
                    "action_details": rule.get("action_details", {})
                })
        
        if matches:
            # Return best match
            best = max(matches, key=lambda x: x["confidence"])
            return best
        else:
            # No rules matched, return generic
            return {
                "diagnosis": "Degradation detected but cause unclear",
                "confidence": 0.50,
                "severity": "medium",
                "recommended_action": "MONITOR_ONLY",
                "action_details": {}
            }
    
    def _calculate_rule_confidence(self, rule: dict, sensor_data: dict, anomalies: list) -> float:
        """
        Calculate how well sensor data matches rule pattern.
        Returns 0.0 to 1.0.
        """
        # Simplified example - in practice, this is more complex
        matched_anomalies = 0
        for expected_anomaly in rule.get("patterns", []):
            if expected_anomaly in [a["type"] for a in anomalies]:
                matched_anomalies += 1
        
        confidence = min(1.0, matched_anomalies / max(len(rule.get("patterns", [])), 1))
        return confidence
```

**Key Points:**
- Line 80-86: Confidence check decides between rule and LLM
- Line 100-150: `_execute_action()` implements all four action paths
- Line 113-123: `URGENT_REPAIR` → immediate work order
- Line 125-139: `SCHEDULE_MAINTENANCE` → schedule for future
- Line 141-181: `CHECK_PARTS_FIRST` → conditional logic (parts → schedule; no parts → escalate)
- Line 183-194: `MONITOR_ONLY` → no tool call, just recommendation


---

## 5. Implementation Plan

### Day 5: GatewayClient + Services Setup

| Task | Time | Deliverable |
|------|------|-------------|
| Test GatewayClient | 30 min | Verify token + tool calls work |
| Create `services/` directory structure | 30 min | Orchestrator + 2 agent service folders |
| Create HealthAgent service | 1.5 hr | FastAPI app with POST /analyze |
| Create DiagnosisAgent service | 1.5 hr | FastAPI app with POST /diagnose |

### Day 6: Orchestrator + Docker Compose

| Task | Time | Deliverable |
|------|------|-------------|
| Create Orchestrator service | 1.5 hr | FastAPI + LangGraph workflow |
| Create Dockerfiles | 1 hr | 3 Dockerfiles |
| Create docker-compose.yml | 30 min | All 3 services configured |
| Test locally with Docker Compose | 1 hr | All services running |

### Day 7: Integration Testing + Polish

| Task | Time | Deliverable |
|------|------|-------------|
| End-to-end workflow test | 1 hr | Full workflow with real tools |
| Error handling improvements | 1 hr | Graceful failures, logging |
| Documentation | 30 min | Updated README, usage guide |

---

## 6. File Structure (Week 2 Day 5-7 Final Implementation)

### Current Directory Structure

```
project-root/
│
├── src/
│   ├── agents/                       # Agent core logic (PURE PYTHON)
│   │   ├── base_agent.py
│   │   ├── health_agent.py           # ✅ Pure classification, NO tools
│   │   └── diagnosis_agent.py        # ✅ 4-step process: pattern → confidence → LLM → execute
│   │
│   ├── gateway/                      # GatewayClient module
│   │   ├── __init__.py
│   │   ├── client.py                 # ✅ Cognito token + tool calls
│   │   └── exceptions.py
│   │
│   ├── graph/                        # Orchestration workflow (CORE LOGIC)
│   │   └── workflow.py               # ✅ OrchestrationWorkflow class (LangGraph 4-node, HTTP-based)
│   │
│   └── services/                     # SERVICE WRAPPERS (CONTAINER ENTRY POINTS)
│       ├── orchestrator/             # Container 1 (Port 8000)
│       │   ├── app.py                # ✅ FastAPI wrapper for OrchestrationWorkflow
│       │   ├── Dockerfile
│       │   └── requirements.txt
│       │
│       ├── health_agent/             # Container 2 (Port 8001)
│       │   ├── app.py                # ✅ FastAPI wrapper for HealthAgent
│       │   ├── Dockerfile
│       │   └── requirements.txt
│       │
│       └── diagnosis_agent/          # Container 3 (Port 8002)
│           ├── app.py                # ✅ FastAPI wrapper for DiagnosisAgent
│           ├── Dockerfile
│           └── requirements.txt
│
│   └── utils/                        # Utility modules (data loading, helpers)
│       └── device_loader.py          # ✅ DeviceLoader class for real sensor data
│
├── data/
│   └── generated/                    # Real device time-series data
│       ├── pump-001.json            # 720 hourly readings per device
│       ├── pump-002.json
│       ├── motor-005.json
│       └── ... (17 devices total)
│
├── docker-compose.yml
├── .agentcore.env                    # Secrets (gitignored)
└── .agentcore.env.example            # Template
```

### Device Endpoint Architecture: Data Loading Pattern

**Separation of Concerns:**

The device endpoint system uses a **3-tier architecture** for clean separation:

```
Tier 1: Data Layer
└── data/generated/{device_id}.json (720 hourly readings, real sensor time-series)

Tier 2: Data Loader Utility
└── src/utils/device_loader.py (DeviceLoader class)
    └── Methods: list_available_devices(), get_device_status(), get_device_summary()
    └── Purpose: Load + format JSON device data for agent processing
    └── Returns: Device status dict compatible with OrchestratorRequest

Tier 3: API Endpoints
└── src/services/orchestrator/app.py (FastAPI wrapper)
    └── GET /devices → Lists all available devices
    └── GET /devices/{device_id}/summary → Device status + 30-day trends
    └── GET /devices/{device_id} → Main endpoint: load data → run workflow
    └── Imports: DeviceLoader from src.utils.device_loader
    └── Usage: device_loader = DeviceLoader(data_dir="data/generated")

Tier 4: Workflow Layer
└── LangGraph 4-node workflow (HealthAgent → Router → DiagnosisAgent → Aggregator)

Tier 5: Integration Layer
└── AWS AgentCore Gateway (MCP tool execution)
```

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| **Separate DeviceLoader class** | Reusable utility, testable independently, can be imported by other services |
| **Location: src/utils/** | Shared utilities location (not agent-specific, not service-specific) |
| **DeviceLoader NOT in app.py** | Keeps orchestrator app.py clean (wrapper only), follows single-responsibility principle |
| **Real device data in data/generated/** | Docker-friendly location (`COPY data/ ./data/` in Dockerfile.orchestrator) |
| **DeviceLoader imported by app.py** | Orchestrator app calls DeviceLoader to fetch device data before processing |
| **3 endpoints for devices** | /devices (list), /devices/{id}/summary (history), /devices/{id} (process) |

**Example Usage in Orchestrator:**

```python
# src/services/orchestrator/app.py

from src.utils.device_loader import DeviceLoader

# Initialize once at startup
device_loader = DeviceLoader(data_dir="data/generated")

@app.get("/devices")
async def list_devices():
    """List all available devices."""
    devices = device_loader.list_available_devices()
    return {"devices": devices, "count": len(devices)}

@app.get("/devices/{device_id}")
async def process_device(device_id: str):
    """Load device data and run full orchestration workflow."""
    # Load real device status from JSON files
    device_status = device_loader.get_device_status(device_id)
    
    # Convert to OrchestratorRequest format
    request = OrchestratorRequest(
        device_id=device_id,
        equipment_type=device_status["equipment_type"],
        current_reading=device_status["current_reading"]
    )
    
    # Run LangGraph workflow
    result = await workflow.invoke(request)
    
    return result
```

**Comparison to Phase 2.8:**

| Aspect | Phase 2.8 (Inline) | Phase 3.1 (Separated) |
|--------|-------------------|----------------------|
| **Data loading logic** | Hardcoded in orchestrator app.py | Separate DeviceLoader utility |
| **Reusability** | Limited to orchestrator | Available to any service |
| **Testability** | Mixed concerns (hard to test loader alone) | Pure DeviceLoader class (easy to test) |
| **Maintainability** | Data logic + API logic in same file | Clean separation of concerns |
| **Docker integration** | Data not included | Data automatically in container |

**Benefits of Separation:**

✅ **Modularity:** DeviceLoader can be used by health checks, dashboards, or other services  
✅ **Testability:** DeviceLoader tested independently (no HTTP overhead)  
✅ **Clarity:** app.py is obviously an HTTP wrapper, not a data processor  
✅ **Scalability:** Easy to add database backend later (replace JSON files with queries)  
✅ **Code reuse:** Multiple services can import DeviceLoader  

### Architecture Pattern: Core + Wrapper Separation

**Design Principle:** Consistent microservices pattern across all components

```
Agent Pattern:
├── Core: src/agents/health_agent.py (reusable Python class)
└── Wrapper: src/services/health_agent/app.py (FastAPI endpoint)

Workflow Pattern (NOW CONSISTENT):
├── Core: src/graph/workflow.py (OrchestrationWorkflow class, reusable)
└── Wrapper: src/services/orchestrator/app.py (FastAPI endpoints)

Benefits:
- Core logic is container-agnostic (can run anywhere)
- Service wrappers are just HTTP frontends
- Easy to test core logic independently
- Consistent structure across all services
```

### Key Files Implementation Status

| File | Purpose | Status | Implementation |
|------|---------|--------|-----------------|
| `src/agents/health_agent.py` | Pure health classification | ✅ Updated | Threshold rules + anomaly detection, NO tools |
| `src/agents/diagnosis_agent.py` | 4-step diagnosis | ✅ Updated | Pattern matching → Confidence → LLM → Actions |
| `src/gateway/client.py` | Cognito + tool calls | ✅ Done | Token caching + MCP tool invocation |
| `src/graph/workflow.py` | OrchestrationWorkflow (CORE) | ✅ Refactored | LangGraph 4-node, HTTP to agents, async |
| `src/services/orchestrator/app.py` | FastAPI wrapper | ✅ Refactored | Pure wrapper, imports OrchestrationWorkflow |
| `src/services/health_agent/app.py` | FastAPI wrapper | ✅ Updated | Pure wrapper, imports HealthAgent |
| `src/services/diagnosis_agent/app.py` | FastAPI wrapper | ✅ Updated | Pure wrapper, imports DiagnosisAgent |
| `docker-compose.yml` | Local multi-container setup | ⬜ Pending | Orchestrates 3 services + networking |

---

## 7. Testing Strategy (Week 2 Day 5-7)

### 3-Container Architecture Testing

**Local Setup (Docker Compose):**
```bash
# Start all 3 services
docker-compose up --build

# Verify services are running
curl http://localhost:8000/health  # Orchestrator
curl http://localhost:8001/health  # HealthAgent
curl http://localhost:8002/health  # DiagnosisAgent
```

### HTTP Endpoint Tests

**1. HealthAgent Service (Port 8001)**
```bash
# Test pure health classification
curl -X POST http://localhost:8001/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "pump-001",
    "equipment_type": "PUMP",
    "current_reading": {
      "readings": {
        "temperature": {"value": 72, "unit": "C", "normal_range": [20, 95]},
        "vibration": {"value": 2.1, "unit": "mm/s", "normal_range": [0, 3]}
      }
    }
  }'

# Expected response: health_status="healthy", degradation_score=0.05
```

**2. DiagnosisAgent Service (Port 8002)**
```bash
# Test 4-step diagnosis
curl -X POST http://localhost:8002/diagnose \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "comp-001",
    "equipment_type": "COMPRESSOR",
    "health_status": "warning",
    "degradation_score": 0.35,
    "anomalies": ["pressure_fluctuation", "vibration_high"],
    "current_reading": {...}
  }'

# Expected: action="SCHEDULE_MAINTENANCE", confidence=0.88
```

**3. Orchestrator Service (Port 8000) - Full Workflow**
```bash
# Test complete 4-node workflow
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "pump-001",
    "equipment_type": "PUMP",
    "current_reading": {
      "readings": {
        "temperature": {"value": 72, "unit": "C", "normal_range": [20, 95]},
        "vibration": {"value": 2.1, "unit": "mm/s", "normal_range": [0, 3]}
      }
    }
  }'

# Expected:
# - Calls HealthAgent (Node 1) → health_status="healthy"
# - Router (Node 2) → route="end" (cost optimization)
# - Aggregator (Node 4) → returns immediately
# - Total time: ~80ms
```

### Integration Tests (4 Stories)

| Test | Device Status | Expected Path | Time |
|------|---------------|---------------|------|
| **Story 1: Happy** | Healthy (temp 72°C, normal vibration) | health_only | 80ms |
| **Story 2: Simple** | Warning (pressure unstable, vibration high) | full_diagnosis (rule confidence 0.88) | 200ms |
| **Story 3: Ambiguous** | Warning (temp elevated, medium vibration) | full_diagnosis + LLM (rule confidence 0.72) | 450ms |
| **Story 4: Critical** | Critical (temp 98°C, vibration critical) | full_diagnosis (rule confidence 0.96) | 120ms |

### Test Commands

```bash
# Health check all services
curl -s http://localhost:8000/health && echo "✓ Orchestrator"
curl -s http://localhost:8001/health && echo "✓ HealthAgent"
curl -s http://localhost:8002/health && echo "✓ DiagnosisAgent"

# Get workflow info
curl http://localhost:8000/workflow-info | jq

# Run all 4 story tests
python tests/test_e2e_all_stories.py
```
pytest tests/test_agents_integration.py -v

# Full end-to-end (requires AWS + may create real records)
pytest tests/test_workflow_e2e.py -v --run-e2e

# All tests
pytest tests/ -v
```

---

## 8. Migration to AgentCore Runtime

### What Changes When Moving to AWS

| Aspect | Local | AgentCore Runtime |
|--------|-------|-------------------|
| Where agents run | Your machine (Python process) | AWS managed containers |
| Where GatewayClient runs | Inside agent process | Inside agent container (same) |
| Config source | `.agentcore.env` file | Environment variables / Secrets Manager |
| Data source | `data/generated/*.json` | S3 bucket |
| LLM calls | Azure OpenAI API | Azure OpenAI API (same) |

### Code Changes Required

**Almost none.** The GatewayClient code stays identical:

```python
# This works BOTH locally and in AgentCore Runtime
import os

COGNITO_CLIENT_ID = os.getenv("COGNITO_APP_CLIENT_ID")
COGNITO_CLIENT_SECRET = os.getenv("COGNITO_APP_CLIENT_SECRET")
# ... etc
```

**Only deployment config changes:**
- Dockerfile packages your code
- AgentCore Runtime injects environment variables
- IAM role provides AWS permissions

### Container Architecture (AgentCore Runtime)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AgentCore Runtime (AWS)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 1. Orchestrator Container                                            │   │
│  │                                                                     │   │
│  │  FastAPI + LangGraph workflow                                       │   │
│  │  Calls agent services via internal HTTP                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                          │                    │                             │
│                          ▼                    ▼                             │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐          │
│  │ 2. HealthAgent Container    │  │ 3. DiagnosisAgent Container │          │
│  │                             │  │                             │          │
│  │  /app/src/gateway/client.py │  │  /app/src/gateway/client.py │          │
│  │  /app/src/agents/health_    │  │  /app/src/agents/diagnosis_ │          │
│  │          agent.py           │  │          agent.py           │          │
│  │                             │  │                             │          │
│  │  [In-memory token cache]    │  │  [In-memory token cache]    │          │
│  └─────────────────────────────┘  └─────────────────────────────┘          │
│               │                             │                               │
│               └─────────────────────────────┘                               │
│                             │                                               │
│                             ▼                                               │
│                    ┌─────────────────────┐                                 │
│                    │ AgentCore Gateway   │  (MCP Tools)                    │
│                    └─────────────────────┘                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Summary: Why This Design Works

1. **3 containers** — Orchestrator + 2 Agent services
2. **Each container is self-sufficient** — no shared state needed
3. **Token caching is per-process** — fine, tokens are cheap
4. **Same code locally and in AWS** — only config source changes
5. **No changes for runtime migration** — just containerize and deploy

---

## Quick Reference

### Run with Docker Compose

```bash
# Build and run all 3 containers
docker-compose up --build

# Test the workflow
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"device_id": "device-001", "temperature": 98, "vibration_level": "high"}'

# View logs
docker compose logs -f orchestrator
docker compose logs -f health-agent
docker compose logs -f diagnosis-agent

# Stop
docker compose down
```

---

## 9. Documentation & Testing Resources

### Complete Documentation Index

All documentation is available to guide you through implementation, testing, and deployment:

| Guide | Purpose | Best For |
|-------|---------|----------|
| [START_HERE.md](START_HERE.md) | Main entry point with overview | First time users |
| [QUICK_REFERENCE_CARD.md](QUICK_REFERENCE_CARD.md) | One-page command reference | Quick lookups while testing |
| [DOCKER_E2E_QUICK_START.md](DOCKER_E2E_QUICK_START.md) | Step-by-step getting started | Running tests quickly |
| [WEEK2_DAY5_7_COMPLETE.md](WEEK2_DAY5_7_COMPLETE.md) | Full implementation details | Understanding the complete system |
| [IMPLEMENTATION_WEEK2_DAY5_7_DOCKER_E2E.md](IMPLEMENTATION_WEEK2_DAY5_7_DOCKER_E2E.md) | Technical implementation summary | Developers making changes |
| [README_DOCKER_E2E_TESTING.md](README_DOCKER_E2E_TESTING.md) | Component index and overview | Project overview and navigation |
| [FINAL_DELIVERY_SUMMARY.md](FINAL_DELIVERY_SUMMARY.md) | What's delivered and status | Project completion verification |
| [COMPLETION_STATUS.txt](COMPLETION_STATUS.txt) | Completion checklist | Pre-deployment verification |

### Testing Scripts Available

| Script | Purpose | Command |
|--------|---------|---------|
| `scripts/run_e2e_tests.sh` | Full automation (build + start + test) | `bash scripts/run_e2e_tests.sh test` |
| `scripts/run_manual_e2e_test.py` | Manual HTTP testing of 4 stories | `python scripts/run_manual_e2e_test.py` |
| `tests/test_e2e_all_stories.py` | Async pytest test suite | `python tests/test_e2e_all_stories.py` |
| `scripts/preflight_check.sh` | Verify setup before deployment | `bash scripts/preflight_check.sh` |

### Quick Start (10 Seconds)

```bash
cd /home/skroy/AGENTIC_AI_POC_Phase3_1
bash scripts/run_e2e_tests.sh test
```

This will build, start, and test all services in one command.

### Success Verification

All components are ready when:
- ✅ Services start: `docker-compose up -d --build`
- ✅ Services are healthy: `curl http://localhost:8000/health`
- ✅ All 4 stories pass: Happy Path, Simple Issue, Ambiguous, Emergency
- ✅ Response times meet targets (80-450ms)
- ✅ No errors in logs: `docker-compose logs`

When all items above are complete, system is ready for AWS deployment.

---

**Status: ✅ READY FOR TESTING AND DEPLOYMENT**

### Test GatewayClient Standalone (before Docker)

```bash
# Ensure .agentcore.env is populated
source venv/bin/activate

# Test GatewayClient
python -c "from src.gateway.client import GatewayClient; g = GatewayClient(); print(g.list_tools())"
```

### Key Environment Variables

```bash
# Required for tool calls
COGNITO_APP_CLIENT_ID=...
COGNITO_APP_CLIENT_SECRET=...
COGNITO_TOKEN_ENDPOINT=https://agentic-ai-poc-3-1-auth.auth.us-east-1.amazoncognito.com/oauth2/token
COGNITO_SCOPE=agentcore/invoke
GATEWAY_URL=https://agenticai-poc-3-1-mcp-gateway-kvxs7ruhsl.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp

# Required for LLM (Azure OpenAI)
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT_NAME=<your-deployment>  # e.g., gpt-4
```

---

*Document created: June 10, 2026*
