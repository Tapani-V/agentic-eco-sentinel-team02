# Phase 3.1 Update: Dashboard Intelligence & Multi-Agent Visibility

**Date**: June 12, 2026  
**Status**: ✅ Complete and Tested

---

## Overview

Phase 3.1 extends the core agent architecture with two major features:
1. **Rich Recommendation Fields** for dashboard display
2. **Multi-Agent Tracking** endpoints for workflow visibility

---

## Feature 1: Recommendation Fields

### What Changed

All API responses now include action-specific recommendations for operations teams.

### New Response Fields

```json
{
  "llm_insights": "string - LLM's interpretation of findings",
  "immediate_actions": ["array", "of", "actionable", "steps"],
  "predicted_failure_date": "2026-06-12T17:14:17.291542",  // null for healthy devices
  "recommendation_details": "string - detailed maintenance explanation"
}
```

### Examples by Action Type

**URGENT_REPAIR** (Critical):
```json
{
  "predicted_failure_date": "2026-06-12T17:14:17.291542",  // Immediate
  "immediate_actions": [
    "Stop PUMP operations immediately",
    "Isolate equipment from production line",
    "Inspect for visible damage or wear",
    "Replace critical components (bearings/seals/valves)",
    "Run full diagnostics before restart"
  ],
  "recommendation_details": "URGENT: Equipment failure is imminent. Immediate emergency repair required..."
}
```

**SCHEDULE_MAINTENANCE** (Warning):
```json
{
  "predicted_failure_date": "2026-06-26T17:14:36.550470",  // 14 days out
  "immediate_actions": [
    "Schedule preventive maintenance window (1-2 weeks)",
    "Order necessary replacement parts (valves)",
    "Notify operations of planned downtime",
    "Prepare maintenance crew and tools",
    "Monitor equipment closely until maintenance window"
  ],
  "recommendation_details": "PREVENTIVE: Schedule maintenance within 2 weeks to address degradation..."
}
```

**MONITOR_ONLY** (Healthy):
```json
{
  "predicted_failure_date": null,
  "immediate_actions": [
    "Continue normal operations",
    "Perform routine inspections per schedule",
    "Monitor sensor readings for changes",
    "Log equipment status in maintenance tracking system"
  ],
  "recommendation_details": "MONITOR: No action required at this time. Continue regular monitoring schedule."
}
```

### Implementation Files

| File | Changes |
|------|---------|
| `src/agents/diagnosis_agent.py` | Added `_build_recommendations()` method |
| `src/services/diagnosis_agent/app.py` | Updated DiagnosisAgentResponse schema |
| `src/graph/workflow.py` | Added recommendation fields to WorkflowState |
| `src/services/orchestrator/app.py` | Updated OrchestratorResponse schema |

---

## Feature 2: Multi-Agent Tracking

### New Endpoints

#### 1. GET /agents-trace/{device_id}

Returns full request history for a device showing which agents/tools were invoked.

```bash
curl http://localhost:8000/agents-trace/pump-004
```

**Response**:
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

#### 2. GET /agents-summary

Aggregate statistics across all devices showing routing patterns and tool usage.

```bash
curl http://localhost:8000/agents-summary
```

**Response**:
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

### Tracking Logic

- **HealthAgent Always Used**: Every request goes through HealthAgent for health classification
- **DiagnosisAgent Conditional**: Only invoked if health status is warning or critical (cost optimization)
- **MCP Tools**: Extracted from tool_results returned by DiagnosisAgent

### Routing Paths

| Path | Condition | Agents Used |
|------|-----------|-------------|
| `health_only` | Device is healthy | HealthAgent only |
| `full_diagnosis` | Device has issues | HealthAgent + DiagnosisAgent |

### Implementation Files

| File | Changes |
|------|---------|
| `src/graph/workflow.py` | Added agents_used[], mcp_tools_used[] to WorkflowState |
| `src/graph/workflow.py` | Updated nodes to track agent invocation |
| `src/services/orchestrator/app.py` | Added /agents-trace/{device_id} endpoint |
| `src/services/orchestrator/app.py` | Added /agents-summary endpoint |

---

## Testing Results

### Verified Scenarios

✅ **Critical Device (pump-004)**
- Agents: HealthAgent → DiagnosisAgent (both invoked)
- Tools: create-work-order
- Action: URGENT_REPAIR
- Recommendation: Immediate shutdown, replacement needed

✅ **Warning Device (compressor-002)**
- Agents: HealthAgent → DiagnosisAgent (both invoked)
- Tools: schedule-maintenance
- Action: SCHEDULE_MAINTENANCE
- Recommendation: 14-day maintenance window

✅ **Healthy Device (pump-001)**
- Agents: HealthAgent only (cost optimization)
- Tools: none
- Action: MONITOR_ONLY
- Recommendation: Continue normal operations

### Test Commands

```bash
# Test critical device with recommendations
curl http://localhost:8000/devices/pump-004 | jq '.recommendation_details'

# Test agent tracking
curl http://localhost:8000/agents-trace/pump-004 | jq '.requests[0].agents_used'

# Test summary statistics
curl http://localhost:8000/agents-summary | jq '.devices[].routing_paths'
```

---

## Architecture Improvements

### Dashboard Display
Operations teams can now see:
- **What to do** (immediate_actions)
- **Why to do it** (llm_insights)
- **When to do it** (predicted_failure_date)
- **Full context** (recommendation_details)

### Observability
System engineers can now see:
- Which agents were invoked per request
- Which MCP tools were called
- Routing patterns (health_only vs full_diagnosis)
- Request history per device

### Cost Optimization
- Healthy devices skip expensive DiagnosisAgent call
- Only critical/warning devices get full analysis
- In-memory tracking (50 records per device limit)

---

## Files Modified

```
src/agents/diagnosis_agent.py
  - _build_recommendations()  [NEW]
  - _get_parts_for_anomaly()  [NEW]

src/services/diagnosis_agent/app.py
  - DiagnosisAgentResponse    [UPDATED schema]

src/graph/workflow.py
  - WorkflowState             [NEW fields: llm_insights, immediate_actions, predicted_failure_date, recommendation_details]
  - _diagnosis_agent_node()   [UPDATED to extract recommendations]

src/services/orchestrator/app.py
  - OrchestratorResponse      [UPDATED schema with recommendation + tracking fields]
  - /agents-trace/{device_id} [NEW endpoint]
  - /agents-summary           [NEW endpoint]
  - Initial state setup       [UPDATED to initialize recommendation fields]
  - Response building         [UPDATED in both /devices and /process endpoints]

docs/WEEK2_DAY5_7_AGENT_INTEGRATION.md
  - Added Phase 3.1 section documenting all changes
```

---

## Next Steps

1. **Dashboard Integration**: Update frontend to display recommendation fields
2. **Persistent Tracking**: Replace in-memory request_history with DynamoDB
3. **Alert System**: Trigger notifications based on predicted_failure_date
4. **Performance Metrics**: Add monitoring for agent execution times
5. **Production Deployment**: Deploy to AWS ECS with CloudWatch logging

---

## Rollback Plan

If issues occur:
```bash
# Revert to pre-Phase 3.1 state
git checkout HEAD~1 src/
docker-compose down && docker-compose up -d --build
```

All changes are backward compatible - recommendation fields are optional in responses.
