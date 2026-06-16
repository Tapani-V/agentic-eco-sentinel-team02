# Phase 3: Complete Agent Integration with MCP Tools & AWS Backend
## WEEK 2 - Complete End-to-End Workflow

---

## Executive Summary

This document consolidates the complete architecture, MCP tool integration, AWS service connectivity, and deployment strategy for the Agentic AI POC Phase 3.

**Key Architectural Decisions:**
- **Core + Wrapper Pattern**: Separation of business logic (src/agents, src/graph) from HTTP transport (src/services)
- **MCP Tool Integration**: All agents call AWS MCP Gateway via Cognito OAuth 2.0 client_credentials flow
- **AWS Backend**: S3 (spare parts), DynamoDB (maintenance schedule), Lambda (maintenance execution)
- **Local Testing**: Docker Compose with 3 containers (Orchestrator, HealthAgent, DiagnosisAgent)
- **Service Communication**: HTTP-based (httpx) on isolated Docker network

---

## Architecture Overview

### Component Topology

```
┌─────────────────────────────────────────────────────────────────────┐
│                    REQUEST ENTRY POINT                             │
│              Orchestrator Service (Port 8000)                      │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
         ▼             ▼             ▼
    ┌────────┐    ┌─────────┐   ┌──────────┐
    │Node: HA│    │Node:    │   │Node:     │
    │   (HA) │───▶│Router   │──▶│  Agg.    │
    └────────┘    └────┬────┘   └──────────┘
         │             │
         │    ┌────────▼─────────┐
         │    │Node: DA (Diag)   │
         │    │ - Pattern Match  │
         │    │ - Confidence     │
         │    │ - LLM Reasoning  │
         │    │ - MCP Tool Call  │
         └───▶└──────────────────┘
              (Returns to Agg.)

         HTTP Boundaries:
         - HealthAgent:     http://health-agent:8001
         - DiagnosisAgent:  http://diagnosis-agent:8002
         - Gateway/MCP:     AWS MCP Gateway (Cognito authenticated)
```

### Service Stack

| Service | Port | Purpose | MCP Tools |
|---------|------|---------|-----------|
| **Orchestrator** | 8000 | LangGraph workflow orchestration (4-node) | None (coordination only) |
| **HealthAgent** | 8001 | Threshold-based health classification | create-work-order (on critical) |
| **DiagnosisAgent** | 8002 | Root cause analysis with pattern matching | create-work-order, schedule-maintenance, get-spare-parts |

---

### DiagnosisAgent Decision Logic (Simplified Model)

**Design Principle**: Clean two-layer decision process with mandatory parts validation before scheduling.

```
STEP 1: MATCH PATTERNS
├─ Load equipment-specific rules
├─ Calculate confidence (0.0-1.0)
└─ Pick best matching pattern

STEP 2: CONFIDENCE CHECK (Single Threshold: 0.85)
├─ if confidence >= 0.85:
│  └─ TRUST RULE → use recommended action directly
└─ if confidence < 0.85:
   └─ CALL LLM → get AI judgment for action

STEP 3: VALIDATE & EXECUTE ACTION (3 Possible Actions)
├─ URGENT_REPAIR
│  └─ Create critical work order immediately
├─ SCHEDULE_MAINTENANCE
│  ├─ Check spare parts availability (automatic validation)
│  ├─ If parts available → schedule maintenance (3-7 days)
│  └─ If parts unavailable → create procurement work order
└─ MONITOR_ONLY
   └─ Defer action, recommend re-check in 8 hours
```

**Key Points:**
1. **Single confidence threshold (0.85)**: Not 0.72, not multiple bands — just: trust or ask LLM?
2. **Mandatory parts validation**: SCHEDULE_MAINTENANCE **always** checks spare parts first, regardless of confidence source
3. **If parts unavailable**: Escalates to procurement instead of scheduling work that can't proceed
4. **If parts available**: Schedules immediately with parts confirmed in inventory
5. **LLM called for ambiguity**, not for parts checking: LLM provides AI judgment; parts validation is mechanical

---



### Overview

MCP (Model Context Protocol) tools enable agents to interact with backend AWS services:

1. **Tool Invocation**: Via `GatewayClient.call_tool(tool_name, arguments)`
2. **Authentication**: Cognito OAuth 2.0 client_credentials flow
3. **Token Caching**: In-memory cache (1-hour TTL) to minimize Cognito calls
4. **Error Handling**: Graceful degradation - tool failures don't break workflow

### Tool Definitions

#### 1. create-work-order

**Purpose**: Create maintenance/repair work orders in the ticketing system

**When Called**:
- DiagnosisAgent: URGENT_REPAIR action (confidence ≥ 0.85 or critical device state)
- HealthAgent: When health_status = "critical"

**Arguments**:
```python
{
    "device_id": "PUMP-001",
    "equipment_type": "centrifugal_pump",
    "priority": "CRITICAL",           # CRITICAL | HIGH | MEDIUM | LOW
    "severity": "CRITICAL",            # CRITICAL | HIGH | MEDIUM | LOW
    "source": "DiagnosisAgent",        # Originating component
    "issue_description": "Root cause identified: bearing failure",
    "requested_by": "Agent-RCA-001"
}
```

**Returns**:
```json
{
    "work_order_id": "WO-2024-001234",
    "device_id": "PUMP-001",
    "status": "CREATED",
    "created_timestamp": "2024-01-15T10:30:00Z",
    "assigned_to": "technician_123"
}
```

**AWS Integration**: Creates ticket in ServiceNow/Jira via Lambda webhook

---

#### 2. schedule-maintenance

**Purpose**: Schedule preventive maintenance tasks in DynamoDB

**When Called**: 
- DiagnosisAgent: SCHEDULE_MAINTENANCE action (after mandatory spare parts validation)

**Arguments**:
```python
{
    "device_id": "PUMP-001",
    "equipment_type": "centrifugal_pump",
    "maintenance_type": "bearing_replacement",
    "scheduled_date": "2024-01-20",    # YYYY-MM-DD
    "priority": "HIGH",
    "estimated_duration_hours": 4,
    "required_parts": ["bearing_part_no_123", "seal_kit_456"],
    "notes": "Bearing showing degradation, schedule before failure"
}
```

**Returns**:
```json
{
    "schedule_id": "SCH-2024-005678",
    "device_id": "PUMP-001",
    "scheduled_date": "2024-01-20",
    "status": "SCHEDULED",
    "assigned_crew": "Team-B"
}
```

**AWS Integration**: 
- DynamoDB: Writes to `agentic-maintenance-schedule` table
- EventBridge: Triggers Lambda at scheduled date for automated execution
- Lambda: `agentic-scheduled-maintenance-executor` function handles execution

---

#### 3. get-spare-parts

**Purpose**: Query available spare parts inventory from S3

**When Called**:
- DiagnosisAgent: **Mandatory validation before SCHEDULE_MAINTENANCE action** (checks parts availability to determine if maintenance can proceed)

**Arguments**:
```python
{
    "equipment_type": "centrifugal_pump",
    "part_type": "bearing",
    "include_specifications": true
}
```

**Returns**:
```json
{
    "parts": [
        {
            "part_number": "bearing_part_no_123",
            "description": "Deep groove ball bearing 6205",
            "quantity_available": 12,
            "location": "Warehouse-A, Shelf-C-3",
            "unit_cost": 45.50,
            "lead_time_days": 0,
            "supplier": "SKF"
        },
        {
            "part_number": "seal_kit_456",
            "description": "Mechanical seal kit for PUMP-001",
            "quantity_available": 5,
            "location": "Warehouse-A, Shelf-D-1",
            "unit_cost": 125.00,
            "lead_time_days": 0,
            "supplier": "Flowserve"
        }
    ],
    "query_timestamp": "2024-01-15T10:30:00Z"
}
```

**AWS Integration**: 
- S3 Bucket: `agentic-ai-spare-parts/spare-parts/`
- Lambda Function: Reads parts catalog from S3 and queries inventory database
- Format: JSON files organized by equipment type

---

### GatewayClient Implementation

**Location**: `src/gateway/client.py`

**Responsibilities**:
1. Obtain Cognito tokens (client_credentials flow)
2. Cache tokens with TTL management
3. Call MCP tools via HTTP (POST to MCP Gateway)
4. Handle errors gracefully

**Key Methods**:

```python
class GatewayClient:
    def __init__(self):
        """Initialize with Cognito credentials from environment"""
        # Reads: COGNITO_DOMAIN, COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET
        # Initializes: token cache, expiry tracking
        
    def call_tool(self, tool_name: str, arguments: Dict) -> Dict:
        """
        Call an MCP tool with automatic token management
        
        Args:
            tool_name: 'create-work-order', 'schedule-maintenance', 'get-spare-parts'
            arguments: Dict of tool parameters
            
        Returns:
            Tool response or error dict with graceful degradation
            
        Token Caching:
            - First call: Requests token from Cognito
            - Subsequent calls (within TTL): Uses cached token
            - Token refresh: Automatic when < 5 min until expiry
        """
```

**Error Handling**:
- Cognito connection failure → Cached token if available, else error dict
- Tool invocation timeout → Error dict with status='error'
- Invalid tool name → Error dict with status='invalid_tool'
- All errors logged but don't crash workflow

---

## Agent Implementations

### HealthAgent (Port 8001)

**Purpose**: Local threshold-based health classification with critical escalation

**Input**:
```python
{
    "device_id": "PUMP-001",
    "equipment_type": "centrifugal_pump",
    "sensor_data": {
        "temperature_celsius": 85.5,
        "vibration_mm_s": 5.2,
        "pressure_bar": 42.3,
        "flow_gpm": 1200
    },
    "anomaly_scores": {
        "temperature_high": 0.8,
        "vibration_high": 0.9,
        "pressure_abnormal": 0.4
    }
}
```

**Processing (6 Steps)**:

1. **Anomaly Aggregation**: Combine sensor anomalies into list
2. **Threshold Evaluation**: Compare against predefined baselines
3. **Degradation Score**: Calculate weighted health score (0.0-1.0)
   - temperature_high (>90°C): +0.25
   - vibration_high (>4.5 mm/s): +0.45
   - pressure issues: +0.12
   - flow anomalies: +0.10
4. **Health Classification**:
   - score < 0.3: "healthy"
   - score 0.3-0.7: "warning"
   - score ≥ 0.7: "critical"
5. **Response Construction**: Health status + anomalies + score
6. **MCP Escalation** (**NEW**): If health_status = "critical"
   - Call `_call_critical_work_order(device_id, equipment_type, anomalies)`
   - MCP Tool: `create-work-order` with priority=CRITICAL
   - Include tool_results in response

**Output**:
```python
{
    "device_id": "PUMP-001",
    "health_status": "critical",
    "degradation_score": 0.75,
    "anomalies": ["temperature_high: 85.5°C", "vibration_high: 5.2 mm/s"],
    "requires_diagnosis": true,
    "tool_results": {
        "create-work-order": {
            "work_order_id": "WO-2024-001234",
            "status": "CREATED"
        }
    }
}
```

**Code Location**: `src/agents/health_agent.py`
- Class: `HealthAgent`
- Key Methods: 
  - `execute()` - Main analysis with MCP escalation logic
  - `_compute_degradation_score()` - Weighted scoring
  - `_call_critical_work_order()` - **NEW** - MCP critical escalation

---

### DiagnosisAgent (Port 8002)

**Purpose**: Root cause analysis with pattern matching, LLM reasoning, and MCP tool execution

**4-Step Root Cause Analysis**:

1. **Pattern Recognition**: Match symptoms to known failure patterns
   ```python
   patterns = {
       "bearing_failure": {
           "symptoms": ["vibration_high", "temperature_high"],
           "confidence_base": 0.7
       },
       "cavitation": {
           "symptoms": ["pressure_abnormal", "vibration_spike"],
           "confidence_base": 0.6
       },
       "wear": {
           "symptoms": ["flow_degradation", "efficiency_low"],
           "confidence_base": 0.5
       }
   }
   ```

2. **Confidence Scoring**: Adjust based on anomaly magnitudes and sensor agreement
   - Base pattern confidence × (1 + anomaly_severity_factor)
   - Cap at 1.0

3. **LLM-Based Reasoning** (OpenAI GPT-4):
   ```
   Prompt: "Given symptoms: [list], confidence [score], 
            suggest root cause, recommended action, 
            required spare parts, maintenance timeline"
   ```
   - Temperature + vibration → bearing failure → 0.85 confidence
   - Returns: root_cause, action_plan, parts_needed, timeline

4. **MCP Tool Execution** (Conditional):
   - If confidence ≥ 0.7: Call `create-work-order`
   - If confidence ≥ 0.6 and maintenance_type detected: Call `schedule-maintenance`
   - Call `get-spare-parts` to check availability

**Output**:
```python
{
    "device_id": "PUMP-001",
    "root_cause": "bearing_failure",
    "confidence": 0.85,
    "reasoning": "High vibration + temperature indicates bearing wear...",
    "recommended_action": "Replace bearing immediately",
    "required_parts": ["bearing_part_no_123", "seal_kit_456"],
    "parts_availability": {
        "bearing_part_no_123": {"qty": 12, "location": "Warehouse-A"},
        "seal_kit_456": {"qty": 5, "location": "Warehouse-A"}
    },
    "maintenance_timeline": "Schedule within 24 hours",
    "tool_results": {
        "create-work-order": {
            "work_order_id": "WO-2024-001234",
            "status": "CREATED"
        },
        "get-spare-parts": {
            "parts": [...]
        }
    }
}
```

**Code Location**: `src/agents/diagnosis_agent.py`
- Class: `DiagnosisAgent`
- Key Methods:
  - `execute()` - 4-step root cause analysis with MCP tool calls
  - `_match_patterns()` - Pattern recognition engine
  - `_score_confidence()` - Confidence calculation
  - `_execute_action()` - MCP tool invocation (create-work-order, schedule-maintenance, get-spare-parts)

---

## Cognito Authentication Flow

### OAuth 2.0 Client Credentials Grant

```
┌──────────────────┐
│  GatewayClient   │
│   (Agent)        │
└────────┬─────────┘
         │ 1. Request token
         │ (client_id, client_secret)
         ▼
┌──────────────────────────────────────────┐
│        AWS Cognito User Pool             │
│   /oauth2/token endpoint                 │
│   grant_type: client_credentials         │
└────────┬─────────────────────────────────┘
         │ 2. Return access_token + TTL
         ▼
┌──────────────────┐
│ Token Cache      │
│ (1 hour TTL)     │
│ Refresh at 5min  │
│ before expiry     │
└────────┬─────────┘
         │ 3. Use token for tool calls
         ▼
┌──────────────────────────────────┐
│    AWS MCP Gateway               │
│  (API Gateway + Lambda)          │
│  Authorization: Bearer {token}   │
│  POST /tools/{tool_name}         │
└──────────────────────────────────┘
```

### Token Caching Strategy

- **Initial Request**: Call Cognito to get fresh token + expiry time
- **Cached Usage**: Reuse token until `expiry_time - 5_minutes`
- **Auto-Refresh**: Request new token automatically at 5-min before expiry
- **Fallback**: Use stale token if Cognito unreachable (graceful degradation)

**Implementation**: `src/gateway/client.py` - `_get_or_refresh_token()` method

---

## Docker Compose Orchestration

### Service Configuration

**File**: `docker-compose.yml`

**Services**:

1. **orchestrator** (Port 8000)
   - Entry point for all requests
   - LangGraph workflow execution
   - Coordinates HealthAgent and DiagnosisAgent calls
   - Environment: AWS credentials, service URLs

2. **health-agent** (Port 8001)
   - Lightweight local analysis
   - Immediate critical escalation
   - MCP tool call: create-work-order (when critical)
   - Health check: `/health` endpoint

3. **diagnosis-agent** (Port 8002)
   - Root cause analysis
   - Pattern matching + LLM reasoning
   - All 3 MCP tools: create-work-order, schedule-maintenance, get-spare-parts
   - Health check: `/health` endpoint

**Network**: `agentic-network` (internal bridge)
- All services communicate via HTTP on Docker network
- External access only through port 8000 (orchestrator)

**Environment Variables** (from `.agentcore.env`):
```
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
COGNITO_DOMAIN=https://...
COGNITO_CLIENT_ID=...
COGNITO_CLIENT_SECRET=...
MCP_GATEWAY_URL=...
OPENAI_API_KEY=...
```

### Launch & Stop

```bash
# Launch all services
docker-compose up -d

# View logs
docker-compose logs -f orchestrator
docker-compose logs -f health-agent
docker-compose logs -f diagnosis-agent

# Stop services
docker-compose down
```

---

## AWS Backend Architecture

### S3: Spare Parts Inventory

**Bucket**: `agentic-ai-spare-parts`

**Structure**:
```
s3://agentic-ai-spare-parts/
├── spare-parts/
│   ├── centrifugal_pump/
│   │   ├── bearings.json
│   │   ├── seals.json
│   │   └── shafts.json
│   ├── electric_motor/
│   │   ├── windings.json
│   │   └── bearings.json
│   └── compressor/
│       ├── valves.json
│       └── impellers.json
```

**Example File** (`bearings.json`):
```json
{
  "parts": [
    {
      "part_number": "bearing_123",
      "description": "Deep groove ball bearing 6205",
      "category": "bearing",
      "quantity_available": 12,
      "warehouse_location": "Warehouse-A, Shelf-C-3",
      "unit_cost": 45.50,
      "supplier": "SKF",
      "lead_time_days": 0,
      "equipment_type": "centrifugal_pump"
    }
  ]
}
```

**Access**: Lambda function queries S3 via `get-spare-parts` MCP tool

---

### DynamoDB: Maintenance Schedule

**Table**: `agentic-maintenance-schedule`

**Schema**:
```
Primary Key: device_id (Partition Key) + scheduled_date (Sort Key)

Attributes:
- device_id (String, PK)
- scheduled_date (String, SK) - YYYY-MM-DD
- maintenance_type (String) - bearing_replacement, seal_change, etc.
- priority (String) - CRITICAL, HIGH, MEDIUM, LOW
- status (String) - SCHEDULED, IN_PROGRESS, COMPLETED, CANCELLED
- assigned_crew (String)
- estimated_duration_hours (Number)
- required_parts (List of Strings)
- created_timestamp (String, ISO 8601)
- completion_timestamp (String, optional)
- notes (String)

Global Secondary Indexes:
- device_id-status-index: Query by device and status
- scheduled_date-index: Query upcoming maintenance
```

**Access**:
- Write: `schedule-maintenance` MCP tool (DiagnosisAgent)
- Read: Scheduled maintenance queries
- Update: Lambda execution updates status
- Delete: Completed maintenance archival

---

### Lambda: Scheduled Maintenance Executor

**Function**: `agentic-scheduled-maintenance-executor`

**Trigger**: EventBridge Rule
```
Schedule: Cron expression for daily maintenance check
   cron(0 8 * * ? *)  # Run at 8 AM daily

Target: Lambda function with DynamoDB events
```

**Behavior**:
1. Query DynamoDB for today's scheduled maintenance
2. For each scheduled item:
   - Verify parts availability (call S3)
   - Notify assigned crew (SNS)
   - Update status to "IN_PROGRESS"
3. Log execution in CloudWatch

**Output**: 
```python
{
    "processed_maintenance": 3,
    "successful": 2,
    "failed": 1,
    "timestamp": "2024-01-15T08:00:00Z"
}
```

---

## Testing Strategy

### Story-Based Testing

Each of the 4 test stories validates different workflow paths:

#### Story 1: Healthy Device
- Input: Normal sensor readings, no anomalies
- Expected Flow: HealthAgent → healthy status → No DiagnosisAgent call
- Assertions:
  - health_status = "healthy"
  - No MCP tools called
  - Response time < 500ms

#### Story 2: Simple Root Cause
- Input: Bearing failure symptoms (high vibration + temperature)
- Expected Flow: HealthAgent → warning → DiagnosisAgent → bearing_failure → create-work-order
- Assertions:
  - DiagnosisAgent called
  - root_cause = "bearing_failure"
  - Work order created via MCP tool
  - get-spare-parts called

#### Story 3: Ambiguous Symptoms
- Input: Mixed symptoms (pressure + flow + temperature)
- Expected Flow: HealthAgent → warning → DiagnosisAgent → confidence < 0.85 → LLM judgment → SCHEDULE_MAINTENANCE → parts validation
- Assertions:
  - DiagnosisAgent called
  - LLM consulted (confidence < 0.85)
  - Spare parts validated before scheduling
  - Maintenance scheduled if parts available, escalated if not

#### Story 4: Critical Escalation
- Input: Multiple high-severity anomalies
- Expected Flow: HealthAgent → critical → create-work-order (immediate) → also DiagnosisAgent
- Assertions:
  - HealthAgent calls create-work-order directly
  - Tool_results returned in HealthAgent response
  - DiagnosisAgent performs full analysis
  - Both agents contribute to resolution

### Integration Test Script

**Location**: `tests/test_integration.py` (to be created)

**Test Cases**:
```python
def test_story_1_healthy_device():
    """Verify healthy device does not trigger diagnosis"""
    response = post("/process", {
        "device_id": "PUMP-001",
        "sensor_data": {...}
    })
    assert response["health_status"] == "healthy"
    assert response["tool_results"] == {}

def test_story_2_simple_diagnosis():
    """Verify bearing failure is correctly diagnosed and work order created"""
    response = post("/process", {...})
    assert response["diagnosis"]["root_cause"] == "bearing_failure"
    assert "WO-" in response["tool_results"]["create-work-order"]["work_order_id"]

def test_story_3_ambiguous():
    """Verify low-confidence diagnosis triggers maintenance scheduling"""
    response = post("/process", {...})
    assert 0.5 < response["diagnosis"]["confidence"] < 0.7
    assert "schedule-maintenance" in response["tool_results"]

def test_story_4_critical():
    """Verify critical status triggers immediate work order AND diagnosis"""
    response = post("/process", {...})
    assert response["health_status"] == "critical"
    assert "create-work-order" in response["health_results"]["tool_results"]
    assert response["diagnosis"]["root_cause"] is not None
```

### End-to-End Workflow Test

**Location**: `tests/test_e2e.py` (to be created)

**Scenario**: Complete workflow from device anomaly to maintenance execution
```
1. Send device anomaly to Orchestrator (POST /process)
2. Verify HealthAgent response (health_status, degradation_score)
3. For critical: Verify immediate work order creation
4. Verify DiagnosisAgent root cause analysis
5. Verify MCP tool calls (all 3 tools if applicable)
6. Query DynamoDB for maintenance schedule (verify entry created)
7. Verify S3 spare parts inventory was queried
8. Verify work order created in ticketing system (mock)
9. Assert all HTTP response times < acceptable thresholds
```

---

## Phase 3.1 Enhancement: Dashboard Intelligence & Agent Tracking

### Recommendation Fields

The orchestration system now generates rich recommendation fields for dashboard display:

#### Fields Added to All Responses

```json
{
  "insights": "Rule-Based Analysis: Device is in critical condition. Pump valve wear - pressure unstable with high vibration. Continued operation poses safety/reliability risks.",
  "immediate_actions": [
    "Stop PUMP operations immediately",
    "Isolate equipment from production line",
    "Inspect for visible damage or wear",
    "Replace critical components (bearings/seals/valves)",
    "Run full diagnostics before restart"
  ],
  "predicted_failure_date": "2026-06-12T17:14:17.291542",
  "recommendation_details": "URGENT: Pump valve wear - pressure unstable with high vibration. Equipment failure is imminent. Immediate emergency repair required to prevent catastrophic failure and production loss."
}
```

#### Recommendation Logic by Action Type

| Action | Analysis Source | Timeline | Actions |
|--------|-----------------|----------|---------|
| **URGENT_REPAIR** | Rule-Based (critical status) | Immediate | Stop ops, isolate, inspect, replace components, re-diagnose |
| **SCHEDULE_MAINTENANCE** | Rule-Based or LLM-based | 3-7 days | **Validate spare parts first** → If available: schedule maintenance; If unavailable: escalate to procurement |
| **MONITOR_ONLY** | LLM-based (low confidence) | Ongoing | Continue operations, routine inspections, re-check in 8 hours with escalation thresholds |

#### Implementation Details

- **Location**: `src/agents/diagnosis_agent.py` - `_build_recommendations()` method
- **Triggered**: Automatically after DiagnosisAgent root cause analysis
- **Parts Extraction**: Anomalies analyzed to recommend specific parts (bearings, seals, valves)
- **Propagation**: Flows through workflow → orchestrator response → API clients

#### Semantic Clarity: `llm_used` Flag vs `insights` Field

**Important Distinction:**

| Concept | Meaning | Example |
|---------|---------|---------|
| **`llm_used: bool`** | Was LLM invoked to **determine** which action to take? | Critical device: `false` (action forced by escalation rule, not LLM) |
| **`insights: string`** | **Analysis reasoning** explaining why this action was chosen | Always populated, shows "Rule-Based Analysis:" or "LLM-based Analysis:" prefix |

**Example - Critical Device (URGENT_REPAIR):**
```json
{
  "llm_used": false,
  "insights": "Rule-Based Analysis: Device is in critical condition. Compressor thermal stress - possible valve issue. Continued operation poses safety/reliability risks."
}
```
✅ Semantically clear: Action was forced by critical status (not LLM), but we provide rule-based reasoning

**Example - Warning Device with LLM Check:**
```json
{
  "llm_used": true,
  "insights": "LLM-based Analysis: Device showing degradation patterns. Pump valve wear - pressure unstable with high vibration. Proactive maintenance can prevent failure."
}
```
✅ Semantically clear: LLM was consulted because confidence < 0.85, and it determined this action

---

### Agent & Tool Usage Tracking

New endpoints provide visibility into which agents and MCP tools are invoked:

#### New Endpoints

**1. GET /agents-trace/{device_id}**
- Returns full request history for a specific device
- Shows which agents/tools used in each analysis

Example:
```bash
curl http://localhost:8000/agents-trace/pump-004
```

Response:
```json
{
  "device_id": "pump-004",
  "total_requests": 1,
  "requests": [
    {
      "timestamp": "2026-06-12T17:05:45.009446",
      "agents_used": ["HealthAgent", "DiagnosisAgent"],
      "mcp_tools_used": ["create-work-order"],
      "action": "URGENT_REPAIR",
      "health_status": "critical",
      "path": "full_diagnosis"
    }
  ]
}
```

**2. GET /agents-summary**
- Aggregates statistics across all devices
- Shows routing patterns and tool usage distribution

Example:
```bash
curl http://localhost:8000/agents-summary
```

Response:
```json
{
  "total_devices": 3,
  "devices": [
    {
      "device_id": "pump-004",
      "total_requests": 1,
      "agents_used": ["HealthAgent", "DiagnosisAgent"],
      "mcp_tools_used": ["create-work-order"],
      "routing_paths": {
        "health_only": 0,
        "full_diagnosis": 1
      },
      "actions_taken": {
        "URGENT_REPAIR": 1
      },
      "last_request": "2026-06-12T17:05:45.009446"
    }
  ]
}
```

#### Tracking Fields in Response

All endpoint responses now include:
- `agents_used`: List of agent names that were invoked (e.g., ["HealthAgent", "DiagnosisAgent"])
- `mcp_tools_used`: List of MCP tools that were called (e.g., ["create-work-order"])

#### Implementation Architecture

- **State Tracking**: `WorkflowState` TypedDict includes `agents_used[]` and `mcp_tools_used[]`
- **HealthAgent Node**: Appends "HealthAgent" when executed
- **DiagnosisAgent Node**: Appends "DiagnosisAgent" and extracts tool names from tool_results
- **Request History**: In-memory dictionary with 50-record limit per device (production: use Redis/DynamoDB)

---

## Configuration & Deployment

### Local Development Setup

1. **Copy environment template**:
   ```bash
   cp .agentcore.env.template .agentcore.env
   ```

2. **Fill in AWS credentials**:
   ```
   AWS_ACCESS_KEY_ID=your_key
   AWS_SECRET_ACCESS_KEY=your_secret
   COGNITO_DOMAIN=your_domain
   COGNITO_CLIENT_ID=your_client_id
   COGNITO_CLIENT_SECRET=your_secret
   OPENAI_API_KEY=your_openai_key
   ```

3. **Build and launch**:
   ```bash
   docker-compose up -d
   docker-compose logs -f
   ```

4. **Verify services**:
   ```bash
   curl http://localhost:8000/health    # Orchestrator
   curl http://localhost:8001/health    # HealthAgent
   curl http://localhost:8002/health    # DiagnosisAgent
   ```

5. **Test recommendation fields**:
   ```bash
   curl http://localhost:8000/devices/pump-004 | jq '.recommendation_details'
   ```

6. **Check agent tracking**:
   ```bash
   curl http://localhost:8000/agents-summary | jq '.devices[0].agents_used'
   ```

### Production Deployment

For AWS ECS/Fargate deployment:
- Use AWS Secrets Manager for credentials
- Enable CloudWatch logging per service
- Use Application Load Balancer for orchestrator endpoint
- Configure Auto Scaling based on request queue depth
- Enable X-Ray tracing for request correlation
- Replace in-memory request_history with DynamoDB for persistence

---

## Next Steps

1. ✅ **Completed**: MCP tool integration (all 3 tools in appropriate agents)
2. ✅ **Completed**: HealthAgent critical escalation to MCP
3. ✅ **Completed**: Docker Compose orchestration
4. ✅ **Completed (Phase 3.1)**: Recommendation fields for dashboard
5. ✅ **Completed (Phase 3.1)**: Agent & tool usage tracking endpoints
6. ⏳ **Pending**: Integration test script (`tests/test_integration.py`)
7. ⏳ **Pending**: End-to-end workflow test (`tests/test_e2e.py`)
8. ⏳ **Pending**: AWS Lambda deployment for maintenance executor
9. ⏳ **Pending**: Production configuration (ECS, CloudWatch, X-Ray)
10. ⏳ **Pending**: Persistent request history (DynamoDB backend)

---

## References

- **LangGraph Docs**: https://python.langchain.com/docs/langgraph
- **AWS MCP**: https://aws.amazon.com/blogs/machine-learning/
- **Cognito OAuth 2.0**: https://docs.aws.amazon.com/cognito/
- **FastAPI**: https://fastapi.tiangolo.com/
- **Docker Compose**: https://docs.docker.com/compose/
