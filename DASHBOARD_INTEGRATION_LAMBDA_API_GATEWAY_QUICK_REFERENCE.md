# Phase 5: Lambda + API Gateway - Quick Reference Card

**Date**: 2026-07-23  
**Status**: Ready for Deployment  

---

## 🚀 One-Command Deployment

```bash
# Test locally first
python3 test_lambda_handler.py

# Refresh AWS login (if needed)
aws sso login --profile StandardAccess-450410489798 --no-browser

# Deploy to AWS (using boto3 - simple & direct)
AWS_PROFILE=StandardAccess-450410489798 python3 scripts/deploy_lambda_boto3.py
```

**Output**: AWS will display your API endpoint URL (save this!)

---

## 📋 Key Files

| File | Purpose | Location |
|------|---------|----------|
| **Handler Code** | Lambda function | `functions/lambda_orchestrator_handler.py` |
| **Deployment Script** | boto3-based AWS deployment | `scripts/deploy_lambda_boto3.py` |
| **Local Tests** | Validate handler locally | `test_lambda_handler.py` |
| **Full Guide** | Complete deployment guide | `DASHBOARD_INTEGRATION_LAMBDA_API_GATEWAY_DEPLOYMENT_GUIDE.md` |
| **Config File** | Cognito credentials | `.agentcore.env` |

---

## 🧪 Local Testing (Before Deployment)

```bash
# Run all tests
python3 test_lambda_handler.py

# Verbose output
python3 test_lambda_handler.py --verbose

# Expected: All 9 tests pass ✓
```

---

## 🌐 Deployment Steps

### Prerequisites
```bash
# Install SAM CLI
pip install aws-sam-cli

# Verify AWS credentials
aws sts get-caller-identity --profile StandardAccess-450410489798
```

### Deploy

**Option 1: Automated** (Recommended)
```bash
python3 scripts/deploy_lambda_api_gateway.py \
  --profile StandardAccess-450410489798 \
  --region us-east-1
```

**Option 2: Dry-Run** (See what would happen)
```bash
python3 scripts/deploy_lambda_api_gateway.py \
  --profile StandardAccess-450410489798 \
  --region us-east-1 \
  --dry-run
```

**Option 3: Guided** (Interactive prompts)
```bash
python3 scripts/deploy_lambda_api_gateway.py \
  --profile StandardAccess-450410489798 \
  --region us-east-1 \
  --guided
```

### Capture Output

After deployment, save the **API Endpoint URL**:

```bash
# Option 1: From deployment output (copy from screen)
# https://abc123.execute-api.us-east-1.amazonaws.com/prod/orchestrate

# Option 2: Query CloudFormation
aws cloudformation describe-stacks \
  --stack-name orchestrator-handler-stack \
  --profile StandardAccess-450410489798 \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text
```

---

## ✅ Test Deployed Lambda

### Test with curl

Replace `https://YOUR_API_ENDPOINT/orchestrate` with actual endpoint:

```bash
curl -X POST https://YOUR_API_ENDPOINT/orchestrate \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "motor-004",
    "equipment_type": "MOTOR",
    "current_reading": {
      "readings": {
        "current": {"value": 100, "unit": "Amps", "normal_range": [60, 80]},
        "temperature": {"value": 143.19, "unit": "F", "normal_range": [60, 120]}
      }
    }
  }' | jq '.'
```

### View CloudWatch Logs

```bash
# Watch logs in real-time
aws logs tail /aws/lambda/orchestrator-handler-450410489798 \
  --profile StandardAccess-450410489798 \
  --region us-east-1 \
  --follow

# Or view last 20 lines
aws logs tail /aws/lambda/orchestrator-handler-450410489798 \
  --profile StandardAccess-450410489798 \
  --region us-east-1 \
  --max-items 20
```

### Check MCP Tools Executed

```bash
# Filter for MCP tool keywords
aws logs filter-log-events \
  --log-group-name /aws/lambda/orchestrator-handler-450410489798 \
  --filter-pattern "MCP OR access_token OR tool" \
  --profile StandardAccess-450410489798 \
  --region us-east-1
```

---

## 🎯 Dashboard Integration

### Step 1: Update Config

Edit `src/dashboard/config.py`:

```python
# Change from:
ORCHESTRATOR_URL: str = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000")

# To:
ORCHESTRATOR_URL: str = os.getenv(
    "ORCHESTRATOR_URL",
    "https://abc123.execute-api.us-east-1.amazonaws.com/prod/orchestrate"
)
```

### Step 2: Start Dashboard

```bash
# Terminal 1: Dashboard API
cd src/dashboard
python3 -m uvicorn main:app --host 0.0.0.0 --port 8080

# Terminal 2: Test
curl http://localhost:8080/api/fleet-summary | jq '.devices[0]'
```

### Step 3: Verify Data Flow

```bash
# Fleet summary (real agent data)
curl http://localhost:8080/api/fleet-summary | jq '.total_devices'

# Work orders (from MCP tools)
curl http://localhost:8080/api/work-orders | jq '.total'

# Maintenance schedules
curl http://localhost:8080/api/maintenance-schedule | jq '.schedules | length'
```

---

## 🔧 Configuration Environment Variables

**Lambda needs these environment variables** (set during deployment):

| Variable | Value | Source |
|----------|-------|--------|
| `ORCHESTRATOR_ENDPOINT` | Agent endpoint URL | `agent_endpoints.json` |
| `COGNITO_APP_CLIENT_ID` | OAuth2 client ID | `.agentcore.env` |
| `COGNITO_APP_CLIENT_SECRET` | OAuth2 client secret | `.agentcore.env` |
| `COGNITO_TOKEN_ENDPOINT` | Cognito token URL | `.agentcore.env` |
| `COGNITO_SCOPE` | OAuth2 scope | `.agentcore.env` (default: `agentcore/invoke`) |
| `GATEWAY_URL` | MCP gateway URL | `.agentcore.env` |
| `LOG_LEVEL` | Logging level | Default: `INFO` |

**Deployment script reads these automatically** from `.agentcore.env` and `agent_endpoints.json`

---

## 🚨 Common Issues & Fixes

### Lambda Fails to Start
```bash
# Check CloudWatch logs
aws logs tail /aws/lambda/orchestrator-handler-450410489798 \
  --profile StandardAccess-450410489798 \
  --region us-east-1 \
  --follow

# If missing Cognito credentials, re-deploy:
python3 scripts/deploy_lambda_api_gateway.py \
  --profile StandardAccess-450410489798 \
  --region us-east-1
```

### Can't Reach Agent
```bash
# Verify agent is running
aws bedrock-agentcore list-agent-runtimes \
  --profile StandardAccess-450410489798 \
  --region us-east-1

# Verify endpoint in agent_endpoints.json
cat agent_endpoints.json | jq '.agents.orchestrator'
```

### Dashboard Shows 503 Error
```bash
# Check if Lambda is receiving requests
aws logs tail /aws/lambda/orchestrator-handler-450410489798 \
  --profile StandardAccess-450410489798 \
  --region us-east-1 \
  --follow

# Check if orchestrator endpoint is reachable
curl -v https://agentcore-runtime.us-east-1.amazonaws.com/runtimes/orchestrator_runtime-6UF3HDGyvL/process
```

### OAuth Token Fails
```bash
# Verify Cognito credentials are correct in .agentcore.env
cat .agentcore.env | grep COGNITO

# Test token directly
curl -X POST https://agentic-ai-poc-3-1-auth.auth.us-east-1.amazoncognito.com/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&scope=agentcore/invoke" \
  -u "51iaqr9v3eupu65dnm8fi8alkj:16ifnrr9f96ddibphfnivbldhuln75o6rei4rirpnfhpcc6c9vt3"
```

---

## 📊 AWS Console Quick Links

**After Deployment**, find resources in AWS Console:

- **Lambda Function**: Search for `orchestrator-handler` in Lambda console
- **API Gateway**: Search for `orchestrator-api` in API Gateway console
- **CloudWatch Logs**: `/aws/lambda/orchestrator-handler-450410489798`
- **CloudFormation**: Stack name `orchestrator-handler-stack`
- **IAM Role**: `orchestrator-lambda-role-450410489798`

---

## ⏱️ Expected Times

| Step | Time | Notes |
|------|------|-------|
| Local tests | 2-3 min | ~9 tests |
| SAM build | 3-5 min | Packages dependencies |
| Deployment | 5-10 min | Creates resources |
| First curl test | < 1 min | May have 2-3s cold start |
| Dashboard integration | 2-3 min | Just config change |

**Total**: ~20-30 minutes from start to dashboard working

---

## 🎯 Success Checklist

After completion:

- [ ] Local tests all pass (9/9)
- [ ] SAM deployment succeeds
- [ ] API Gateway endpoint created
- [ ] Lambda function created
- [ ] curl test returns agent results
- [ ] CloudWatch logs show invocation
- [ ] Dashboard config updated
- [ ] Dashboard fetches data from Lambda endpoint
- [ ] Dashboard shows real device data
- [ ] MCP tools appear in logs (if applicable)

---

## 📚 Full Documentation

For detailed information, see:
- **[PHASE5_LAMBDA_DEPLOYMENT_GUIDE.md](PHASE5_LAMBDA_DEPLOYMENT_GUIDE.md)** - Complete guide
- **[LAMBDA_API_GATEWAY_REFERENCE.md](LAMBDA_API_GATEWAY_REFERENCE.md)** - Design & reference
- **[functions/template.yaml](functions/template.yaml)** - Infrastructure code
- **[functions/lambda_orchestrator_handler.py](functions/lambda_orchestrator_handler.py)** - Handler implementation

---

**Quick Help**: `python3 scripts/deploy_lambda_api_gateway.py --help`

**Questions?** See PHASE5_LAMBDA_DEPLOYMENT_GUIDE.md → Troubleshooting section
