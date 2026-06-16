# Phase 1 Week 1 Day 1-2: Setup Guide

Complete walkthrough for setting up all AWS resources for Phase 1.

---

## Prerequisites

✅ **Required:**
- Python 3.11+
- AWS account with SSO profile configured
- Permission boundary exists: `GroupIT_ProjectPermissionBoundary`
- AWS CLI configured and authenticated

✅ **Verify Setup:**
```bash
# Check Python version
python --version  # Should be 3.11+

# Check AWS SSO profile
aws configure list --profile your-sso-profile

# Check AWS credentials
aws sts get-caller-identity

# Check permission boundary exists
aws iam get-policy --policy-arn arn:aws:iam::ACCOUNT_ID:policy/GroupIT_ProjectPermissionBoundary
```

---

## Step 1: Project Setup

### 1.1 Create Virtual Environment

```bash
# From project root: /home/skroy/AGENTIC_AI_POC_Phase3_1

# Create virtual environment
python -m venv venv

# Activate it
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate     # On Windows
```

### 1.2 Install Dependencies

```bash
# Install all required packages
pip install -r requirements.txt

# Verify installation
python -c "import boto3; print(f'Boto3 version: {boto3.__version__}')"
```

### 1.3 Create Configuration File

```bash
# Copy template to .env
cp .env.template .env

# Edit .env with your values
# IMPORTANT values to update:
#   - AWS_REGION: us-east-1 (or your preferred region)
#   - AWS_PROFILE: your-sso-profile (your SSO profile name)
#   - AWS_ACCOUNT_ID: your-account-id (12-digit account ID)
#   - PERMISSION_BOUNDARY: GroupIT_ProjectPermissionBoundary (as-is)
#   - COGNITO_TEST_USER_PASSWORD: Choose a strong password (min 8 chars, upper, lower, numbers)
```

**Example .env:**
```ini
AWS_REGION=us-east-1
AWS_PROFILE=my-sso-profile
AWS_ACCOUNT_ID=123456789012
PERMISSION_BOUNDARY=GroupIT_ProjectPermissionBoundary
COGNITO_USER_POOL_NAME=agentic-ai-poc-3-1-user-pool
COGNITO_CLIENT_NAME=agentic-ai-poc-3-1-client
COGNITO_TEST_USER_EMAIL=test@example.com
COGNITO_TEST_USER_PASSWORD=TempPassword123!
DYNAMODB_TABLE_NAME=agentic-ai-poc-3-1-conversation-memory
PROJECT_NAME=agentic-ai-poc-3-1
ENVIRONMENT=development
```

---

## Step 2: Run AWS Resource Setup

### 2.1 Execute Main Setup Script

```bash
# From project root
python scripts/main_setup.py
```

**What it does (in order):**
1. ✅ Validates configuration
2. ✅ Creates 3 IAM roles with permission boundary
   - `agentic-ai-agent-role` (for local agents)
   - `agentic-ai-lambda-execution-role` (for Lambda tools)
   - `agentic-ai-ecs-task-role` (for ECS tools)
3. ✅ Creates Cognito User Pool
   - Creates User Pool for authentication
   - Creates User Pool Client for frontend/API
   - Creates test user for development
4. ✅ Creates DynamoDB table
   - Conversation memory table with Global Secondary Indexes
   - Enables TTL for automatic cleanup

**Expected output:**
```
======================================================================
  🚀 AGENTIC AI POC - PHASE 1 SETUP
======================================================================

📋 Configuration Loaded:
Configuration:
  Region: us-east-1
  Profile: my-sso-profile
  Account ID: 123456789012
  Permission Boundary: GroupIT_ProjectPermissionBoundary
  Environment: development
  
  Cognito Pool: agentic-ai-poc-3-1-user-pool
  DynamoDB Table: agentic-ai-poc-3-1-conversation-memory
  LLM Enabled: False

[... setup progresses ...]

======================================================================
  🎉 SETUP COMPLETE - SUMMARY
======================================================================

✓ IAM Roles Created:
    agent_role: arn:aws:iam::123456789012:role/agentic-ai-agent-role
    lambda_execution_role: arn:aws:iam::123456789012:role/agentic-ai-lambda-execution-role
    ecs_task_role: arn:aws:iam::123456789012:role/agentic-ai-ecs-task-role

✓ Cognito Configuration:
    User Pool ID: us-east-1_xxxxx
    Client ID: yyyyy
    Test Email: test@example.com

✓ DynamoDB Configuration:
    Table Name: agentic-ai-poc-3-1-conversation-memory
    Table ARN: arn:aws:dynamodb:us-east-1:123456789012:table/agentic-ai-poc-3-1-conversation-memory
    Billing Mode: PAY_PER_REQUEST

======================================================================
```

### 2.2 Verify Setup

```bash
# Verify all resources were created correctly
python scripts/main_setup.py verify
```

**Expected output:**
```
🔍 Verifying AWS Resources

Checking IAM Roles...
  ✓ agentic-ai-agent-role
  ✓ agentic-ai-lambda-execution-role
  ✓ agentic-ai-ecs-task-role

Checking Cognito User Pool...
  ✓ agentic-ai-poc-3-1-user-pool (ID: us-east-1_xxxxx)

Checking DynamoDB Table...
  ✓ agentic-ai-poc-3-1-conversation-memory (Status: ACTIVE)

✅ All resources verified!
```

---

## Step 3: Understand What Was Created

### IAM Roles (Permission Boundary Applied)

**agentic-ai-agent-role**
- Used by: Local Python agents on your machine
- Permissions:
  - Call AgentCore Gateway (bedrock:InvokeAgent)
  - Read/write DynamoDB conversation memory
  - Call Cognito for authentication
  - Invoke Lambda tools (MCP-1, MCP-2)
- Permission Boundary: `GroupIT_ProjectPermissionBoundary`

**agentic-ai-lambda-execution-role**
- Used by: Lambda functions (MCP-1, MCP-2) 
- Permissions:
  - CloudWatch logging
  - Read DynamoDB (for device specs/health rules)
  - Read S3 (for rule files)
- Permission Boundary: `GroupIT_ProjectPermissionBoundary`

**agentic-ai-ecs-task-role**
- Used by: ECS Fargate tasks (MCP-3, MCP-4)
- Permissions:
  - CloudWatch logging
  - Read/write DynamoDB
  - Read AWS Secrets Manager (for Azure OpenAI key)
  - Read/write S3
- Permission Boundary: `GroupIT_ProjectPermissionBoundary`

### Cognito User Pool

- **User Pool ID:** `us-east-1_xxxxx` (stored in AWS)
- **Client ID:** Used by frontend/API for JWT tokens
- **Test User:** `test@example.com` / `TempPassword123!` (for development)
- **Token Validity:** 
  - Access token: 1 hour
  - ID token: 1 hour  
  - Refresh token: 30 days

### DynamoDB Table

- **Table Name:** `agentic-ai-poc-3-1-conversation-memory`
- **Partition Key:** `session_id` (unique conversation session)
- **Sort Key:** `timestamp` (when message was sent)
- **Global Secondary Indexes:**
  - `user_id-timestamp-index` (query by user)
  - `device_id-timestamp-index` (query by equipment)
- **TTL:** Automatic cleanup after 30 days inactivity
- **Billing:** Pay-per-request (scales automatically)

---

## Troubleshooting

### "Permission Denied" Error

**Problem:** `AccessDenied` when creating resources

**Solution:**
```bash
# Verify permission boundary exists
aws iam get-policy --policy-arn arn:aws:iam::ACCOUNT_ID:policy/GroupIT_ProjectPermissionBoundary

# Check your AWS permissions
aws iam get-user

# Check CloudTrail for denied actions
aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=CreateRole
```

### "InvalidParameterException" on IAM Role Creation

**Problem:** `The specified value for PermissionsBoundary is not valid.`

**Solution:**
1. Verify permission boundary ARN format: `arn:aws:iam::ACCOUNT_ID:policy/GroupIT_ProjectPermissionBoundary`
2. Verify policy exists: `aws iam get-policy --policy-arn <ARN>`
3. Check permission boundary is accessible by your role

### "Cognito User Pool Already Exists"

**Problem:** Setup skips Cognito creation

**Solution:** This is fine - existing pool is reused. Script will:
- Find the existing pool ID
- Create a new client if needed
- Create test user (or skip if exists)

To use a different pool, delete the old one:
```bash
# ⚠️ WARNING: This deletes all users and data
aws cognito-idp delete-user-pool --user-pool-id us-east-1_xxxxx
```

### DynamoDB Table in "CREATING" Status

**Problem:** Verification shows table is not ACTIVE

**Solution:** Wait 1-2 minutes for table to initialize

```bash
# Check table status
aws dynamodb describe-table --table-name agentic-ai-poc-3-1-conversation-memory --region us-east-1 --profile StandardAccess-450410489798 --query 'Table.TableStatus'

# Expected output: ACTIVE
```

### AWS SSO Profile Not Found

**Problem:** `Unable to locate credentials`

**Solution:**
```bash
# List available profiles
aws configure list-profiles

# Set default profile
export AWS_PROFILE=your-sso-profile

# Or update .env
# AWS_PROFILE=your-sso-profile
```

---

## What's Next?

✅ **Completed:**
- Project structure created
- Virtual environment ready
- AWS resources deployed
- IAM roles with permission boundary
- Cognito User Pool for authentication
- DynamoDB for conversation memory

🔄 **Next (Week 1 Day 3-4):**
- Synthetic sensor data generator
- Ask: "Generate code for Week 1 Day 3-4: Equipment simulator and synthetic data generation"

---

## Environment Variables Reference

All environment variables from `.env`:

| Variable | Example | Required | Purpose |
|----------|---------|----------|---------|
| `AWS_REGION` | `us-east-1` | Yes | AWS region for all resources |
| `AWS_PROFILE` | `my-sso` | Yes | AWS SSO profile name |
| `AWS_ACCOUNT_ID` | `123456789012` | Yes | 12-digit AWS account ID |
| `PERMISSION_BOUNDARY` | `GroupIT_ProjectPermissionBoundary` | Yes | Company policy name |
| `COGNITO_USER_POOL_NAME` | `agentic-ai-poc-3-1-user-pool` | No | User Pool name |
| `COGNITO_CLIENT_NAME` | `agentic-ai-poc-3-1-client` | No | Client app name |
| `COGNITO_TEST_USER_EMAIL` | `test@example.com` | No | Dev test user |
| `COGNITO_TEST_USER_PASSWORD` | `TempPassword123!` | Yes | Dev test password |
| `DYNAMODB_TABLE_NAME` | `agentic-ai-poc-3-1-conversation-memory` | No | Memory table name |
| `PROJECT_NAME` | `agentic-ai-poc-3-1` | No | Versioned project name |
| `DYNAMODB_BILLING_MODE` | `PAY_PER_REQUEST` | No | Billing (PROVISIONED or PAY_PER_REQUEST) |
| `AZURE_OPENAI_API_KEY` | `sk-...` | No | For MCP-3 LLM (optional in Phase 1) |

---

## Cost Estimate (Week 1 Day 1-2)

| Service | Cost | Notes |
|---------|------|-------|
| Cognito | Free | 50K free monthly active users |
| DynamoDB | ~$0.25/month | Pay-per-request, development usage |
| IAM Roles | Free | No charge for role creation |
| **Total** | **~$0.25** | Testing setup cost |

---

## Production Considerations

✅ **What's production-ready in this setup:**
- Permission boundaries applied (company compliance)
- Separate roles for each component (least privilege)
- DynamoDB TTL enabled (cost optimization)
- Logging enabled (CloudWatch)
- Tags applied (cost allocation)

⚠️ **Before production (Phase 2):**
- Enable MFA for AWS account
- Enable CloudTrail logging
- Set up CloudWatch alarms
- Implement encryption keys
- Set resource quotas/limits
- Add VPC security groups

---

## Quick Reference Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Run full setup
python scripts/main_setup.py

# Verify resources created
python scripts/main_setup.py verify

# Check IAM roles
aws iam list-roles | grep agentic-ai

# Check Cognito pool
aws cognito-idp list-user-pools --max-results 10

# Check DynamoDB table
aws dynamodb describe-table --table-name agentic-ai-poc-3-1-conversation-memory --region us-east-1 --profile StandardAccess-450410489798

# View .env
cat .env

# Deactivate virtual environment
deactivate
```

---

## Support

For issues:
1. Check troubleshooting section above
2. Verify .env configuration is correct
3. Run `python scripts/main_setup.py verify`
4. Check AWS CloudTrail for errors
5. Review CloudFormation events if using Terraform (Phase 2)

---

**🎉 Setup Complete! Ready for Week 1 Day 3-4.**
