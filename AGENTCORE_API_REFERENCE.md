# AgentCore Runtime API Reference (Manual - no Swagger available)

AgentCore Runtime doesn't expose a discoverable OpenAPI/Swagger page (see
`docs/PHASE_4_AGENTCORE_DEPLOYMENT.md` for why). This document is a manual
substitute: the exact request/response JSON shape for every agent, based on
the actual handler code, plus how to check which agents/MCP tools processed
any given request.

---

## Public HTTP entry point (via API Gateway + Lambda)

Base URL: `https://mn6y8y0u26.execute-api.us-east-1.amazonaws.com/prod`

Only the **orchestrator** is reachable directly over HTTP. HealthAgent and
DiagnosisAgent are only invoked agent-to-agent by the orchestrator (see
"Direct AgentCore invocation" section below if you need to test them in
isolation).

### `POST /orchestrate`

Analyze a device using a supplied sensor reading (full HealthAgent →
DiagnosisAgent workflow).

**Request:**
```json
{
  "device_id": "motor-004",
  "equipment_type": "MOTOR",
  "current_reading": {
    "rpm": {"value": 3450.58, "unit": "RPM", "normal_range": [3450, 3550]},
    "current": {"value": 100, "unit": "Amps", "normal_range": [60, 80]},
    "temperature": {"value": 143.19, "unit": "F", "normal_range": [60, 120]}
  }
}
```
Note: each sensor must be `{"value": ..., "unit": ..., "normal_range": [min, max]}` -
a flat scalar (e.g. `"temperature": 82.5`) will be silently ignored (no
anomaly ever detected for it).

**Response (healthy device):**
```json
{
  "device_id": "motor-004",
  "equipment_type": "MOTOR",
  "health_status": "healthy",
  "degradation_score": 0.0,
  "anomalies": [],
  "diagnosis": "Device operating normally",
  "confidence": 1.0,
  "action": "MONITOR_ONLY",
  "action_taken": "No action required",
  "agents_used": ["HealthAgent"],
  "path": "health_only",
  "timestamp": "..."
}
```

**Response (warning/critical device):**
```json
{
  "device_id": "motor-004",
  "health_status": "warning",
  "degradation_score": 0.4,
  "anomalies": ["current_high: 100 Amps (normal: 60-80)", "..."],
  "diagnosis": "Motor bearing degradation - CRITICAL",
  "confidence": 0.9,
  "severity": "high",
  "action": "URGENT_REPAIR",
  "action_taken": "Emergency work order created for motor-004",
  "agents_used": ["HealthAgent", "DiagnosisAgent"],
  "tool_results": {
    "create-work-order": {"work_order_id": "WO-7730c47b", "status": "created", "created_at": "..."}
  },
  "mcp_tools_used": ["create-work-order"],
  "path": "full_diagnosis",
  "timestamp": "..."
}
```
`agents_used` and `mcp_tools_used`/`tool_results` are the fields to check
**which agents/tools handled this specific request** - see "How to check
per-request usage" below.

### `GET /orchestrate/devices`

List all device IDs available in S3 (`agentic-ai-poc-synthetic-data` bucket).

**Response:**
```json
{"total": 17, "devices": ["compressor-001", "...", "pump-005"]}
```

### `GET /orchestrate/devices/{device_id}`

Load the device's latest reading from S3 and run the full analysis workflow
(same response shape as `POST /orchestrate`).

### `GET /orchestrate/devices/{device_id}/summary`

Device summary/history stats (no live agent analysis - just S3 data stats).

**Response:**
```json
{
  "device_id": "motor-004",
  "equipment_type": "MOTOR",
  "last_reading_timestamp": "2026-05-30T23:00:00",
  "current_health": "alert",
  "degradation_score": 0.341,
  "average_degradation_score": 0.3383,
  "trend": "degrading",
  "history_count": 720,
  "readings_available": ["rpm", "current", "temperature", "voltage", "power_factor", "vibration"]
}
```

### `GET /orchestrate/health`

Orchestrator health check.
```json
{"status": "healthy", "service": "OrchestratorAgent"}
```

---

## Direct AgentCore invocation (for testing HealthAgent/DiagnosisAgent in isolation)

These aren't exposed via API Gateway - invoke them directly with boto3 if
you need to test in isolation (e.g. from a Python shell):

```python
import boto3, json, time

session = boto3.Session(profile_name='StandardAccess-450410489798', region_name='us-east-1')
client = session.client('bedrock-agentcore')

def invoke(runtime_id, payload):
    session_id = f"test-{int(time.time()*1000000)}".ljust(33, '0')
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=f'arn:aws:bedrock-agentcore:us-east-1:450410489798:runtime/{runtime_id}',
        runtimeSessionId=session_id,
        payload=json.dumps(payload)
    )
    return json.loads(resp['response'].read().decode('utf-8'))
```

### HealthAgent (`health_agent_runtime-fAr31a5AEi`)

**Request:**
```json
{"device_id": "motor-004", "equipment_type": "MOTOR", "current_reading": {"rpm": {"value": 3450, "unit": "RPM", "normal_range": [3450, 3550]}}}
```
**Response:**
```json
{"statusCode": 200, "body": {"device_id": "motor-004", "health_status": "healthy", "degradation_score": 0.0, "anomalies": [], "analysis_timestamp": "...", "status": "completed"}}
```

### DiagnosisAgent (`diagnosis_agent_runtime-r8AcIc5zbG`)

**Request:**
```json
{"device_id": "motor-004", "equipment_type": "MOTOR", "health_status": "warning", "degradation_score": 0.4, "anomalies": ["current_high: 100 Amps (normal: 60-80)"]}
```
**Response:**
```json
{
  "statusCode": 200,
  "body": {
    "device_id": "motor-004",
    "diagnosis": "Motor bearing degradation - CRITICAL",
    "confidence": 0.9,
    "confidence_rule_based": 0.9,
    "llm_used": false,
    "severity": "high",
    "action": "URGENT_REPAIR",
    "action_taken": "Emergency work order created for motor-004",
    "tool_results": {"create-work-order": {"work_order_id": "WO-...", "status": "created", "created_at": "..."}},
    "status": "completed"
  }
}
```

---

## How to check which agents/MCP tools processed a request

### 1. Read the response body (fastest, works for every request)

- `agents_used`: `["HealthAgent"]` (healthy - DiagnosisAgent skipped) or
  `["HealthAgent", "DiagnosisAgent"]` (non-healthy - full chain ran)
- `mcp_tools_used`: list of MCP tool names actually called (e.g.
  `["create-work-order"]`, `["get-spare-parts", "schedule-maintenance"]`, or
  `[]` if action was `MONITOR_ONLY`)
- `tool_results`: the actual tool call outputs (work order IDs, spare parts
  data, etc.)
- `llm_used` (DiagnosisAgent-only field, not currently forwarded by the
  orchestrator - check CloudWatch logs if you need this): `true` if Azure
  OpenAI (gpt-4o) was called to verify a low-confidence rule match, `false`
  if the rule-based confidence was trusted directly (>= 0.85)

### 2. CloudWatch Logs (full step-by-step trace, request/response bodies)

Each runtime has its own log group:
```
/aws/bedrock-agentcore/runtimes/orchestrator_runtime-6UF3HDGyvL-DEFAULT
/aws/bedrock-agentcore/runtimes/health_agent_runtime-fAr31a5AEi-DEFAULT
/aws/bedrock-agentcore/runtimes/diagnosis_agent_runtime-r8AcIc5zbG-DEFAULT
```

**Important:** AgentCore Runtime creates a **new log stream for every single
invocation** (one microVM per invocation), not one continuous stream per
runtime. So instead of guessing/picking a stream by "most recent", the
reliable way to find the trace for a *specific* request is to search across
the whole log group for something unique from that request's response (e.g.
a `work_order_id` from `tool_results`, or the `device_id`), using
`filter-log-events`:

```bash
# Step 1: Find the exact stream by searching for a known value from the response
# (quote the pattern - CloudWatch's filter syntax treats bare hyphens specially)
aws logs filter-log-events \
  --log-group-name "/aws/bedrock-agentcore/runtimes/diagnosis_agent_runtime-r8AcIc5zbG-DEFAULT" \
  --filter-pattern '"WO-8f5450a0"' \
  --region us-east-1 --profile StandardAccess-450410489798 \
  --query 'events[0].logStreamName' --output text
# -> 2026/07/24/[runtime-logs]46365670-7e35-414d-8bbf-413ef59bd53d

# Step 2: Fetch the full trace from that stream
aws logs get-log-events \
  --log-group-name "/aws/bedrock-agentcore/runtimes/diagnosis_agent_runtime-r8AcIc5zbG-DEFAULT" \
  --log-stream-name '2026/07/24/[runtime-logs]46365670-7e35-414d-8bbf-413ef59bd53d' \
  --region us-east-1 --profile StandardAccess-450410489798 \
  --query 'events[].message' --output text
```

Real example output (compressor-004, escalated to critical):
```
Received payload: {'device_id': 'compressor-004', ..., 'health_status': 'critical', 'anomalies': [...5 anomalies...]}
LLM client initialized (deployment: gpt-4o)
[DiagnosisAgent] STEP 1: Pattern matching
  Rule match: Compressor thermal stress - possible valve issue (confidence: 0.82)
[DiagnosisAgent] STEP 2: Health status escalation check
  Health Status = CRITICAL → Escalating to URGENT_REPAIR (work order required)
[DiagnosisAgent] STEP 3: Confidence check (threshold: 0.85)
  Confidence 0.87 >= 0.85 → TRUST RULE (no LLM needed)
[DiagnosisAgent] STEP 4: Execute action (URGENT_REPAIR)
Fetching new Cognito access token... Token acquired, expires in 3600 seconds
Calling tool: create-work-order___create_work_order with args: {...}
[_execute_action] Work order result: {'work_order_id': 'WO-8f5450a0', 'status': 'created', ...}
Invocation completed successfully (0.399s)
```

If you only need the "most recent N streams" (not a specific request), use:
```bash
aws logs describe-log-streams \
  --log-group-name "/aws/bedrock-agentcore/runtimes/diagnosis_agent_runtime-r8AcIc5zbG-DEFAULT" \
  --order-by LastEventTime --descending --limit 5 \
  --region us-east-1 --profile StandardAccess-450410489798 \
  --query 'logStreams[].{name:logStreamName,lastEvent:lastEventTimestamp}' --output table
```
Note concurrent requests each get their own stream, so "most recent" isn't
always the one you're after if multiple requests happened close together -
`filter-log-events` with a unique value is the more reliable technique.

### 3. AWS Console

Bedrock console → AgentCore → Runtimes → select a runtime → shows invocation
count/metrics and a link to its CloudWatch log group (this is how the "0
invocations on DiagnosisAgent" symptom was first spotted, before tracing it
back to the HealthAgent bug that made every device "healthy" and skipped
DiagnosisAgent entirely).
