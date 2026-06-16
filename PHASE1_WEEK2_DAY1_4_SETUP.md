# Phase 1 Week 2 Day 1-4: MCP Tools & AgentCore Identity

Deploy MCP tools (Lambda + ECS) to AWS with data in S3. Local agents continue reading from local files.

---

## Scope: Create MCP Tools (Lambda + ECS) on AWS + S3 Data Setup

**Key Point:** Week 2 Day 1-4 deploys MCP tools directly to AWS and uploads generated data to S3 for tool access.

- ✅ Generate device sensor data locally (`equipment_simulator`)
- ✅ Generate spare parts inventory locally (`inventory_data_generator`)
- ✅ Create S3 bucket for generated data
- ✅ Upload generated data to S3
- ✅ Define MCP tool schemas (standardized interfaces)
- ✅ Create Lambda functions that implement MCP tools (deployed to AWS)
- ✅ Create ECS containers that implement MCP tools (deployed to AWS)
- ✅ Configure Lambda/ECS to read data from S3
- ✅ Register tools with AWS AgentCore Gateway
- ✅ Set up Cognito & AgentCore Identity for agent authentication
- ✅ Configure AWS AgentCore Memory for agent memory persistence
- ✅ Test tool invocation through AgentCore endpoints
- ❌ NO local agents connected yet (they connect Week 2 Day 5-7)
- ❌ NO dashboard yet (comes Week 2 Day 5-7)

**Focus:** Deploy tools to AWS (Lambda/ECS) reading from S3. Local agents stay local reading from `data/generated/`. Both can coexist this week.

---

## Overview

**Goal:** Deploy MCP tools to AWS (Lambda/ECS) and upload generated data to S3 for tools to use. Keep local agents using local data.

**Phase 1 Architecture:**
```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Local Machine (Agents)                                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│ data/generated/                                                              │
│  ├─ device-*.json (sensor data for agents)                                   │
│  └─ spare_parts_inventory.json (reference data for agents)                   │
│                                                                              │
│ HealthAgent, DiagnosisAgent, EscalationAgent                                 │
│  └─ Read from LOCAL data/generated/                                          │
│  └─ Call MCP tools via AgentCore Gateway                                     │
└──────────────────────────────────────────────────────────────────────────────┘
                            ↓ (HTTPS)
┌──────────────────────────────────────────────────────────────────────────────┐
│ AWS (Tools & Data)                                                           │
├──────────────────────────────────────────────────────────────────────────────┤
│ S3 Bucket: agentic-ai-poc-3-1-data                                           │
│  ├─ data/device-*.json                                                       │
│  └─ data/spare_parts_inventory.json                                          │
│                                                                              │
│ AgentCore Gateway (managed service)                                          │
│  ├─ Tool Registry & Schema Validation                                        │
│  └─ Route to implementations                                                 │
│                                                                              │
│ Lambda Functions:                                                            │
│  ├─ schedule_maintenance (reads spare_parts from S3)                         │
│  ├─ get_spare_parts (reads from S3)                                          │
│  └─ [Phase 3: get_maintenance_history, get_device_alerts]                    │
│                                                                              │
│ ECS Container:                                                               │
│  └─ create_work_order                                                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

**What you'll build:**
- **S3 Setup**: Create bucket and upload generated data (Day 1)
- **MCP Tool Schemas**: Standardized JSON schemas for each tool
- **Lambda Functions**: Implement MCP tools (deployed to AWS, read from S3)
- **ECS Containers**: Implement MCP tools (deployed to AWS)
- **Tool Registration**: Register Lambda/ECS tools with AWS AgentCore Gateway
- **Cognito/AgentCore Identity**: For agent authentication and temporary credentials
- **AgentCore Memory**: Persistent memory for agent conversations and state
- **IAM Roles**: Service roles for Lambda/ECS with S3 permissions

**MCP Tools in Phase 1 (as Lambda or ECS):**
1. `get_spare_parts` - Lambda → reads S3 spare_parts_inventory.json from MCP tools bucket
2. `schedule_maintenance` - Lambda → executes scheduling
3. `create_work_order` - ECS → executes work order creation

**S3 Bucket Structure (Separate Buckets):**
```
MCP Tools Bucket: agentic-ai-poc-3-1-mcp-tools
  └─ mcp/
      └─ spare_parts_inventory.json (only MCP tools data here)

Sensor Data Bucket: agentic-ai-poc-3-1-sensor-data
  └─ devices/
      ├─ device-001.json through device-016.json
      ├─ motor-*.json
      ├─ pump-*.json
      ├─ compressor-*.json
      └─ generator-*.json
```

**Why Separate Buckets?**
- MCP tools bucket: For Lambda/ECS tool execution (read-only)
- Sensor data bucket: For agents when they move to Phase 2+ (read/write)
- Clear separation of concerns
- Different access patterns and policies

**Why MCP (Model Context Protocol)?**
- Standardized tool interface for AI agents
- Safety: Schema validation before execution
- Consistency: Same format across all tools
- Extensibility: Easy to add new tools later

---

## Prerequisites

✅ From Week 1:
- AWS infrastructure deployed (Cognito, DynamoDB)
- Equipment simulator and synthetic data
- Local agents working (HealthAgent, DiagnosisAgent)
- LangGraph workflow tested

✅ Also needed:
- AWS CLI configured
- IAM permissions to create Cognito Identity Pool and Lambda roles
- Understanding of MCP (Model Context Protocol)

---

## Architecture Decisions

**Why AWS AgentCore Gateway (Managed Service)?**
- AWS provides the gateway infrastructure
- Integrated with AgentCore Identity and Memory
- Handles tool routing, validation, and response formatting
- No need to build/maintain custom gateway code
- Scales automatically for production use

**Why MCP Tool Schemas?**
- Standardized interface for Lambda and ECS tools
- AgentCore uses schemas to validate tool inputs
- Agents understand tool capabilities through schemas
- JSON schema is industry standard

**Why Lambda for Some Tools?**
- Fast, stateless operations (read-only queries)
- Gets maintenance history, device alerts, spare parts
- Lower latency, easier to maintain
- Cost-efficient for frequent calls

**Why ECS for Other Tools?**
- Long-running operations (orchestration, integration)
- Schedule maintenance, create work orders
- Can maintain state, call external systems
- More flexibility for complex business logic

**Why Cognito & AgentCore Identity?**
- Agents need temporary AWS credentials (no hardcoded keys)
- AgentCore Identity manages credential lifecycle
- Credentials auto-rotate for security
- Cognito provides multi-factor auth option
- Trust relationship between local agents and AWS

**Why AgentCore Memory?**
- Agents need persistent conversation state
- Memory persists between agent runs
- Enables multi-turn interactions
- Integration with AgentCore Gateway for seamless access

**Why Tool Stubs First?**
- Test tool contracts with local mock data
- Verify JSON schemas are correct
- Gateway + tools work before adding Lambda
- Easy to swap real Lambda in Week 3

**Why MCP Format?**
- Aligns with Claude's native tool calling
- Industry standard (supported by LangGraph)
- Future-proof for other AI models
- Gateway handles JSON-RPC protocol

---

## Implementation Overview

**Files to Create:**

### Lambda Functions (Python in AWS)
1. `src/lambda_functions/get_maintenance_history.py` - MCP tool as Lambda
2. `src/lambda_functions/get_device_alerts.py` - MCP tool as Lambda
3. `src/lambda_functions/schedule_maintenance.py` - MCP tool as Lambda
4. `src/lambda_functions/get_spare_parts.py` - MCP tool as Lambda

### ECS Task Definitions (Docker containers)
1. `src/ecs_tasks/create_work_order/app.py` - MCP tool as ECS container
2. `src/ecs_tasks/create_work_order/Dockerfile` - Container definition
3. `src/ecs_tasks/create_work_order/requirements.txt` - Python dependencies

### Tool Schemas & Registration
1. `src/tools/schemas.py` - MCP tool schema definitions
2. `src/tools/tool_registry.py` - Register tools with AgentCore
3. `scripts/register_tools.py` - Script to register Lambda/ECS with AgentCore

### Agent Authentication (Local)
1. `src/identity/agentcore_credentials.py` - AgentCore Identity client
2. `src/identity/agent_config.py` - AgentCore endpoint configuration
3. `test_agentcore_connection.py` - Test agent can reach AgentCore

### Infrastructure (Terraform or CloudFormation)
1. `infra/lambda_iam_role.tf` - IAM role for Lambda functions
2. `infra/ecs_task_role.tf` - IAM role for ECS tasks
3. `infra/agentcore_memory_setup.tf` - AgentCore Memory configuration

**AWS Infrastructure Changes:**
- Create Lambda execution IAM role (for Lambda tools)
- Create ECS task execution IAM role (for ECS tools)
- Create service role for local agents (for AgentCore Identity)
- Set up AgentCore Memory namespace
- Configure tool registration in AgentCore

**Total New Code:** ~1,500 lines (Lambda + ECS + schemas + registration)

---

## Quick Start

### Step 1: Generate Data Locally

```bash
# Generate device sensor data (16 devices, 30 days each)
python -m src.data.equipment_simulator --output-dir data/generated

# Generate spare parts inventory (reference data)
python -m src.data.inventory_data_generator --output-dir data/generated

# Result: data/generated/ now has all JSON files
```

### Step 2: Upload Data to S3

```bash
# Create S3 bucket and upload all generated data
python scripts/setup_s3_for_mcp_tools.py \
  --bucket-name agentic-ai-poc-3-1-data \
  --data-dir data/generated \
  --region us-east-1 \
  --output-summary s3_setup_summary.txt

# This:
# - Creates S3 bucket (if not exists)
# - Uploads all JSON files to S3
# - Configures bucket policy
# - Outputs S3 URLs for tools to use
```

### Step 3: Define MCP Tool Schemas

```bash
# Define what each tool expects/returns
# Example: get_spare_parts tool
# Input: {issue_type}
# Output: {available, part_name, part_id, quantity_in_stock, ...}
# AgentCore uses these schemas for validation
```

### Step 4: Create Lambda Functions

```bash
# Implement MCP tools as Lambda functions (Python)
# Each Lambda gets:
#   - MCP tool schema
#   - S3 access via IAM role (to read spare_parts_inventory.json)
#   - Cognito credentials (passed by AgentCore)
#
# Example: get_spare_parts Lambda reads from S3
```

### Step 5: Create ECS Task Definition

```bash
# Implement MCP tools as ECS containers (Python + FastAPI)
# Each ECS task gets:
#   - MCP tool schema
#   - Docker container
#   - Service role with S3 permissions
#   - Environment variables from AgentCore
```

### Step 6: Register Tools with AWS AgentCore

```bash
# Register Lambda and ECS tools with AgentCore Gateway
# AgentCore learns:
#   - Tool names and schemas
#   - Lambda ARNs or ECS task definitions
#   - Required IAM permissions
#   - S3 bucket access for data
```

### Step 7: Configure Agent Authentication

```bash
# Set up AgentCore Identity for local agents
# Agents get:
#   - AgentCore endpoint URL
#   - Agent service credentials
#   - AgentCore Memory namespace
#   - Trust relationship with Lambda/ECS tools
```

### Step 8: Test Connection

```bash
# Test: Local agent can authenticate with AgentCore
# Test: Agent can invoke tools through AgentCore
# Test: Tools return proper MCP responses
# Test: Tools successfully read from S3
```

---

## Expected Output

**S3 Setup Summary:**
```
S3 Setup Summary
================

Bucket Name: agentic-ai-poc-3-1-data
Region: us-east-1
Files Uploaded: 18

Uploaded Files:
  - device-001.json
    Location: s3://agentic-ai-poc-3-1-data/data/device-001.json
  - ...
  - spare_parts_inventory.json
    Location: s3://agentic-ai-poc-3-1-data/data/spare_parts_inventory.json

Configuration:
  ✅ Versioning: Enabled
  ✅ Data Prefix: data/
  ✅ Access: Lambda/ECS services can read

MCP Tools Can Now:
  - Read spare_parts_inventory.json from S3 (for get_spare_parts tool)
  - Read device data from S3 (if needed)

Local Agents Still Read From:
  - data/generated/*.json (local machine)
```

**Tool Registry (registered with AgentCore):**
```json
{
  "tools": [
    {
      "name": "get_spare_parts",
      "description": "Check spare parts availability for issue type",
      "type": "lambda",
      "arn": "arn:aws:lambda:us-east-1:123456789:function:mcp-get-spare-parts",
      "input_schema": {...},
      "output_schema": {...},
      "s3_data_source": "s3://agentic-ai-poc-3-1-data/data/spare_parts_inventory.json"
    },
    {
      "name": "schedule_maintenance",
      "description": "Schedule maintenance task",
      "type": "lambda",
      "arn": "arn:aws:lambda:us-east-1:123456789:function:mcp-schedule-maintenance",
      "input_schema": {...},
      "output_schema": {...}
    },
    {
      "name": "create_work_order",
      "description": "Create a maintenance work order",
      "type": "ecs",
      "task_definition": "arn:aws:ecs:us-east-1:123456789:task-definition/mcp-create-work-order:1",
      "input_schema": {...},
      "output_schema": {...}
    }
  ]
}
```

**Agent Credentials (from AgentCore Identity):**
```json
{
  "agentcore_endpoint": "https://agent.agentcore-gateway.us-east-1.amazonaws.com",
  "agent_id": "agent-phase3-1-local",
  "credentials": {
    "access_key": "ASIA...",
    "secret_key": "...",
    "session_token": "...",
    "expiration": "2026-05-27T18:00:00Z"
  },
  "memory_namespace": "agentic-ai-poc-3-1"
}
```

**Test Results:**
- ✅ All tool schemas validate
- ✅ Lambda functions deployed successfully
- ✅ ECS task definitions registered
- ✅ Tools registered with AgentCore Gateway
- ✅ Agent can authenticate with AgentCore Identity
- ✅ Agent can invoke tools through AgentCore
- ✅ Tool responses formatted correctly (MCP JSON-RPC)
- ✅ AgentCore Memory namespace created and accessible
- ✅ All tests pass with Exit Code: 0

---

## Troubleshooting

**Cognito Identity Pool not created?**
```bash
# Check that Week 1 setup completed
python scripts/main_setup.py verify

# If missing, Cognito Identity Pool section will be added
```

**Agent role permissions denied?**
```bash
# Verify role has inline policy for DynamoDB/Lambda
# Check trust relationship with Cognito Identity Pool
# Test with simpler permissions first (e.g., read-only DynamoDB)
```

**Tool schema validation fails?**
```bash
# Check JSON schema syntax
# Verify required fields match implementation
# Test with valid sample data
```

**Credentials expired?**
```bash
# Cognito Identity credentials auto-expire (1 hour default)
# Mechanism should auto-refresh
# Check token refresh logic in agent_credentials.py
```

---

## Key Concepts

**MCP (Model Context Protocol):**
- JSON-RPC based protocol for tool calls
- Tool call structure: `{jsonrpc: "2.0", method: "tool_name", params: {...}}`
- Response structure: `{jsonrpc: "2.0", result: {...}}`
- Standardized schema validation

**AWS AgentCore Gateway (Managed Service):**
- AWS-provided service for agent tool routing
- Handles MCP tool invocation
- Manages credentials and permissions
- Integrated with AgentCore Identity and Memory
- Agents call: `https://agent.agentcore-gateway.region.amazonaws.com`

**Lambda as MCP Tools:**
- Stateless, event-driven functions
- Fast execution (< 1 second typical)
- Best for: read operations, queries
- Example: `get_maintenance_history` (queries DynamoDB)

**ECS Containers as MCP Tools:**
- Containerized applications
- Can maintain state
- Longer execution times allowed
- Best for: orchestration, external system integration
- Example: `create_work_order` (calls external work order system)

**AgentCore Identity (for Agents):**
- Provides temporary credentials to agents
- Agent authenticates once at startup
- Gets: access key, secret key, session token
- Credentials auto-refresh
- Scoped to agent's allowed operations

**AgentCore Memory (for Agent State):**
- Persistent memory service for agents
- Stores conversation history
- Stores agent decision state
- Shared across agent invocations
- Integrated with AgentCore Gateway

**Tool Permissions (IAM):**
- Each Lambda/ECS has execution role
- Role defines what resources tool can access
- Example: DynamoDB read-only for `get_maintenance_history`
- Example: DynamoDB write + Lambda invoke for `schedule_maintenance`
- AgentCore enforces these permissions

**Credential Lifecycle:**
1. Local agent starts → requests credentials from AgentCore Identity
2. AgentCore Identity verifies → returns temporary AWS credentials
3. Agent calls tool through AgentCore Gateway with credentials
4. AgentCore routes to Lambda or ECS
5. Lambda/ECS uses credentials to access AWS services (DynamoDB, etc.)
6. Response returned through AgentCore Gateway to agent
7. Credentials expire → auto-refresh on next agent call

---

## Next: Week 2 Day 5-7

After tools are registered with AgentCore:
1. **Week 2 Day 5-7:** Connect local agents to AWS AgentCore
2. Update agents to use AgentCore credentials
3. Agents call tools through AgentCore Gateway endpoints
4. Build Flask dashboard UI (also calls AgentCore endpoints)
5. End-to-end integration test (local agents → AgentCore → Lambda/ECS)

**Note:** Tools are DEPLOYED and REGISTERED in Day 1-4. In Day 5-7, local agents just connect to them.

---

## Success Criteria

✅ Generated data created locally (equipment_simulator + inventory_data_generator)  
✅ S3 bucket created successfully  
✅ All JSON files uploaded to S3 (18 files total)  
✅ S3 bucket policy configured for Lambda/ECS access  
✅ S3 setup summary verified  
✅ All tool schemas defined and validated  
✅ Lambda functions created and deployed (3 functions: get_spare_parts, schedule_maintenance, ...)  
✅ ECS task definition created and deployed (1 service: create_work_order)  
✅ Lambda/ECS tools configured with S3 IAM permissions  
✅ All tools registered with AWS AgentCore Gateway  
✅ AgentCore Identity configured for agent authentication  
✅ AgentCore Memory namespace created  
✅ Agent can obtain credentials from AgentCore Identity  
✅ Agent can invoke tool through AgentCore Gateway (test only)  
✅ Tool responses formatted correctly (MCP JSON-RPC)  
✅ Tools can successfully read from S3  
✅ All tests pass with Exit Code: 0  
✅ Tools ready for agents to connect (Week 2 Day 5-7)
