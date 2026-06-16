# Using Swagger UI to Test Endpoints

## Quick Start

1. **Ensure services are running:**
   ```bash
   docker compose up -d
   ```

2. **Open Swagger UI:**
   ```
   http://localhost:8000/docs
   ```

3. **You should see three endpoints:**
   - `GET /health` - Service health check
   - `GET /devices` - List all devices
   - `GET /devices/{device_id}/summary` - Device details with history
   - `GET /devices/{device_id}` - Process device (main endpoint)
   - `POST /process` - Manual device processing
   - `GET /workflow-info` - Architecture information

## Testing Each Endpoint

### 1. Health Check
**Endpoint:** `GET /health`

1. Click on the endpoint
2. Click "Try it out"
3. Click "Execute"

**Expected Response (200):**
```json
{
  "status": "healthy",
  "service": "Orchestrator"
}
```

---

### 2. List All Devices
**Endpoint:** `GET /devices`

1. Click on the endpoint
2. Click "Try it out"
3. Click "Execute"

**Expected Response (200):**
```json
{
  "total": 17,
  "devices": [
    "compressor-001",
    "compressor-002",
    "compressor-003",
    "compressor-004",
    "generator-001",
    "generator-002",
    "generator-003",
    "motor-001",
    "motor-002",
    "motor-003",
    "motor-004",
    "motor-005",
    "pump-001",
    "pump-002",
    "pump-003",
    "pump-004",
    "pump-005"
  ]
}
```

---

### 3. Get Device Summary
**Endpoint:** `GET /devices/{device_id}/summary`

1. Click on the endpoint
2. Click "Try it out"
3. In the `device_id` field, enter: `pump-001`
4. Click "Execute"

**Expected Response (200):**
```json
{
  "device_id": "pump-001",
  "equipment_type": "PUMP",
  "last_reading_timestamp": "2026-05-30T23:00:00",
  "current_health": "healthy",
  "degradation_score": 0.023,
  "average_degradation_score": 0.027,
  "trend": "improving",
  "history_count": 720,
  "readings_available": ["flow", "pressure", "temperature", "vibration", "suction_pressure"]
}
```

**What this tells you:**
- Device is healthy (currently)
- Trend is improving (degradation scores decreasing)
- 720 readings available (30 days of hourly data)
- All major sensors available

---

### 4. Process Device (Main Test)
**Endpoint:** `GET /devices/{device_id}`

This is the most important endpoint. It loads real data and runs through the complete workflow.

#### Test Case 1: Healthy Device
1. Click on the endpoint
2. Click "Try it out"
3. Enter `device_id`: `pump-001`
4. Click "Execute"

**Expected Response (200):**
```json
{
  "device_id": "pump-001",
  "health_status": "healthy",
  "diagnosis": "Device operating normally",
  "confidence": 1.0,
  "action": "MONITOR_ONLY",
  "action_taken": "No action required",
  "tool_results": {},
  "llm_used": false,
  "path": "health_only",
  "processing_time_ms": 26.35,
  "timestamp": "2026-06-12T16:05:32.123456"
}
```

**What's happening:**
- ✅ **health_only path**: Healthy device, no diagnosis needed
- ✅ **No LLM**: Confidence=1.0 (definitive)
- ✅ **No tools**: No MCP tools called
- ✅ **Fast**: ~26ms (only HealthAgent)

---

#### Test Case 2: Critical Device (Rules-Based Decision)
1. Click on the endpoint
2. Click "Try it out"
3. Enter `device_id`: `pump-002`
4. Click "Execute"

**Expected Response (200):**
```json
{
  "device_id": "pump-002",
  "health_status": "critical",
  "diagnosis": "Pump valve wear - pressure unstable with high vibration",
  "confidence": 0.88,
  "action": "SCHEDULE_MAINTENANCE",
  "action_taken": "Preventive maintenance scheduled for pump-002",
  "tool_results": {
    "schedule-maintenance": {
      "statusCode": 200,
      "body": "{\"maintenance_id\": \"MAINT-20260612-xyz\", \"device_id\": \"pump-002\", \"maintenance_type\": \"preventive\", \"scheduled_date\": \"2026-06-19\", \"status\": \"scheduled\", ...}",
      "headers": {"Content-Type": "application/json"}
    }
  },
  "llm_used": false,
  "path": "full_diagnosis",
  "processing_time_ms": 950.42,
  "timestamp": "2026-06-12T16:05:34.234567"
}
```

**What's happening:**
- ✅ **full_diagnosis path**: Issue detected, diagnosis needed
- ✅ **High confidence (0.88)**: Clear pattern match → RULES-BASED
- ✅ **No LLM**: Confidence ≥ 0.85, so no need for LLM
- ✅ **AWS tool called**: schedule-maintenance created (MAINT-20260612-xyz)
- ✅ **Slower**: ~950ms (includes diagnosis, AWS call)
- ✅ **Real AWS**: Maintenance actually scheduled in AWS

---

#### Test Case 3: Critical Device (LLM Pattern - Not in Real Data)
This would happen with confidence < 0.85, but our real test data has clear patterns.

Example response if LLM were called:
```json
{
  "device_id": "device-x",
  "health_status": "warning",
  "diagnosis": "Bearing misalignment detected based on vibration analysis",
  "confidence": 0.72,
  "action": "CHECK_PARTS_FIRST",
  "llm_used": true,
  "path": "full_diagnosis",
  "processing_time_ms": 850.15,
  "timestamp": "2026-06-12T16:05:35.567890"
}
```

**What would be different:**
- ✅ **llm_used: true**: Azure OpenAI was called
- ✅ **Lower confidence**: 0.72 (ambiguous pattern)
- ✅ **Slower response**: ~850ms (includes LLM call)
- ✅ **Refined diagnosis**: LLM added reasoning

---

#### Test Case 4: Emergency Device (Urgent Repair)
1. Enter `device_id`: `motor-005`
2. Click "Execute"

**Expected Response (200):**
```json
{
  "device_id": "motor-005",
  "health_status": "critical",
  "diagnosis": "Motor bearing degradation - CRITICAL",
  "confidence": 0.90,
  "action": "URGENT_REPAIR",
  "action_taken": "Emergency work order created for motor-005",
  "tool_results": {
    "create-work-order": {
      "work_order_id": "WO-f5cc0b04",
      "status": "created",
      "created_at": "2026-06-12T16:05:36.789012"
    }
  },
  "llm_used": false,
  "path": "full_diagnosis",
  "processing_time_ms": 713.28,
  "timestamp": "2026-06-12T16:05:37.890123"
}
```

**What's happening:**
- ✅ **Critical status**: Severe issue detected
- ✅ **High confidence (0.90)**: Clear critical pattern
- ✅ **URGENT_REPAIR action**: Needs immediate attention
- ✅ **Work order created**: WO-f5cc0b04 (real AWS work order)
- ✅ **Full diagnosis path**: ~713ms

---

### 5. Workflow Info
**Endpoint:** `GET /workflow-info`

1. Click on the endpoint
2. Click "Try it out"
3. Click "Execute"

**Expected Response (200):**
```json
{
  "workflow": "LangGraph 4-node workflow (Week 2 Day 5-7)",
  "architecture": {
    "core": "src/graph/workflow.py (OrchestrationWorkflow class)",
    "wrapper": "src/services/orchestrator/app.py (FastAPI service)"
  },
  "nodes": [
    {
      "name": "health_agent",
      "purpose": "Classify device health (healthy/warning/alert/critical)",
      "calls": "HealthAgent service via HTTP POST /analyze",
      "tools": "None"
    },
    ...
  ]
}
```

---

### 6. Manual Process (Alternative)
**Endpoint:** `POST /process`

This endpoint lets you send custom sensor data instead of loading from files.

1. Click on the endpoint
2. Click "Try it out"
3. Modify the example JSON body:

```json
{
  "device_id": "pump-test",
  "equipment_type": "PUMP",
  "current_reading": {
    "readings": {
      "temperature": {
        "value": 75,
        "unit": "°C",
        "normal_range": [20, 95]
      },
      "vibration": {
        "value": 2.1,
        "unit": "mm/s",
        "normal_range": [0, 3]
      },
      "pressure": {
        "value": 4.5,
        "unit": "bar",
        "normal_range": [4, 5]
      },
      "flow": {
        "value": 850,
        "unit": "L/min",
        "normal_range": [800, 900]
      }
    }
  }
}
```

4. Click "Execute"

**Expected Response (200):**
```json
{
  "device_id": "pump-test",
  "health_status": "healthy",
  "diagnosis": "Device operating normally",
  "confidence": 1.0,
  "action": "MONITOR_ONLY",
  "action_taken": "No action required",
  "tool_results": {},
  "llm_used": false,
  "path": "health_only",
  "processing_time_ms": 32.15,
  "timestamp": "2026-06-12T16:05:40.123456"
}
```

---

## Testing Strategy

### Quick Validation (5 minutes)
1. `GET /devices` → See all 17 devices
2. `GET /devices/pump-001` → Verify healthy path (health_only)
3. `GET /devices/motor-005` → Verify critical path (work order created)
4. `GET /devices/pump-002/summary` → See device history

### Comprehensive Test (15 minutes)
1. Test all device types (pump, motor, compressor, generator)
2. Test healthy vs critical devices
3. Check processing times
4. Verify confidence scores
5. Confirm MCP tool results in AWS
6. Check trend analysis

### Load Testing (30 minutes)
1. Run `scripts/test_device_endpoint.py`
2. Test different devices sequentially
3. Monitor response times
4. Check Docker resource usage

---

## Response Code Reference

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success | Normal device processing |
| 400 | Bad request | Invalid JSON in POST |
| 404 | Not found | Device doesn't exist |
| 500 | Server error | Service failed |

---

## Troubleshooting

### "Failed to connect to localhost:8000"
```bash
# Check if services are running
docker compose ps

# Should see all 3 containers in "Up" state
# If not, start them:
docker compose up -d
```

### Swagger UI not loading
```bash
# Check orchestrator logs
docker compose logs orchestrator

# Service should be running on port 8000
curl http://localhost:8000/health
```

### Device not found (404)
```bash
# List available devices first
curl http://localhost:8000/devices

# Use exact device_id from the list
curl http://localhost:8000/devices/pump-001
```

### Slow response times
- First request might be slower (~500-900ms) due to LLM initialization
- Subsequent requests should be faster (~150-300ms) for rules-based decisions
- Healthy devices always fast (~20-80ms)

---

## Key Observations

Looking at Swagger responses, you'll see:

1. **Healthy devices**: `llm_used: false`, `path: health_only`, `~26ms`
2. **Clear issues**: `llm_used: false`, `confidence: 0.88+`, `path: full_diagnosis`, `~150-300ms`
3. **Ambiguous**: `llm_used: true`, `confidence: <0.85`, `path: full_diagnosis`, `~800-1000ms`
4. **AWS integration**: `tool_results` contains real work orders/maintenance IDs from AWS

This confirms the system is working correctly with smart LLM decision logic!
