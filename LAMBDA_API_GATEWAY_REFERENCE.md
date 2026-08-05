# Lambda + API Gateway Integration - Quick Reference

**Status**: Design phase - Ready for implementation  
**Target**: Next session work  
**Estimated time**: 2-3 hours  

---

## 🎯 Objective

Enable dashboard and curl to trigger agents without direct AWS network access.

```
curl/Dashboard → API Gateway (HTTPS) → Lambda → AgentCore Agents
```

---

## 📋 Implementation Checklist

### Phase 1: Create Lambda Handler
- [ ] Function: `LambdaOrchestratorHandler`
- [ ] Handler: `lambda_handler(event, context)`
- [ ] Input: API Gateway event (device data)
- [ ] Output: Agent results
- [ ] Timeout: 120 seconds
- [ ] Memory: 512 MB

### Phase 2: Create API Gateway Endpoint
- [ ] Resource: `/orchestrate`
- [ ] Method: `POST`
- [ ] Integration: Lambda
- [ ] CORS: Enable (for dashboard)
- [ ] Auth: Optional (API key or Cognito)
- [ ] Stage: `prod`

### Phase 3: Test
- [ ] curl test
- [ ] CloudWatch logs check
- [ ] Latency measurement
- [ ] Error handling

### Phase 4: Dashboard Integration
- [ ] Update API endpoint URL
- [ ] Add auth headers if needed
- [ ] Display results
- [ ] Error handling

---

## 📦 Lambda Handler Pseudocode

```python
import json
import requests
import os
from datetime import datetime

# Loaded from environment variables set during deployment
ORCHESTRATOR_ENDPOINT = os.getenv('ORCHESTRATOR_ENDPOINT')

def lambda_handler(event, context):
    """
    Invoke orchestrator agent with device data.
    
    Input (from API Gateway):
    {
      "device_id": "motor-004",
      "equipment_type": "MOTOR",
      "current_reading": {"readings": {...}}
    }
    
    Output:
    {
      "statusCode": 200,
      "body": JSON with agent results
    }
    """
    
    print(f"[{datetime.now().isoformat()}] Lambda invoked")
    print(f"Event: {json.dumps(event)[:500]}")
    
    try:
        # Parse incoming request
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        device_id = body.get('device_id')
        equipment_type = body.get('equipment_type')
        current_reading = body.get('current_reading')
        
        # Validate input
        if not all([device_id, equipment_type, current_reading]):
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing required fields: device_id, equipment_type, current_reading'
                })
            }
        
        print(f"Processing device: {device_id} ({equipment_type})")
        
        # Invoke orchestrator agent
        print(f"Calling orchestrator endpoint: {ORCHESTRATOR_ENDPOINT}/process")
        
        response = requests.post(
            f"{ORCHESTRATOR_ENDPOINT}/process",
            json={
                "device_id": device_id,
                "equipment_type": equipment_type,
                "current_reading": current_reading
            },
            timeout=60,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"Orchestrator response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error from orchestrator: {response.text[:500]}")
            return {
                'statusCode': 503,
                'body': json.dumps({
                    'error': f'Agent unavailable: {response.status_code}',
                    'details': response.text[:200]
                })
            }
        
        # Parse agent results
        agent_result = response.json()
        
        print(f"Agent result: {json.dumps(agent_result, indent=2)[:500]}")
        
        # Check for MCP tool usage (for verification)
        mcp_tools_used = agent_result.get('mcp_tools_used', [])
        if mcp_tools_used:
            print(f"✅ MCP tools invoked: {mcp_tools_used}")
        
        # Return successful response
        return {
            'statusCode': 200,
            'body': json.dumps(agent_result),
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'  # For dashboard CORS
            }
        }
    
    except requests.exceptions.Timeout:
        print(f"ERROR: Orchestrator timeout (> 60s)")
        return {
            'statusCode': 504,
            'body': json.dumps({
                'error': 'Agent processing timeout',
                'details': 'Analysis took longer than 60 seconds'
            })
        }
    
    except requests.exceptions.ConnectionError as e:
        print(f"ERROR: Cannot reach orchestrator: {e}")
        return {
            'statusCode': 503,
            'body': json.dumps({
                'error': 'Cannot reach agent endpoint',
                'details': str(e)[:200]
            })
        }
    
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'details': str(e)[:200]
            })
        }
```

---

## 🔌 API Gateway Configuration

### Endpoint Details

```
Endpoint Type: REST API
Base URL: https://{api-id}.execute-api.{region}.amazonaws.com/{stage}

Example:
https://abc123.execute-api.us-east-1.amazonaws.com/prod/orchestrate
```

### Request/Response Examples

**Request**:
```bash
curl -X POST https://api.example.com/orchestrate \
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
  }'
```

**Response (200 OK)**:
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

**Response (503 Service Unavailable)**:
```json
{
  "error": "Agent unavailable",
  "details": "Connection refused"
}
```

---

## 🚀 Deployment Methods

### Option 1: AWS SAM (Recommended)
```yaml
# template.yaml
Resources:
  LambdaFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: lambda_orchestrator_handler.lambda_handler
      Runtime: python3.11
      Timeout: 120
      Memory: 512
      Environment:
        Variables:
          ORCHESTRATOR_ENDPOINT: !Sub 'https://agentcore.../runtimes/orchestrator...'
      Events:
        ApiEvent:
          Type: Api
          Properties:
            RestApiId: !Ref ApiGateway
            Method: POST
            Path: /orchestrate
```

**Deploy**:
```bash
sam build
sam deploy --guided
```

### Option 2: AWS Console (Manual)
1. Lambda console → Create function
2. Name: `orchestrator-handler`
3. Runtime: Python 3.11
4. Copy handler code
5. Set environment variables
6. API Gateway → Create REST API
7. Create POST /orchestrate → Lambda integration
8. Deploy to stage

### Option 3: boto3 (Programmatic)
```python
import boto3

lambda_client = boto3.client('lambda')
apigw_client = boto3.client('apigateway')

# Create Lambda function
lambda_client.create_function(
    FunctionName='orchestrator-handler',
    Runtime='python3.11',
    Handler='lambda_orchestrator_handler.lambda_handler',
    Code={'ZipFile': b'...'},
    Timeout=120,
    MemorySize=512,
    Environment={
        'Variables': {
            'ORCHESTRATOR_ENDPOINT': 'https://...'
        }
    }
)
```

---

## 📊 Testing Checklist

### Test 1: Lambda Function Directly
```python
# In AWS Lambda console, test with:
{
  "body": "{\"device_id\": \"motor-004\", ...}"
}
```

**Expected**: CloudWatch shows successful invocation, agent result returned

### Test 2: API Gateway via curl
```bash
curl -X POST https://api.example.com/orchestrate \
  -H "Content-Type: application/json" \
  -d '{"device_id": "motor-004", ...}'
```

**Expected**: HTTP 200, agent result in response body

### Test 3: CloudWatch Logs
```bash
aws logs tail /aws/lambda/orchestrator-handler --follow
```

**Expected**: See invocation, agent calls, results

### Test 4: Latency Check
```bash
time curl -X POST https://api.example.com/orchestrate -d '{...}'
```

**Expected**: 10-15 seconds (includes agent cold start if scaled to zero)

### Test 5: Error Handling
```bash
# Test with invalid data
curl -X POST https://api.example.com/orchestrate \
  -d '{"device_id": "motor-004"}'  # Missing equipment_type
```

**Expected**: HTTP 400, error message

---

## 🔐 Security Considerations

### Authentication Options

**1. No auth** (for testing):
- ✅ Simple, no overhead
- ❌ Publicly accessible
- Use case: Development only

**2. API Key**:
- ✅ Simple, API Gateway native
- ❌ No user identity tracking
- Use case: Service-to-service

**3. Cognito**:
- ✅ User authentication
- ❌ Complexity in configuration
- Use case: Dashboard (user identities)

**4. IAM** (AWS services only):
- ✅ Fine-grained permissions
- ❌ AWS-only
- Use case: Internal microservices

### Recommended (for now)
```
Development: No auth
Production: Cognito (via dashboard) + API Key (for curl/services)
```

---

## 📈 Monitoring & Observability

### CloudWatch Metrics to Track

- **Invocations**: Successful / Failed
- **Duration**: Min / Max / Average
- **Errors**: Timeout, ConnectionError, ValidationError
- **Cold starts**: Agent spinup time
- **MCP tool usage**: When tools are invoked

### Dashboard Queries

```bash
# Count successful invocations
aws logs filter-log-events \
  --log-group-name /aws/lambda/orchestrator-handler \
  --filter-pattern '"statusCode": 200'

# Find errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/orchestrator-handler \
  --filter-pattern '"statusCode": 5'

# Track latency
aws logs filter-log-events \
  --log-group-name /aws/lambda/orchestrator-handler \
  --filter-pattern '"processing_time_ms"'
```

---

## 💡 Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| "Cannot reach agent endpoint" | Lambda not in VPC / VPC doesn't have NAT | Add Lambda to VPC with NAT gateway |
| Timeout (>60s) | Agent taking too long | Increase Lambda timeout to 120s |
| CORS errors | Browser blocks cross-origin | Enable CORS on API Gateway |
| 503 errors | Orchestrator cold start | Set minInstances=1 for orchestrator |
| High latency | Health/Diagnosis agents cold start | Accept 2-3s cold start or set minInstances=1 |

---

## 📝 Environment Variables (Set During Deployment)

```bash
# Lambda function environment
ORCHESTRATOR_ENDPOINT=https://agentcore-runtime.us-east-1.amazonaws.com/runtimes/orchestrator_runtime-6UF3HDGyvL
AWS_REGION=us-east-1
LOG_LEVEL=INFO
```

**How to set**:
- Lambda console → Configuration → Environment variables
- Or in template.yaml → Environment section
- Or via boto3 client.update_function_configuration()

---

## 🎬 Expected User Flow

### Scenario 1: Dashboard User
```
1. Dashboard loads
2. User clicks "Analyze Device"
3. Dashboard calls: POST /api/orchestrate
4. Browser sends request to API Gateway
5. API Gateway invokes Lambda
6. Lambda calls Orchestrator agent
7. Agent analyzes (10-15 seconds)
8. Results returned through Lambda → API Gateway → Dashboard
9. Dashboard displays results
10. User sees recommendations + work order
```

### Scenario 2: curl Testing
```
1. Tester runs: curl -X POST https://api.../orchestrate -d '{...}'
2. curl sends to API Gateway
3. API Gateway invokes Lambda
4. Lambda calls agent
5. Results printed to terminal
6. Tester can verify MCP tools were used
```

### Scenario 3: Batch Processing
```
1. Scheduled Lambda triggers (EventBridge)
2. Processes 100 devices in a loop
3. Each device invocation reuses agent (no cold starts)
4. Saves results to S3
5. Dashboard later displays batch results
```

---

## ✅ Success Criteria

When complete:
- [ ] Lambda function created and tested
- [ ] API Gateway endpoint deployed
- [ ] curl successfully invokes agents
- [ ] Dashboard can call API Gateway
- [ ] CloudWatch logs show complete flow
- [ ] MCP tool usage verified in logs
- [ ] Latency acceptable (< 30 seconds)
- [ ] Error handling works properly

---

**Status**: Ready for implementation ✅  
**Next**: Create Lambda handler and deploy via SAM
