# MCP Tool Integration - DiagnosisAgent

## Overview

The DiagnosisAgent now fully integrates MCP tool calls for executing maintenance actions. This is **STEP 4** of the 4-step diagnosis process.

---

## Architecture

```
DiagnosisAgent (Core Logic)
├── Step 1: Pattern Matching
├── Step 2: Confidence Check
├── Step 3: LLM Enhancement (if needed)
└── Step 4: Execute Action ← MCP TOOLS CALLED HERE
    └── GatewayClient (Cognito token + tool calls)
        ├── create-work-order
        ├── schedule-maintenance
        └── get-spare-parts
```

---

## MCP Tools Integrated

### 1. **create-work-order** (Action: URGENT_REPAIR)
**When:** Device has critical issue requiring immediate repair

```python
tool_result = gateway_client.call_tool(
    tool_name="create-work-order",
    arguments={
        "device_id": "pump-001",
        "equipment_type": "PUMP",
        "priority": "EMERGENCY",
        "issue_description": "Anomalies: temperature_high, vibration_critical",
        "requested_by": "DiagnosisAgent"
    }
)
```

**Response:**
```json
{
    "status": "success",
    "work_order_id": "WO-2026-06-12-001",
    "device_id": "pump-001",
    "priority": "EMERGENCY",
    "created_at": "2026-06-12T10:30:00Z"
}
```

---

### 2. **schedule-maintenance** (Action: SCHEDULE_MAINTENANCE)
**When:** Device needs planned preventive maintenance

```python
tool_result = gateway_client.call_tool(
    tool_name="schedule-maintenance",
    arguments={
        "device_id": "pump-001",
        "equipment_type": "PUMP",
        "maintenance_type": "preventive",
        "priority": "HIGH",
        "issue_description": "Anomalies: pressure_fluctuation",
        "scheduled_by": "DiagnosisAgent"
    }
)
```

**Response:**
```json
{
    "status": "success",
    "maintenance_id": "MAINT-2026-06-12-001",
    "device_id": "pump-001",
    "scheduled_date": "2026-06-15T08:00:00Z",
    "maintenance_type": "preventive"
}
```

---

### 3. **get-spare-parts** (Action: CHECK_PARTS_FIRST)
**When:** Need to verify spare parts availability before scheduling

```python
tool_result = gateway_client.call_tool(
    tool_name="get-spare-parts",
    arguments={
        "equipment_type": "PUMP",
        "component_type": "critical",
        "check_availability": True
    }
)
```

**Response:**
```json
{
    "status": "success",
    "equipment_type": "PUMP",
    "components": [
        {
            "component": "bearing_assembly",
            "available": True,
            "quantity": 5,
            "part_number": "PUMP-BEARING-001"
        },
        {
            "component": "seals",
            "available": False,
            "quantity": 0,
            "part_number": "PUMP-SEAL-002",
            "expected_delivery": "2026-06-20"
        }
    ]
}
```

---

## Cognito Token Flow

GatewayClient handles token management automatically:

```
1. Initialize: GatewayClient()
   └── Load credentials from .agentcore.env
   
2. First tool call:
   └── Request token via Cognito (client_credentials grant)
   └── Cache token with expiry
   
3. Subsequent calls:
   └── Use cached token if valid (with 5-min refresh buffer)
   └── Auto-refresh if near expiry
   └── Retry with fresh token if 401 error
```

---

## Error Handling

DiagnosisAgent catches and logs all MCP tool errors:

```python
try:
    tool_result = gateway_client.call_tool(...)
except GatewayError as e:
    logger.error(f"Gateway error: {e}")
except TokenError as e:
    logger.error(f"Token error: {e}")
except ToolCallError as e:
    logger.error(f"Tool call error: {e}")
```

All errors are returned in `action_result['tools']['error']` without breaking the workflow.

---

## Environment Setup

Required `.agentcore.env` variables:

```bash
# Cognito
COGNITO_APP_CLIENT_ID=your_client_id
COGNITO_APP_CLIENT_SECRET=your_client_secret
COGNITO_TOKEN_ENDPOINT=https://cognito-idp.region.amazonaws.com/oauth2/token
COGNITO_SCOPE=agentcore/invoke

# Gateway
GATEWAY_URL=https://your-gateway-url/rpc
```

---

## Code Structure

### DiagnosisAgent (`src/agents/diagnosis_agent.py`)

```python
class DiagnosisAgent(BaseAgent):
    def __init__(self):
        self.gateway_client = None  # Lazy initialized
    
    async def _execute_action(self, ...):
        """
        STEP 4: Execute action with MCP tools
        
        - Initializes GatewayClient on first use
        - Calls appropriate tool based on action type
        - Returns tool results in response
        - Handles errors gracefully
        """
        if not self.gateway_client:
            self.gateway_client = GatewayClient()
        
        if action == 'URGENT_REPAIR':
            tool_result = self.gateway_client.call_tool(
                "create-work-order",
                {...}
            )
        # ... other actions
```

### Orchestrator Flow

```
Orchestrator (/process)
  ↓
Calls → HealthAgent Service
  ↓
Router checks → health_status
  ↓
If not healthy → Calls DiagnosisAgent Service
  ↓
DiagnosisAgent.execute()
  - Step 1: Pattern matching ✅
  - Step 2: Confidence check ✅
  - Step 3: LLM (future)
  - Step 4: Execute action ← MCP TOOLS CALLED HERE
    └── GatewayClient.call_tool()
  ↓
Returns action_result with tool_results to Orchestrator
  ↓
Orchestrator aggregates and returns to client
```

---

## Testing

### Local Testing (Without AWS)
Tools will fail gracefully with appropriate error messages if .agentcore.env is not configured:

```bash
# This should work (without actual tool calls)
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "pump-001",
    "equipment_type": "PUMP",
    "current_reading": {"readings": {...}}
  }'
```

### Integration Testing (With AWS)
When .agentcore.env is configured:

```bash
# Real tool calls executed
pytest tests/test_mcp_integration.py
```

---

## Status

✅ **Completed:**
- [x] GatewayClient integration
- [x] Tool call structure (create-work-order, schedule-maintenance, get-spare-parts)
- [x] Error handling
- [x] Token caching
- [x] Cognito flow

⏳ **Next:**
- [ ] Integration tests with mock tools
- [ ] Full end-to-end test with AWS
- [ ] docker-compose.yml for local testing
- [ ] LLM integration (Step 3)

