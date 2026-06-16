# Week 2 Day 1-4: Step-by-Step Implementation

**Format:** You complete each step, then I brief you on the next step and provide code when requested.

---

## Architecture Summary (Updated)

**Two Separate S3 Buckets:**

1. **MCP Tools Bucket** (Phase 1 now)
   - Name: `agentic-ai-poc-3-1-mcp-tools`
   - Contains: `mcp/spare_parts_inventory.json` (only MCP tools data)
   - Access: Lambda/ECS functions read from here
   - Setup: You'll do this in Step 2

2. **Sensor Data Bucket** (Phase 2+)
   - Name: `agentic-ai-poc-3-1-sensor-data`
   - Contains: `devices/device-*.json`, `motor-*.json`, etc.
   - Access: Agents will read from here when they move to AWS
   - Setup: Later (agents stay local for Phase 1)

**Local Data (Phase 1):**
- Agents read from: `data/generated/` locally (sensor data)
- MCP tools read from: `data/mcp-tools/` locally (spare parts inventory)
- **MCP tools → S3 now** (Lambda/ECS functions need it immediately in Step 2)
- **Sensor data → S3 later** (Phase 2, when agents move to AWS)
- Summary: MCP data uploads to S3 in Phase 1, sensor data uploads in Phase 2

---

## Step 1: Generate MCP Tools Data Locally

**Objective:** Create the JSON data files that MCP tools will use (spare parts inventory).

**What to do:**
1. Generate spare parts inventory file
2. Verify it was created
3. Check the file content briefly

**When done:** Tell me "Step 1 complete" and I'll brief you on Step 2.

---

## Running Commands

**Step 1 Command:**
```bash
python -m src.data.inventory_data_generator --output-dir data/mcp-tools
```

**Verify:**
```bash
ls -lh data/mcp-tools/spare_parts_inventory.json
cat data/mcp-tools/spare_parts_inventory.json | head -50
```

**Expected:**
- File created: `data/mcp-tools/spare_parts_inventory.json`
- File contains 8 spare parts in `{"spare_parts": [...]}` array format
- Each part has: `part_type`, `part_id`, `part_name`, `category`, `stock_quantity`, `unit_cost`
- Valid `part_type` values: bearing, seal, valve, component, coil, fan, regulator, impeller
- File size ~2-3 KB

---

## Step 2: Upload MCP Tools Data to S3

**Objective:** Upload the spare parts inventory to S3 bucket that Lambda/ECS tools will read from.

**What to do:**
1. Create S3 bucket: `agentic-ai-poc-3-1-mcp-tools`
2. Upload `spare_parts_inventory.json` to S3
3. Configure bucket permissions for Lambda/ECS access
4. Verify upload succeeded

**When done:** Tell me "Step 2 complete" and I'll brief you on Step 3.

---

## Step 2 Command

**Upload to S3:**
```bash
python scripts/setup_s3_for_mcp_tools.py \
  --bucket-name agentic-ai-poc-3-1-mcp-tools \
  --data-dir data/mcp-tools \
  --file-filter spare_parts_inventory.json \
  --region us-east-1 \
  --output-summary s3_mcp_setup_summary.txt
```

**Verify:**
```bash
cat s3_mcp_setup_summary.txt
```

**Expected:**
- Bucket created: `agentic-ai-poc-3-1-mcp-tools`
- File uploaded: `spare_parts_inventory.json`
- Summary shows upload location and S3 URL
- Summary file size ~1-2 KB

---

## Step 3: Define MCP Tool Schemas

**Objective:** Create the tool definitions that AgentCore Gateway will use to route requests to Lambda/ECS functions.

**What to do:**
1. Create `tools/schemas/` directory
2. Create 3 JSON schema files (get_spare_parts, schedule_maintenance, create_work_order)
3. Each schema defines input/output parameters

**When done:** Tell me "Step 3 complete" and I'll brief you on Step 4.

---

## Step 3: Commands

**Create directory:**
```bash
mkdir -p tools/schemas
```

**Create get_spare_parts.json:**
```bash
cat > tools/schemas/get_spare_parts.json << 'EOF'
{
  "name": "get_spare_parts",
  "description": "Get available spare parts matching specified criteria",
  "inputSchema": {
    "type": "object",
    "properties": {
      "part_type": {
        "type": "string",
        "description": "Type of spare part to search for (e.g., bearing, seal, filter)"
      },
      "category": {
        "type": "string",
        "description": "Optional category filter (e.g., mechanical, electrical, hydraulic)"
      }
    },
    "required": ["part_type"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "parts": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "part_id": {"type": "string"},
            "part_name": {"type": "string"},
            "category": {"type": "string"},
            "stock_quantity": {"type": "integer"},
            "unit_cost": {"type": "number"}
          }
        }
      },
      "count": {"type": "integer"}
    }
  }
}
EOF
```

**Create schedule_maintenance.json:**
```bash
cat > tools/schemas/schedule_maintenance.json << 'EOF'
{
  "name": "schedule_maintenance",
  "description": "Schedule maintenance for a device",
  "inputSchema": {
    "type": "object",
    "properties": {
      "device_id": {
        "type": "string",
        "description": "ID of the device to schedule maintenance for"
      },
      "maintenance_type": {
        "type": "string",
        "description": "Type of maintenance (e.g., preventive, corrective, inspection)"
      },
      "scheduled_date": {
        "type": "string",
        "description": "Scheduled date (YYYY-MM-DD format)"
      }
    },
    "required": ["device_id", "maintenance_type", "scheduled_date"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "maintenance_id": {"type": "string"},
      "device_id": {"type": "string"},
      "status": {"type": "string"},
      "scheduled_date": {"type": "string"}
    }
  }
}
EOF
```

**Create create_work_order.json:**
```bash
cat > tools/schemas/create_work_order.json << 'EOF'
{
  "name": "create_work_order",
  "description": "Create a new work order",
  "inputSchema": {
    "type": "object",
    "properties": {
      "work_order_type": {
        "type": "string",
        "description": "Type of work order (e.g., repair, installation, inspection)"
      },
      "priority": {
        "type": "string",
        "description": "Priority level (critical, high, medium, low)"
      },
      "description": {
        "type": "string",
        "description": "Detailed description of the work to be done"
      }
    },
    "required": ["work_order_type", "priority", "description"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "work_order_id": {"type": "string"},
      "status": {"type": "string"},
      "created_at": {"type": "string"}
    }
  }
}
EOF
```

**Verify:**
```bash
ls -lh tools/schemas/
cat tools/schemas/get_spare_parts.json | head -20
```

**Expected:**
- Directory created: `tools/schemas/`
- 3 JSON files created with proper schema definitions
- Each file ~300-400 bytes
- All files are valid JSON

---

## Step 4: Create Lambda Functions for MCP Tools

**Objective:** Deploy 2 Lambda functions that serve as MCP tools (get_spare_parts and schedule_maintenance).

**Step 4 has 4 sub-steps:**
- Step 4a: Create DynamoDB tables (maintenance_schedules, work_orders)
- Step 4b: Create Lambda function code
- Step 4c: Create IAM execution role
- Step 4d: Deploy functions to AWS

**When all 4 sub-steps complete:** Tell me "Step 4 complete" and I'll brief you on Step 5.

---

## Step 4a: Create DynamoDB Tables

**Objective:** Create 2 DynamoDB tables for Lambda functions to write data.

**Tables to create:**
1. `maintenance_schedules` - stores scheduled maintenance records
2. `work_orders` - stores urgent work order records

**Command:**

```bash
export AWS_PROFILE=StandardAccess-450410489798
python scripts/setup_dynamodb_for_mcp_tools.py \
  --region us-east-1 \
  --output-summary dynamodb_setup_summary.txt \
  --verbose
```

**What this does:**
- Creates `maintenance_schedules` table with indexes for device queries
- Creates `work_orders` table with indexes for priority queries
- Waits for tables to become ACTIVE
- Saves summary to `dynamodb_setup_summary.txt`

**Verify:**
```bash
cat dynamodb_setup_summary.txt
```

**Expected:**
- Table: `maintenance_schedules` (ACTIVE)
- Table: `work_orders` (ACTIVE)
- Both with on-demand billing (PAY_PER_REQUEST)
- Global Secondary Indexes created
- Summary shows table ARNs

---

## Step 4b: Create Lambda Function Code

**Objective:** Review Lambda handler code for the 2 functions.

**Handler files created:**
1. `tools/lambdas/get_spare_parts_handler.py` (reads from S3)
2. `tools/lambdas/schedule_maintenance_handler.py` (writes to DynamoDB)

**Review the code:**

```bash
# View get_spare_parts handler
cat tools/lambdas/get_spare_parts_handler.py | head -80

# View schedule_maintenance handler
cat tools/lambdas/schedule_maintenance_handler.py | head -80
```

**Handler 1: get_spare_parts**
- Reads inventory from S3: `s3://agentic-ai-poc-3-1-mcp-tools/data/spare_parts_inventory.json`
- Input: `part_type` (required), `category` (optional)
- Output: List of matching spare parts with stock info
- Logic:
  1. Read S3 file
  2. Filter by part_type (case-insensitive)
  3. Optional: filter by category
  4. Return matching parts or empty list

**Handler 2: schedule_maintenance**
- Writes to DynamoDB: `maintenance_schedules` table
- Input: `device_id`, `maintenance_type`, `scheduled_date`
- Output: maintenance_id, status, confirmation
- Logic:
  1. Validate inputs (date format, maintenance_type)
  2. Generate unique maintenance_id: `MAINT-YYYYMMDD-XXXXXX`
  3. Write record to DynamoDB
  4. Return confirmation with maintenance_id

**Environment Variables (needed for deployment):**
- `MCP_TOOLS_BUCKET`: S3 bucket name (default: agentic-ai-poc-3-1-mcp-tools)
- `MAINTENANCE_TABLE`: DynamoDB table name (default: maintenance_schedules)

**When ready:** Tell me "Step 4b reviewed" and I'll provide Step 4c (IAM role + deployment)

---

## Step 4c: Create IAM Execution Role


**Objective:** Create IAM role for Lambda functions with permissions and permission boundary.

**Permissions needed:**
- Read from S3 bucket: `agentic-ai-poc-3-1-mcp-tools`
- Write to DynamoDB tables: `maintenance_schedules`, `work_orders`
- CloudWatch Logs for debugging
- **Permission boundary:** `GroupIT_ProjectPermissionBoundary` (from .env)

**How to run:**
Run the deployment script below. It will create or update the IAM role automatically with the correct permissions and permission boundary.

```bash
python scripts/deploy_mcp_lambdas.py
```

**What this does:**
- Creates/updates the IAM role with all required permissions and the permission boundary
- Packages and deploys both Lambda functions
- Sets environment variables
- Tests each Lambda with a sample event

**No manual IAM setup needed!**

---

## Notes on 4c


**Objective:** Package and deploy Lambda function code to AWS Lambda.

**How to run:**
Just run the deployment script (see above). It will handle packaging, deployment, environment variables, and testing.

**What does "package" mean for Lambda?**
- AWS Lambda needs your code (and any extra libraries) zipped into a single file called a "deployment package".
- For simple functions (no extra libraries), just zip the .py file.
- If you use extra libraries, you must include them in the zip too.
- The deployment script does this for you automatically.

**What the script does:**
1. Zips each Lambda handler file (and dependencies if needed)
2. Uploads to AWS Lambda (creates or updates the function)
3. Sets environment variables (like S3 bucket and DynamoDB table names)
4. Invokes each Lambda with a test event and prints the response

**Verify:**
- Check the script output for "Deployment complete." and Lambda responses.

**If you need to update code:**
- Edit the handler .py files, then re-run the script.

**No manual zipping or AWS Console steps needed!**

---

## Next: Hybrid Agent Decision Logic (Reference)
---

## Step 5: Create ECS Task for create_work_order

---





**Objective:** Deploy the create_work_order tool as a FastAPI app running on AWS ECS Fargate.

**Step 5 has 7 sub-steps:**
- Step 5a: Create FastAPI app (app.py)
- Step 5b: Write requirements.txt
- Step 5c: Write Dockerfile
- Step 5d: Build Docker image
- Step 5e: Push image to ECR
- Step 5f: Create ECS task definition
- Step 5g: Deploy to ECS Fargate and test

---

### Step 5a: Create FastAPI app

**File:** `src/ecs_tasks/create_work_order/app.py`

**What to do:**
- Implement a FastAPI app with a POST endpoint `/work_order` that accepts JSON and returns a work order with a unique ID and timestamp.

**Example:**
```python
from fastapi import FastAPI, Request
from pydantic import BaseModel
from datetime import datetime
import uuid

app = FastAPI()

class WorkOrderRequest(BaseModel):
  work_order_type: str
  priority: str
  description: str

class WorkOrderResponse(BaseModel):
  work_order_id: str
  status: str
  created_at: str

@app.post("/work_order", response_model=WorkOrderResponse)
async def create_work_order(req: WorkOrderRequest):
  work_order_id = f"WO-{uuid.uuid4().hex[:8]}"
  created_at = datetime.utcnow().isoformat()
  return WorkOrderResponse(
    work_order_id=work_order_id,
    status="created",
    created_at=created_at
  )
```

---

### Step 5b: Write requirements.txt

**File:** `src/ecs_tasks/create_work_order/requirements.txt`

**Contents:**
```
fastapi
uvicorn
boto3
```

---

### Step 5c: Write Dockerfile

**File:** `src/ecs_tasks/create_work_order/Dockerfile`

**Example:**
```
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py ./
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### Step 5d: Build Docker image

**Command:**
```bash
sudo service docker start
```

```bash
docker build -t create-work-order:latest src/ecs_tasks/create_work_order
```

# To test it locally before pushing and depoying to AWS
```bash
docker run -p 8000:8000 create-work-order:latest
```
```bash
curl -X POST http://localhost:8000/work_order \
  -H "Content-Type: application/json" \
  -d '{"work_order_type": "repair", "priority": "high", "description": "Fix leaking valve"}'
```
---


### Step 5e: Push image to ECR

**Recommended:** Use the provided shell script to automate all ECR steps:

```bash
bash scripts/push_create_work_order_to_ecr.sh
```

This script will:
- Ensure the ECR repository exists
- Authenticate Docker to ECR
- Tag your image
- Push it to 450410489798.dkr.ecr.us-east-1.amazonaws.com/create-work-order:latest

**Manual steps (if you prefer):**
1. Create an ECR repository (if not already done):
  ```bash
  aws ecr create-repository --repository-name create-work-order
  ```
2. Authenticate Docker to ECR:
  ```bash
  aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 450410489798.dkr.ecr.us-east-1.amazonaws.com
  ```
3. Tag and push the image:
  ```bash
  docker tag create-work-order:latest 450410489798.dkr.ecr.us-east-1.amazonaws.com/create-work-order:latest
  docker push 450410489798.dkr.ecr.us-east-1.amazonaws.com/create-work-order:latest
  ```

---

### Step 5f: Create ECS task definition
Check the notes section first below.
**Recommended:** Use the provided shell script to automate ECS task definition and deployment:

```bash
bash scripts/deploy_create_work_order_ecs.sh <ECR_IMAGE_URL>
```

Replace `<ECR_IMAGE_URL>` with your pushed image, e.g.:
`450410489798.dkr.ecr.us-east-1.amazonaws.com/create-work-order:latest`

This script will:
- Register the ECS task definition (Fargate, port 8000)
- Ensure the ECS cluster exists
- Create or update the ECS service

### Step 5g: Notes: Network Setup for ECS (not used; check 5g (b))

**Objective:** Create a custom VPC, subnet, and security group for your ECS service. (was not allowed so tried app runner instead of fargate base ecs deployment)

**Script provided:**
```bash
bash scripts/create_agentic_ai_roy_vpc.sh
```
This will create:
- VPC named agentic-ai-roy
- Subnet in that VPC
- Security group named ECS-SG (with inbound port 8000 open)

**After running, note the output:**
- VPC ID
- Subnet ID
- Security Group ID

You will use the Subnet ID and Security Group ID in the ECS deployment script (Step 5f).

**IMPORTANT:**
- You must edit the script to set your actual subnet and security group IDs in the --network-configuration section.
- The script is idempotent: you can re-run it to update the service with a new image.

Manual steps are still listed below for reference if you want to do it via AWS Console or CLI.

---

### Step 5g (a): Deploy to ECS Fargate and test (not used; instead app runner; check below)

**If you used the script above,** your service will be deployed automatically. To test:
1. Get the public endpoint (ALB or public IP) from the ECS service details in the AWS Console.
2. Test the endpoint:
  ```bash
  curl -X POST <ECS-ENDPOINT>/work_order \
    -H "Content-Type: application/json" \
    -d '{"work_order_type": "repair", "priority": "high", "description": "Fix leaking valve"}'
  ```
3. You should get a JSON response with work_order_id, status, and created_at

---
### Step 5g(b):

## Deploying MCP Tool with AWS App Runner (Recommended; vpc creation is not allowed so ecs container could not be deployed; App runner is going to be used as an alternative)

As ECS Fargate/VPC is not allowed, use AWS App Runner for a simple, production-ready deployment with a public HTTPS endpoint.

### Steps:
1. **Push your Docker image to ECR** (see Step 5e).
2. **Create an IAM role** with the `AmazonEC2ContainerRegistryReadOnly` policy for App Runner to pull your image:
   - Run the provided script to automate this step:
     ```bash
     python scripts/create_apprunner_ecr_pull_role.py
     ```
   - This will create the role with the required policy and permission boundary. Note the role ARN printed by the script for the next step.

3. **Deploy with App Runner:**
#command: bash scripts/deploy_create_work_order_apprunner.sh 450410489798.dkr.ecr.us-east-1.amazonaws.com/create-work-order:latest arn:aws:iam::450410489798:role/apprunner-ecr-pull-role StandardAccess-450410489798

This is just here as  a note:
  ```bash
  aws apprunner create-service \
    --service-name create-work-order-apprunner \
    --source-configuration '{
      "ImageRepository": {
        "ImageIdentifier": "450410489798.dkr.ecr.us-east-1.amazonaws.com/create-work-order:latest",
        "ImageRepositoryType": "ECR"
      },
      "AuthenticationConfiguration": {
        "AccessRoleArn": "arn:aws:iam::450410489798:role/apprunner-ecr-pull-role"
      }
    }' \
    --region us-east-1 \
    --profile StandardAccess-450410489798
  ```
  - Update the values if your ECR image or IAM role ARN are different.

4. **Get the Service URL:**
  - Run the commands printed by the script to get your App Runner ServiceUrl.

5. **Test the endpoint:**
  ```bash
  curl -X POST https://tisvuktmqa.us-east-1.awsapprunner.com/work_order   -H "Content-Type: application/json"   -d '{"work_
order_type": "repair", "priority": "high", "description": "Fix leaking valve"}'
  ```
### service url is: https://tisvuktmqa.us-east-1.awsapprunner.com

6. **Configure AgentCore Gateway:**
  - Use the App Runner ServiceUrl as the endpoint for your MCP tool.

---

## Step 6: AgentCore Gateway + Cognito OAuth (Starter Kit Workflow)

**Objective:** Use the Python starter-kit scripts in the `scripts/` directory to create the gateway, register tools, and validate auth.

### 6a) Validate Cognito App Client OAuth settings

**What this script does (simple):**
- Checks if Cognito app client is ready for OAuth login.
- Verifies OAuth is enabled, `code` flow is enabled, and required scopes exist.

Run from project root:

```bash
python scripts/check_cognito_app_client_oauth.py \
  --profile StandardAccess-450410489798 \
  --region us-east-1
```

**Must pass:**
- OAuth flows enabled
- `code` flow present
- scopes include `openid` and `email`

If it fails, auto-fix using:

**What this fix script does (simple):**
- Turns on OAuth for the app client.
- Enables Authorization Code flow (`code`).
- Adds required scopes (`openid`, `email`).
- Adds callback/logout URLs you pass in command.

```bash
python scripts/fix_cognito_app_client_oauth.py \
  --profile StandardAccess-450410489798 \
  --region us-east-1 \
  --callback-url http://localhost:3000/callback \
  --logout-url http://localhost:3000/logout
```

Then re-check with the first command.

### 6b) Create AgentCore Gateway (starter kit)

**What this script does (simple):**
- Creates AgentCore Gateway.
- Configures gateway auth with Cognito.
- Creates/uses gateway execution IAM role.
- Saves gateway details in `gateway_info.json`.

```bash
python scripts/create_agentcore_gateway_starter.py
```

**Output:** `gateway_info.json` (gateway ID + gateway URL).

### 6c) Register MCP tools (starter kit)

**What this script does (simple):**
- Registers your 3 MCP tools with the gateway:
  - `get-spare-parts` (Lambda) — via starter toolkit
  - `schedule-maintenance` (Lambda) — via starter toolkit
  - `create-work-order` (App Runner HTTP endpoint) — via direct boto3 (see note below)
- Uses values from `.agentcore.env`.
- Script is **idempotent**: already-registered tools are skipped automatically.

> **⚠️ Note on App Runner tool registration:**  
> The `create-work-order` (App Runner) tool is registered differently from Lambda tools.  
> The starter toolkit crashes on `openApiSchema` targets for public endpoints, so the script calls `boto3 bedrock-agentcore-control` directly with:
> - Target type: `openApiSchema` (OpenAPI 3.0 spec)
> - Credentials: `GATEWAY_IAM_ROLE` + `iamCredentialProvider { service: apprunner, region: us-east-1 }`
>
> Target names must use hyphens (AWS rejects underscores): `get-spare-parts`, `schedule-maintenance`, `create-work-order`.

```bash
python scripts/register_mcp_tools_starter.py
```

### 6d) Test gateway + tool invocation (starter kit)

**What this script does (simple):**
- Always checks registered targets via AgentCore control-plane.
- If `COGNITO_APP_CLIENT_SECRET` + `COGNITO_TOKEN_ENDPOINT` are set:
  - Gets an auth token using Cognito.
  - Calls gateway `tools/list`.
  - Calls sample tools (`get_spare_parts`, `schedule_maintenance`, `create_work_order`) to confirm end-to-end connectivity.
- If those optional vars are missing, it skips token/data-plane checks and reports how to enable them.

```bash
python scripts/test_agentcore_gateway_starter_1.py
```

### 6e) Required config file

All scripts above read from `.agentcore.env` (copied from `.agentcore.env.example`).

Required keys include:
- `AWS_REGION`
- `AWS_PROFILE`
- `COGNITO_USER_POOL_ID`
- `COGNITO_APP_CLIENT_ID`
- `GET_SPARE_PARTS_LAMBDA_ARN`
- `SCHEDULE_MAINTENANCE_LAMBDA_ARN`
- `CREATE_WORK_ORDER_URL`

Optional (for data-plane token test in `test_agentcore_gateway_starter.py`):
- `COGNITO_APP_CLIENT_SECRET`
- `COGNITO_TOKEN_ENDPOINT` (example: `https://<your-cognito-domain>.auth.us-east-1.amazoncognito.com/oauth2/token`)

### 6f) Exact commands to enable agent→gateway Cognito token flow

Use these commands when you want full end-to-end data-plane test (`tools/list` + `tools/call`) and later Day 5-7 agent runtime.

#### Automated (recommended)

Run a single script that performs all steps below, then writes results back to `.agentcore.env`:

```bash
python scripts/setup_cognito_token_flow.py
```

This script:
- Creates resource server (`agentcore`) with scope `invoke`
- Creates Cognito hosted domain (`agentic-ai-poc-3-1-auth`)
- Creates confidential app client with `client_credentials` flow
- Updates `.agentcore.env` with: `COGNITO_APP_CLIENT_ID`, `COGNITO_APP_CLIENT_SECRET`, `COGNITO_TOKEN_ENDPOINT`, `COGNITO_SCOPE`
- Is **idempotent** — safe to re-run (skips existing resources)

After the script completes, you must recreate the gateway (so `allowedClients` includes the new client):
```bash
# Delete old gateway first (section 6g), then:
python scripts/create_agentcore_gateway_starter.py
python scripts/register_mcp_tools_starter.py
python scripts/test_agentcore_gateway_starter.py
```

#### Manual steps (reference)

If you prefer to run individual AWS CLI commands instead:

```bash
cd /home/skroy/AGENTIC_AI_POC_Phase3_1
source venv/bin/activate

export AWS_PROFILE=StandardAccess-450410489798
export AWS_REGION=us-east-1
export USER_POOL_ID=us-east-1_R6pOfxcKV
export DOMAIN_PREFIX=agentic-ai-poc-3-1-auth
```

Create resource server + scope (used by client credentials tokens):

```bash
aws cognito-idp create-resource-server \
  --user-pool-id "$USER_POOL_ID" \
  --identifier "agentcore" \
  --name "agentcore" \
  --scopes ScopeName=invoke,ScopeDescription="Invoke AgentCore Gateway" \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE"
```

Create Cognito hosted domain (for `/oauth2/token` endpoint):

```bash
aws cognito-idp create-user-pool-domain \
  --user-pool-id "$USER_POOL_ID" \
  --domain "$DOMAIN_PREFIX" \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE"
```

Create confidential app client (with secret) for agent/service-to-service calls:

```bash
aws cognito-idp create-user-pool-client \
  --user-pool-id "$USER_POOL_ID" \
  --client-name "agentic-ai-poc-3-1-confidential-client" \
  --generate-secret \
  --allowed-o-auth-flows client_credentials \
  --allowed-o-auth-scopes agentcore/invoke \
  --allowed-o-auth-flows-user-pool-client \
  --supported-identity-providers COGNITO \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE"
```

Find the new client ID:

```bash
aws cognito-idp list-user-pool-clients \
  --user-pool-id "$USER_POOL_ID" \
  --max-results 60 \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE"
```

Get client ID + secret (replace `<NEW_CLIENT_ID>`):

```bash
aws cognito-idp describe-user-pool-client \
  --user-pool-id "$USER_POOL_ID" \
  --client-id "<NEW_CLIENT_ID>" \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE" \
  --query 'UserPoolClient.[ClientId,ClientSecret]' \
  --output text
```

Then set these in `.agentcore.env`:

```dotenv
COGNITO_APP_CLIENT_ID=<NEW_CLIENT_ID>
COGNITO_APP_CLIENT_SECRET=<NEW_CLIENT_SECRET>
COGNITO_TOKEN_ENDPOINT=https://agentic-ai-poc-3-1-auth.auth.us-east-1.amazoncognito.com/oauth2/token
COGNITO_SCOPE=agentcore/invoke
```

### 6g) Optional cleanup only (run only if you intentionally recreate the gateway)

You do **not** need to delete the gateway in normal flow.

Run this section only if:
- you intentionally want a fresh gateway, or
- gateway auth config changed and you want clean re-creation.

If delete-gateway fails because targets exist, remove targets first:

```bash
aws bedrock-agentcore-control list-gateway-targets \
  --gateway-identifier <GATEWAY_ID> \
  --region us-east-1 \
  --profile StandardAccess-450410489798 \
  --query 'items[].targetId' --output text
```

```bash
aws bedrock-agentcore-control delete-gateway-target \
  --gateway-identifier <GATEWAY_ID> \
  --target-id <TARGET_ID> \
  --region us-east-1 \
  --profile StandardAccess-450410489798
```

```bash
aws bedrock-agentcore-control delete-gateway \
  --gateway-identifier <GATEWAY_ID> \
  --region us-east-1 \
  --profile StandardAccess-450410489798
```

### 6g-Plus) Technical Note: GatewayClient Roles (Phase 1-5 Preview)

**Important distinction for upcoming agent updates (Day 5-7):**
- **AWS Bedrock AgentCore Starter Toolkit's `GatewayClient`** (in `.venv/lib/python3.x/site-packages/`)
  - Purpose: Infrastructure setup only (create gateways, register targets)
  - Usage: Scripts like `create_agentcore_gateway_starter.py`, `register_mcp_tools_starter.py`
  - Runtime: NOT used by agents (one-time setup, not called per tool request)

- **Custom `GatewayClient` in `src/gateway/client.py`** (your project code)
  - Purpose: Runtime tool invocation (what agents use to call tools)
  - Usage: Agents import and initialize this client to call MCP tools
  - Runtime: Agents use this every time they need a tool (multiple times per execution)
  - Handles: Token caching, refreshing, HTTP requests, error handling

**Why both exist:** AWS toolkit is for setup automation; your custom client is for runtime. They complement each other.

### 6h) Authentication design summary for agent runtime

- There are **two separate hops** in the final runtime design:
  - **Hop 1: caller -> agent service**
    - Example callers: local `curl`, dashboard, backend API.
    - This hop may be open during local development or protected later by API auth.
  - **Hop 2: agent service -> AgentCore Gateway**
    - This hop uses Cognito bearer-token authentication.
- Gateway uses Cognito `customJWTAuthorizer` with:
  - `allowedClients` = service app client ID
  - `discoveryUrl` = user-pool OIDC discovery URL
- Agent runtime uses OAuth `client_credentials` to get bearer token from Cognito.
- Token request requires:
  - `COGNITO_APP_CLIENT_ID`
  - `COGNITO_APP_CLIENT_SECRET`
  - `COGNITO_TOKEN_ENDPOINT`
  - `COGNITO_SCOPE` (for example: `agentcore/invoke`)
- What triggers token fetch?
  - A request reaches the agent service.
  - The agent starts processing.
  - When it needs an MCP tool call, it checks token cache.
  - If token is valid, it reuses it.
  - If token is missing or expired, it fetches a new one from Cognito, stores expiry, then calls gateway.
- Agent sends `Authorization: Bearer <token>` to AgentCore Gateway (`tools/list`, `tools/call`).
- If token request fails, agent should stop tool call and return clear auth error.
- If gateway returns `401/403`, agent should refresh token once and retry once.
- Implement token cache + refresh before expiry in shared gateway client logic.
- Keep client secret in secret manager/env (never in git).

---

**How agent decides maintenance (hybrid approach with 3 outcomes):**

```
1. Agent reads sensor data
2. Check deterministic rules:
  IF temperature > 95°C → OUTCOME 1: Create URGENT work_order (critical issue)
  IF vibration = critical → OUTCOME 1: Create URGENT work_order (critical issue)
  IF all normal → OUTCOME 3: Monitor only (no action needed)
3. IF ambiguous case → OUTCOME 2: Call LLM for analysis
4. LLM analyzes patterns → recommends one of:
  a) schedule_maintenance (preventive/corrective + date)
  b) get_spare_parts (check inventory for needed parts)
  c) create_work_order (urgent repair)
5. Agent calls the appropriate tool based on LLM recommendation
6. Tool writes record to AWS (Lambda→DynamoDB or App Runner→logs)

Summary of 3 Outcomes:
- OUTCOME 1 (Urgent): create_work_order tool called
- OUTCOME 2 (Preventive): LLM decides → schedule_maintenance or get_spare_parts
- OUTCOME 3 (Routine): No tool call, continue monitoring
```

**Ready to proceed with Step 4a (create DynamoDB tables)?**
