# Phase 5: Lambda + API Gateway Deployment Guide

**Status**: Implementation Phase  
**Target**: Enable dashboard and external systems to invoke orchestrator agents  
**Date**: 2026-07-23  

---

## 📋 Quick Summary

This guide covers deploying the Lambda handler and API Gateway that bridge between the dashboard and AgentCore Orchestrator Runtime.

### What We're Building

```
Dashboard/External Systems
    ↓
API Gateway (HTTPS endpoint)
    ↓
Lambda Function (orchestrator-handler)
    ↓
AgentCore Orchestrator Runtime
    ↓
HealthAgent → DiagnosisAgent → MCP Tools
```

### Why This Is Needed

- **Local machines can't reach AgentCore agents** (network restrictions)
- **Lambda runs inside AWS** (has network access)
- **API Gateway provides HTTPS endpoint** (works from anywhere)
- **Dashboard can use new endpoint** (no code changes to agents)

---

## ✅ Prerequisites

### 1. AWS CLI and boto3

```bash
# Install AWS CLI and boto3 (both already in requirements-dev.txt)
pip install awscli boto3

# Verify installations
aws --version
python3 -c "import boto3; print(f'boto3 version: {boto3.__version__}')"
```

### 2. AWS Credentials

You need credentials with permissions to:
- Create/update Lambda functions
- Create/update API Gateway
- Create/update CloudWatch Logs
- Create/update IAM roles

```bash
# Configure AWS CLI
aws configure --profile StandardAccess-450410489798

# Or use existing profile from .agentcore.env deployment
export AWS_PROFILE=StandardAccess-450410489798
```

### 3. Configuration Files

**Required Files**:
- ✅ `.agentcore.env` - Contains Cognito credentials
- ✅ `functions/lambda_orchestrator_handler.py` - Handler code
- ✅ `scripts/deploy_lambda_boto3.py` - Deployment script (boto3-based)

**Verify All Exist**:
```bash
ls -la .agentcore.env
ls -la functions/lambda_orchestrator_handler.py
ls -la scripts/deploy_lambda_boto3.py
```

---

## 🧪 Phase 1: Local Testing

Before deploying to AWS, test the handler locally.

### Step 1.1: Run Local Tests

```bash
# Run all tests
python3 test_lambda_handler.py

# Run with verbose output
python3 test_lambda_handler.py --verbose
```

**Expected Output**:
```
=== Lambda Handler Tests ===
✓ Handler module imported successfully
✓ lambda_handler function exists
✓ parse_api_gateway_event function exists
✓ parse_api_gateway_event function exists
...
✓ All 9 tests passed!
```

### Step 1.2: Verify Handler Code

```bash
# Check handler can be imported
python3 -c "import sys; sys.path.insert(0, 'functions'); from lambda_orchestrator_handler import lambda_handler; print('✓ Handler imports successfully')"
```

### Step 1.3: Test Request Parsing

```bash
# Create test request
python3 << 'EOF'
import sys
import json
sys.path.insert(0, 'functions')
from lambda_orchestrator_handler import parse_api_gateway_event

event = {
    'body': json.dumps({
        'device_id': 'motor-004',
        'equipment_type': 'MOTOR',
        'current_reading': {'readings': {'current': {'value': 100}}}
    })
}

result = parse_api_gateway_event(event)
print(f"Parsed successfully: {result.get('device_id')}")
EOF
```

---

## 🚀 Phase 2: Deploy to AWS (Using boto3)

### Step 2.1: Prepare Environment

```bash
# Activate Python virtual environment
source venv/bin/activate

# Refresh AWS SSO login (if needed)
aws sso login --profile StandardAccess-450410489798 --no-browser

# Verify AWS credentials
aws sts get-caller-identity --profile StandardAccess-450410489798
```

**Expected Output**:
```json
{
    "UserId": "AIDACKCEVSQ6C5EXAMPLE",
    "Account": "450410489798",
    "Arn": "arn:aws:iam::450410489798:role/..."
}
```

### Step 2.2: Run Deployment Script

**Simple One-Command Deployment**:

```bash
AWS_PROFILE=StandardAccess-450410489798 python3 scripts/deploy_lambda_boto3.py
```

That's it! The script will:
1. ✅ Authenticate with AWS using your profile
2. ✅ Load Cognito credentials from `.agentcore.env`
3. ✅ Package Lambda handler code
4. ✅ Create Lambda function (or update if exists)
5. ✅ Find existing Lambda execution role
6. ✅ Create API Gateway REST API (or use existing)
7. ✅ Wire Lambda to POST /orchestrate endpoint
8. ✅ Add CORS headers for dashboard access
9. ✅ Output API endpoint URL

### Step 2.3: Monitor Deployment

**Deployment Output Example**:
```
=== Deploy Lambda + API Gateway (boto3)

[✓] AWS Account: 450410489798
[✓] Lambda package ready
[✓] Using existing IAM role: agentic-ai-lambda-execution-role
[✓] Lambda function ready: orchestrator-handler-450410489798
[✓] API Gateway ready: https://abc123.execute-api.us-east-1.amazonaws.com/prod/orchestrate

=== Deployment Complete ===

Lambda Function: orchestrator-handler-450410489798
API Endpoint:    https://abc123.execute-api.us-east-1.amazonaws.com/prod/orchestrate

Test with curl:
curl -X POST https://abc123.execute-api.us-east-1.amazonaws.com/prod/orchestrate \
  -H 'Content-Type: application/json' \
  -d '{"device_id":"motor-004","equipment_type":"MOTOR","current_reading":{}}'
```

### Step 2.4: Save API Endpoint URL

**The endpoint URL is needed for dashboard configuration**:
```bash
# Copy from script output (it displays at the end)
# Example: https://abc123.execute-api.us-east-1.amazonaws.com/prod/orchestrate

# Save for next step
export ORCHESTRATOR_LAMBDA_ENDPOINT="https://abc123.execute-api.us-east-1.amazonaws.com/prod/orchestrate"
```

---

## 🧪 Phase 3: Test Deployed Lambda

### Step 3.1: Test with curl

Replace endpoint URL with the actual one from deployment output.

```bash
# Test with motor data
curl -X POST https://YOUR_API_ENDPOINT/orchestrate \
  -H "Content-Type: application/json" \
  -d '{
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
  }' | jq '.'
```

**Expected Response (if successful)**:
```json
{
  "device_id": "motor-004",
  "health_status": "alert",
  "diagnosis": "Motor showing signs of bearing degradation",
  "action": "SCHEDULE_MAINTENANCE",
  "action_taken": "Maintenance scheduled",
  "mcp_tools_used": ["get-spare-parts", "schedule-maintenance"],
  "processing_time_ms": 2345
}
```

**Expected Response (if agent not reachable)**:
```json
{
  "error": "Cannot reach agent endpoint",
  "statusCode": 503,
  "details": "Network connectivity issue"
}
```

### Step 3.2: Test CORS Preflight

```bash
curl -X OPTIONS https://YOUR_API_ENDPOINT/orchestrate \
  -H "Access-Control-Request-Method: POST" \
  -H "Origin: http://localhost:8080" \
  -v
```

**Expected Response**: HTTP 200 with CORS headers

### Step 3.3: Check CloudWatch Logs

```bash
# View Lambda logs
aws logs tail /aws/lambda/orchestrator-handler-450410489798 \
  --profile StandardAccess-450410489798 \
  --region us-east-1 \
  --follow
```

**What to Look For**:
- ✅ Lambda invocation logs
- ✅ OAuth token acquisition
- ✅ Orchestrator endpoint calls
- ✅ Processing time
- ✅ MCP tools invoked (if applicable)

### Step 3.4: Verify MCP Tool Execution

If agent took action on a critical device:

```bash
# Check for MCP tool keywords
aws logs filter-log-events \
  --log-group-name /aws/lambda/orchestrator-handler-450410489798 \
  --filter-pattern "MCP OR access_token OR tool" \
  --profile StandardAccess-450410489798 \
  --region us-east-1
```

---

## 🎯 Phase 4: Dashboard Integration

### Step 4.1: Update Dashboard Configuration

Update [src/dashboard/config.py](src/dashboard/config.py):

**Before**:
```python
ORCHESTRATOR_URL: str = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000")
```

**After**:
```python
ORCHESTRATOR_URL: str = os.getenv(
    "ORCHESTRATOR_URL", 
    "https://YOUR_API_ENDPOINT/orchestrate"  # Lambda + API Gateway
)
```

### Step 4.2: Update Environment

Create `.env.lambda` or update `.env`:

```bash
# Dashboard will use API Gateway instead of local Docker
ORCHESTRATOR_URL=https://abc123.execute-api.us-east-1.amazonaws.com/prod/orchestrate
```

### Step 4.3: Start Dashboard

```bash
# Terminal 1: Dashboard API
cd src/dashboard
python3 -m uvicorn main:app --host 0.0.0.0 --port 8080

# Terminal 2: Test endpoint
curl http://localhost:8080/api/fleet-summary | jq '.'
```

### Step 4.4: Verify Data Flow

```
Dashboard UI (localhost:8080)
  ↓
Dashboard API (localhost:8080/api/*)
  ↓
Lambda via API Gateway (HTTPS)
  ↓
Orchestrator Agent (AgentCore)
  ↓
HealthAgent + DiagnosisAgent + MCP Tools
  ↓
Results back to Dashboard
```

**Test Dashboard**:
```bash
# View fleet summary with real agent data
curl http://localhost:8080/api/fleet-summary | jq '.devices[0]'

# View work orders from MCP tools
curl http://localhost:8080/api/work-orders | jq '.total'

# View maintenance schedules
curl http://localhost:8080/api/maintenance-schedule | jq '.schedules[0]'
```

---

## 🛠️ Troubleshooting

### Issue 1: Deployment Fails - SAM CLI Not Found

**Error**: `Command 'sam' not found`

**Solution**:
```bash
pip install aws-sam-cli
sam --version
```

### Issue 2: Deployment Fails - AWS Credentials

**Error**: `Unable to locate credentials`

**Solution**:
```bash
# Option 1: Configure CLI
aws configure --profile StandardAccess-450410489798

# Option 2: Use environment variables
export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
export AWS_DEFAULT_REGION=us-east-1
```

### Issue 3: Lambda Invocation - Connection Timeout

**Error**: `Cannot connect to orchestrator: Connection timeout`

**Diagnosis**:
```bash
# Check agent endpoint is correct in agent_endpoints.json
cat agent_endpoints.json | jq '.agents.orchestrator'

# Check orchestrator agent is running
aws bedrock-agentcore list-agent-runtimes \
  --profile StandardAccess-450410489798 \
  --region us-east-1
```

**Solution**:
- Verify orchestrator endpoint URL in `agent_endpoints.json`
- Verify agent is READY status
- Check Lambda has network access to agent

### Issue 4: Lambda Invocation - OAuth Token Fails

**Error**: `Failed to acquire OAuth token`

**Diagnosis**:
```bash
# Check Cognito credentials in Lambda environment
aws lambda get-function-configuration \
  --function-name orchestrator-handler-450410489798 \
  --profile StandardAccess-450410489798 \
  --region us-east-1 \
  --query 'Environment.Variables'
```

**Solution**:
- Verify Cognito credentials in `.agentcore.env` are correct
- Re-deploy Lambda with correct credentials:
  ```bash
  python3 scripts/deploy_lambda_api_gateway.py --profile StandardAccess-450410489798 --region us-east-1
  ```

### Issue 5: Dashboard Receives 503 Error

**Error**: `"error": "Agent unavailable"`

**Diagnosis**:
```bash
# Check CloudWatch logs
aws logs tail /aws/lambda/orchestrator-handler-450410489798 \
  --profile StandardAccess-450410489798 \
  --region us-east-1 \
  --follow

# Check if agent endpoint is reachable
curl -v https://agentcore-runtime.us-east-1.amazonaws.com/runtimes/orchestrator_runtime-6UF3HDGyvL/process 2>&1 | head -20
```

**Solution**:
- Wait 30-60 seconds for orchestrator to start (cold start)
- Check agent status is READY
- Check agent has Cognito credentials configured

### Issue 6: Logs Show "Missing Cognito Configuration"

**Error**: `Missing Cognito configuration`

**Solution**:
1. Verify `.agentcore.env` exists and has credentials
2. Re-deploy Lambda:
   ```bash
   python3 scripts/deploy_lambda_api_gateway.py --profile StandardAccess-450410489798
   ```
3. Check Lambda environment variables:
   ```bash
   aws lambda get-function-configuration \
     --function-name orchestrator-handler-450410489798 \
     --query 'Environment.Variables' \
     --profile StandardAccess-450410489798
   ```

---

## 📊 Monitoring

### CloudWatch Metrics

**Lambda Metrics**:
```bash
# Invocations in last hour
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=orchestrator-handler-450410489798 \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --profile StandardAccess-450410489798 \
  --region us-east-1
```

**API Gateway Metrics**:
```bash
# API calls in last hour
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Count \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --profile StandardAccess-450410489798 \
  --region us-east-1
```

### CloudWatch Alarms

Alarms automatically created during deployment:
- **orchestrator-lambda-errors-***: Alert if errors > 5
- **orchestrator-lambda-throttles-***: Alert if throttled
- **orchestrator-lambda-high-duration-***: Alert if duration > 90s

Check alarms:
```bash
aws cloudwatch describe-alarms \
  --profile StandardAccess-450410489798 \
  --region us-east-1 \
  --query 'MetricAlarms[?contains(AlarmName, `orchestrator`)]'
```

---

## 🎉 Success Indicators

After deployment, you should see:

✅ **Lambda Function**
- Created: `orchestrator-handler-450410489798`
- Status: Active
- Runtime: Python 3.11
- Memory: 512 MB
- Timeout: 120 seconds

✅ **API Gateway**
- REST API created
- Resource: `/orchestrate`
- Method: POST
- Integration: Lambda
- Stage: `prod`
- CORS: Enabled

✅ **Endpoints Working**
- curl to API Gateway returns results
- CloudWatch logs show invocations
- Dashboard fetches data from API Gateway

✅ **MCP Tools Verified** (Optional)
- CloudWatch logs show MCP tool keywords
- Work orders, schedules, spare parts returned

---

## 📝 Next Steps

After successful deployment:

1. ✅ **Dashboard fully integrated** - Data flows from Dashboard → API Gateway → Lambda → Agents
2. ✅ **External systems can invoke** - Any HTTPS client can call `/orchestrate`
3. ✅ **Monitoring in place** - CloudWatch logs and alarms track everything
4. ⏭️ **Phase 6: Advanced Features**
   - Add authentication (API key, Cognito)
   - Add request validation
   - Add rate limiting
   - Deploy dashboard to AWS

---

## 📖 Reference Files

- **Handler Code**: [functions/lambda_orchestrator_handler.py](functions/lambda_orchestrator_handler.py)
- **SAM Template**: [functions/template.yaml](functions/template.yaml)
- **Deployment Script**: [scripts/deploy_lambda_api_gateway.py](scripts/deploy_lambda_api_gateway.py)
- **Test Script**: [test_lambda_handler.py](test_lambda_handler.py)
- **Design Reference**: [LAMBDA_API_GATEWAY_REFERENCE.md](LAMBDA_API_GATEWAY_REFERENCE.md)

---

**Created**: 2026-07-23  
**Author**: Agentic AI POC Phase 3.1  
**Status**: Ready for Deployment
