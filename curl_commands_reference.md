# curl Commands Reference - Agent Invocation via HTTP

This document provides curl commands to invoke agents deployed on AWS Bedrock AgentCore Runtime.

## Prerequisites

1. AWS CLI configured with appropriate credentials
2. Network access to AWS (VPN, corporate network, or AWS environment)
3. Valid AWS SigV4 signed requests (handled by aws-cli or manual signing)

## Agent Endpoints

```bash
# Orchestrator (entry point - calls health and diagnosis agents)
ORCHESTRATOR_ENDPOINT="https://agentcore-runtime.us-east-1.amazonaws.com/runtimes/orchestrator_runtime-6UF3HDGyvL"

# Health Agent (health scoring)
HEALTH_AGENT_ENDPOINT="https://agentcore-runtime.us-east-1.amazonaws.com/runtimes/health_agent_runtime-fAr31a5AEi"

# Diagnosis Agent (root cause analysis + MCP tools)
DIAGNOSIS_AGENT_ENDPOINT="https://agentcore-runtime.us-east-1.amazonaws.com/runtimes/diagnosis_agent_runtime-r8AcIc5zbG"
```

## Test Device Data (Anomalies)

### Motor-004 (Alert State)
```json
{
  "device_id": "motor-004",
  "equipment_type": "MOTOR",
  "current_reading": {
    "readings": {
      "rpm": {"value": 3450.58, "unit": "RPM", "normal_range": [3450, 3550]},
      "current": {"value": 100, "unit": "Amps", "normal_range": [60, 80]},
      "temperature": {"value": 143.19, "unit": "F", "normal_range": [60, 120]},
      "voltage": {"value": 378.25, "unit": "V", "normal_range": [350, 410]},
      "power_factor": {"value": 0.8424, "unit": "PF", "normal_range": [0.9, 1.0]},
      "vibration": {"value": 5.16, "unit": "mm/s", "normal_range": [0, 2]}
    }
  }
}
```

### Pump-004 (Critical State)
```json
{
  "device_id": "pump-004",
  "equipment_type": "PUMP",
  "current_reading": {
    "readings": {
      "flow": {"value": 292.82, "unit": "GPM", "normal_range": [500, 700]},
      "pressure": {"value": 32.13, "unit": "PSI", "normal_range": [140, 160]},
      "temperature": {"value": 230.83, "unit": "F", "normal_range": [100, 180]},
      "vibration": {"value": 8.2, "unit": "mm/s", "normal_range": [0, 3]}
    }
  }
}
```

## Method 1: Using aws-cli (Recommended - Handles SigV4 Automatically)

### Basic Structure
```bash
aws --profile StandardAccess-450410489798 \
    --region us-east-1 \
    bedrock-runtime invoke-agent \
    --agent-id <AGENT_ID> \
    --agent-alias-id <ALIAS_ID> \
    --session-id <SESSION_ID> \
    --input-text '<JSON_PAYLOAD>' \
    response.json
```

### Invoke Orchestrator with Anomalous Device
```bash
# Set device data
DEVICE_DATA='{
  "device_id": "motor-004",
  "equipment_type": "MOTOR",
  "current_reading": {
    "readings": {
      "rpm": {"value": 3450.58, "unit": "RPM", "normal_range": [3450, 3550]},
      "current": {"value": 100, "unit": "Amps", "normal_range": [60, 80]},
      "temperature": {"value": 143.19, "unit": "F", "normal_range": [60, 120]},
      "voltage": {"value": 378.25, "unit": "V", "normal_range": [350, 410]},
      "power_factor": {"value": 0.8424, "unit": "PF", "normal_range": [0.9, 1.0]},
      "vibration": {"value": 5.16, "unit": "mm/s", "normal_range": [0, 2]}
    }
  }
}'

# Invoke via HTTP endpoint
ENDPOINT="https://agentcore-runtime.us-east-1.amazonaws.com/runtimes/orchestrator_runtime-6UF3HDGyvL"

curl -X POST "$ENDPOINT/process" \
  -H "Content-Type: application/json" \
  -d "$DEVICE_DATA" \
  -v
```

## Method 2: Using curl with Manual SigV4 Signing

This requires AWS SigV4 signing. Easier to use Python script instead:

```bash
# Create request signature using aws-cli (pipe to curl)
ENDPOINT="https://agentcore-runtime.us-east-1.amazonaws.com/runtimes/orchestrator_runtime-6UF3HDGyvL"
PAYLOAD='{"device_id":"motor-004","equipment_type":"MOTOR",...}'

# Using aws-cli to sign and forward
aws --profile StandardAccess-450410489798 \
    --region us-east-1 \
    s3api get-object \
    --bucket SIGNED_REQUEST \
    --key request.json response.json \
    2>&1 | curl -v -X POST "$ENDPOINT/process" \
    -H "Content-Type: application/json" \
    -d @request.json
```

## Method 3: Using Python Script (Recommended for Automation)

See: `test_agentcore_mcp_invocation.py`

```bash
python3 test_agentcore_mcp_invocation.py
```

This script:
- Loads device data from `data/generated/`
- Sends to agent endpoints with proper SigV4 signing
- Displays MCP tool invocation evidence

## Expected Responses

### Successful Agent Response
```json
{
  "device_id": "motor-004",
  "health_status": "alert",
  "diagnosis": "Motor showing signs of bearing degradation",
  "confidence": 0.92,
  "action": "SCHEDULE_MAINTENANCE",
  "action_taken": "Maintenance scheduled for motor-004",
  "mcp_tools_used": ["get-spare-parts", "schedule-maintenance"],
  "tool_results": {
    "get-spare-parts": {
      "spare_parts": ["Motor Bearing", "Lubricant"],
      "availability": "In stock"
    },
    "schedule-maintenance": {
      "scheduled_date": "2026-07-12",
      "work_order_id": "WO-2026-0712-001"
    }
  },
  "processing_time_ms": 2345
}
```

### MCP Tools Used Indicators
Look for these in response:
- `"mcp_tools_used": [...]` - List of Lambda tools invoked
- `"tool_results": {...}` - Results from each tool
- `"action_taken": "..."` - Actual action executed

## Verification: Check MCP Tool Execution

After sending request, wait 30-60 seconds and run:

```bash
python3 quick_mcp_log_check.py
```

This checks CloudWatch logs for:
- `GatewayClient` initialization
- `access_token` (Cognito auth)
- Tool invocation keywords
- Action execution logs

## Network Access Requirements

**Local Development Machine**: Limited direct access
- Can use Lambda wrapper: `python3 lambda_mcp_test_wrapper.py`
- Can check logs via AWS CLI: `aws logs...`

**From AWS EC2/Lambda**: Full access
- Can call agent endpoints directly via curl
- No VPN needed
- Fastest MCP tool execution

**From Corporate Network**: Depends on VPN/proxy config
- Use curl with proxy settings if behind corporate firewall
- May need to setup VPN tunnel first

## Troubleshooting

### Connection Refused / DNS Error
```
Error: Failed to resolve 'agentcore-runtime.us-east-1.amazonaws.com'
```
**Solution**: Need AWS network access (VPN, EC2, Lambda)

### 403 Forbidden / Unauthorized
```
Error: 403 Forbidden
```
**Causes**:
1. Invalid AWS credentials
2. Missing permissions for bedrock-agentcore
3. Invalid SigV4 signature

**Solution**: 
```bash
# Verify credentials
aws --profile StandardAccess-450410489798 sts get-caller-identity

# Check permissions
aws --profile StandardAccess-450410489798 iam get-role-policy \
  --role-name AgentCoreExecutionRole \
  --policy-name AgentCoreFullAccess
```

### 404 Not Found
```
Error: 404 Not Found /runtimes/orchestrator_runtime-6UF3HDGyvL
```
**Causes**:
1. Agent runtime doesn't exist
2. Incorrect runtime ID

**Solution**:
```bash
# List deployed runtimes
aws --profile StandardAccess-450410489798 \
    bedrock-agentcore-control list-agent-runtimes \
    --region us-east-1
```

### Timeout / Slow Response
```
Error: Connection timed out (waited > 120 seconds)
```
**Causes**:
1. Agent processing taking long time
2. LLM API latency
3. MCP tool execution delays

**Solution**:
- Increase timeout: `--connect-timeout 300`
- Check CloudWatch logs to see where time is spent
- Verify Azure OpenAI/LLM endpoint is accessible

## Complete End-to-End Test

```bash
#!/bin/bash

echo "=== MCP Tool E2E Test ==="

# 1. Send anomalous device to orchestrator
echo "1. Invoking orchestrator with motor-004 (alert state)..."
python3 test_agentcore_mcp_invocation.py

# 2. Wait for agent processing and log writing
echo "2. Waiting 45 seconds for logs..."
sleep 45

# 3. Check for MCP tool evidence in logs
echo "3. Checking CloudWatch logs for MCP tool usage..."
python3 quick_mcp_log_check.py

# 4. Verify complete flow
echo "4. Verifying MCP gateway configuration..."
python3 verify_mcp_gateway_access.py

echo "=== E2E Test Complete ==="
```

## Summary

✅ **All tools configured** - Agents have MCP gateway credentials
✅ **Endpoints deployed** - HTTP endpoints ready to accept requests
✅ **Verification methods** - CloudWatch log checking available

**To trigger MCP tool usage**:
1. Send request to orchestrator endpoint with anomalous device
2. Agent invokes diagnosis_agent
3. Diagnosis detects issue → takes action
4. Action calls MCP tools (work order, maintenance scheduling)
5. Check logs 30-60 seconds later

See: `quick_mcp_log_check.py` for log verification
