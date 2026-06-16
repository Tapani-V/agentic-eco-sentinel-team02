# Phase 1 Week 2 Day 1-4: Implementation Reference

Complete implementation details for S3 setup, MCP tools, and AgentCore Identity configuration.

**See [PHASE1_WEEK2_DAY1_4_SETUP.md](PHASE1_WEEK2_DAY1_4_SETUP.md) for architecture and concepts.**

---

## Phase 1 Architecture

**Week 2 Day 1-4 does:**
1. Generate data locally (inventory_data_generator → spare_parts_inventory.json)
2. Upload MCP tools data to S3 (via setup_s3_for_mcp_tools.py → agentic-ai-poc-3-1-mcp-tools bucket)
3. Deploy Lambda/ECS tools to AWS (tools read spare_parts_inventory.json from MCP tools bucket)
4. Register tools with AgentCore Gateway
5. Configure agent authentication

**Result:**
- Local agents read from `data/generated/` locally (STAYS LOCAL in Phase 1)
- Lambda/ECS tools read spare_parts_inventory.json from `s3://agentic-ai-poc-3-1-mcp-tools/mcp/`
- Sensor data stays local in Phase 1, will be uploaded to sensor bucket in Phase 2
- Both agents and tools are ready for Week 2 Day 5-7 integration

**S3 Buckets (Separate Concerns):**
- **MCP Tools Bucket:** `agentic-ai-poc-3-1-mcp-tools` (Phase 1) → Contains spare_parts_inventory.json
- **Sensor Data Bucket:** `agentic-ai-poc-3-1-sensor-data` (Phase 2+) → Will contain device-*.json files

---

## S3 Setup Script: `scripts/setup_s3_for_mcp_tools.py`

**Purpose:** Automatically create MCP tools S3 bucket and upload spare parts data ONLY.

**Usage (MCP Tools Bucket - Phase 1):**
```bash
python scripts/setup_s3_for_mcp_tools.py \
  --bucket-name agentic-ai-poc-3-1-mcp-tools \
  --data-dir data/generated \
  --file-filter spare_parts_inventory.json \
  --region us-east-1 \
  --output-summary s3_mcp_setup_summary.txt
```

**What it does:**
1. Creates S3 bucket: `agentic-ai-poc-3-1-mcp-tools`
2. Enables versioning on bucket
3. Uploads ONLY `spare_parts_inventory.json` to `s3://agentic-ai-poc-3-1-mcp-tools/mcp/`
4. Sets content type to `application/json`
5. Adds metadata tags
6. Configures bucket policy for Lambda/ECS access
7. Outputs summary with S3 URLs

**Output Example:**
```
✅ Bucket created successfully: agentic-ai-poc-3-1-mcp-tools
✅ Versioning enabled for: agentic-ai-poc-3-1-mcp-tools
Found 1 JSON file to upload (filter: spare_parts_inventory.json)
Uploading: spare_parts_inventory.json → s3://agentic-ai-poc-3-1-mcp-tools/mcp/spare_parts_inventory.json
✅ Uploaded: spare_parts_inventory.json
✅ All 1 files uploaded successfully
✅ Bucket policy configured
```

**Sensor Data (Phase 2+):**
- Device sensor files (device-*.json, motor-*.json, etc.) stay LOCAL in Phase 1
- Will be uploaded to separate bucket in Phase 2: `agentic-ai-poc-3-1-sensor-data`
- Format: `s3://agentic-ai-poc-3-1-sensor-data/devices/{device_id}.json`

---

## File Structure

```
scripts/
├── setup_s3_for_mcp_tools.py    (350 lines) - S3 bucket + data upload script
│
src/
├── tools/
│   ├── __init__.py              (15 lines) - Package initialization
│   ├── schemas.py               (280 lines) - MCP tool schema definitions
│   ├── tool_registry.py         (120 lines) - Tool registry (owns tools)
│   └── implementations.py       (450 lines) - Tool implementations (stubs)
├── api/
│   ├── __init__.py              (12 lines) - Package initialization
│   └── gateway.py               (350 lines) - AgentCore Gateway (FastAPI)
└── identity/
    ├── __init__.py              (12 lines) - Package initialization
    ├── cognito_identity.py      (150 lines) - Identity Pool setup
    └── agent_credentials.py     (200 lines) - Credential mechanism

test_tools.py                    (180 lines) - Unit tests for tools
test_gateway.py                  (200 lines) - Gateway endpoint tests
test_agent_credentials.py        (140 lines) - Credential flow tests
test_gateway_integration.py      (250 lines) - End-to-end gateway tests

.env.template                    (updated) - New environment variables
```

**Total Production Code:** ~1,929 lines (includes S3 setup script)  
**Total Test Code:** 770 lines

---

## Implementation Steps

### Step 1: Generate Data Locally

**Run equipment simulator:**
```bash
python -m src.data.equipment_simulator --output-dir data/generated
```

**Output:** 16 device JSON files (device-001.json through generator-003.json)

**Run inventory generator:**
```bash
python -m src.data.inventory_data_generator --output-dir data/generated
```

**Output:** spare_parts_inventory.json with 8 part types

**Result:** `data/generated/` has 18 JSON files

### Step 2: Create S3 Bucket and Upload MCP Tools Data

**Run S3 setup script (MCP Tools Bucket Only):**
```bash
python scripts/setup_s3_for_mcp_tools.py \
  --bucket-name agentic-ai-poc-3-1-mcp-tools \
  --data-dir data/generated \
  --file-filter spare_parts_inventory.json \
  --region us-east-1 \
  --output-summary s3_mcp_setup_summary.txt
```

**Script does:**
1. Creates S3 bucket: `agentic-ai-poc-3-1-mcp-tools`
2. Enables versioning
3. Uploads ONLY `spare_parts_inventory.json` to `s3://agentic-ai-poc-3-1-mcp-tools/mcp/`
4. Configures bucket policy for Lambda/ECS access
5. Saves summary to `s3_mcp_setup_summary.txt`

**Result:**
- MCP tools bucket created and configured
- Spare parts inventory in S3 for Lambda/ECS to read
- Summary file with S3 URLs for reference
- Sensor data files remain local (Phase 1)

### Step 3: Define MCP Tool Schemas

File: `src/tools/schemas.py`

Defines 3 Phase 1 tools:

1. **get_spare_parts** (Lambda)
   - Input: `{issue_type: str}`
   - Output: `{available: bool, part_name: str, part_id: str, quantity_in_stock: int, ...}`
   - Data Source: `s3://agentic-ai-poc-3-1-mcp-tools/mcp/spare_parts_inventory.json`

2. **schedule_maintenance** (Lambda)
   - Input: `{device_id: str, maintenance_type: str, priority: str, ...}`
   - Output: `{id: str, device_id: str, scheduled_date: str, status: str}`
   - Data Source: Reads spare_parts from MCP tools bucket if needed

3. **create_work_order** (ECS)
   - Input: `{device_id: str, issue_type: str, priority: str, description: str}`
   - Output: `{id: str, device_id: str, status: str, assigned_date: str}`
   - Data Source: None (creates new records)

### Step 4-8: Deploy Tools & Register with AgentCore

These steps follow the PHASE1_WEEK2_DAY1_4_SETUP.md document.

---

## Key Files to Create/Update

### 1. `scripts/setup_s3_for_mcp_tools.py` - S3 SETUP (NEW)

**650+ lines** of production-ready Python code.

**Key Class:** `S3DataManager`

Methods:
- `bucket_exists()` - Check if S3 bucket exists
- `create_bucket()` - Create S3 bucket with versioning
- `upload_data_files(data_dir)` - Upload all JSON files from directory to S3
- `configure_bucket_policy()` - Set IAM policy for Lambda/ECS access
- `generate_summary(uploaded_files)` - Generate human-readable summary

**Features:**
- Auto-creates bucket if needed
- Handles multi-region support
- Batch uploads JSON files
- Sets metadata on objects
- Configures bucket policy for service access
- Generates verification summary
- Comprehensive error handling
- Verbose logging option

### 2. `src/tools/schemas.py` - MCP TOOL SCHEMAS

**280+ lines** defining 3 Phase 1 tools:

1. `get_spare_parts` - Check spare parts availability
2. `schedule_maintenance` - Schedule maintenance task
3. `create_work_order` - Create maintenance work order

Each schema includes:
- Tool name and description
- Input JSON schema (what parameters tool accepts)
- Output JSON schema (what tool returns)
- Example request/response
- Data source information

### 3. Lambda Implementation Code

**Lambda for `get_spare_parts` Tool**

```python
import json
import boto3

s3_client = boto3.client('s3')

def lambda_handler(event, context):
    issue_type = event.get('issue_type')
    
    # Read spare parts inventory from MCP tools bucket
    response = s3_client.get_object(
        Bucket='agentic-ai-poc-3-1-mcp-tools',
        Key='mcp/spare_parts_inventory.json'
    )
    inventory = json.loads(response['Body'].read())
    
    # Look up part for issue type
    if issue_type in inventory:
        part_info = inventory[issue_type]
        return {
            'statusCode': 200,
            'body': json.dumps(part_info)
        }
    else:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': f'No part found for {issue_type}'})
        }
```

**Lambda for `schedule_maintenance` Tool**

```python
import json
import boto3
from datetime import datetime, timedelta

def lambda_handler(event, context):
    device_id = event.get('device_id')
    maintenance_type = event.get('maintenance_type')
    
    # Implement scheduling logic
    scheduled_date = (datetime.now() + timedelta(days=2)).isoformat()
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'id': f'MAINT-{device_id}-{datetime.now().timestamp()}',
            'device_id': device_id,
            'maintenance_type': maintenance_type,
            'scheduled_date': scheduled_date,
            'status': 'scheduled'
        })
    }
```

### 4. ECS Task Implementation

**ECS for `create_work_order` Tool**

FastAPI-based container:

```python
from fastapi import FastAPI
from datetime import datetime
import json

app = FastAPI()

@app.post('/create_work_order')
async def create_work_order(request: dict):
    device_id = request.get('device_id')
    issue_type = request.get('issue_type')
    priority = request.get('priority', 'medium')
    
    # Create work order
    work_order_id = f'WO-{device_id}-{datetime.now().timestamp()}'
    
    return {
        'id': work_order_id,
        'device_id': device_id,
        'issue_type': issue_type,
        'priority': priority,
        'status': 'created',
        'assigned_date': datetime.now().isoformat()
    }
```

---

## IAM Configuration for Lambda/ECS

### Lambda Execution Role Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::agentic-ai-poc-3-1-mcp-tools",
        "arn:aws:s3:::agentic-ai-poc-3-1-mcp-tools/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

### ECS Task Execution Role Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:BatchCheckLayerAvailability"
      ],
      "Resource": "arn:aws:ecr:*:*:repository/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

---

## Environment Variables (`.env`)

```
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012

# S3 Configuration (MCP Tools Bucket - Phase 1)
S3_MCP_TOOLS_BUCKET=agentic-ai-poc-3-1-mcp-tools
S3_MCP_TOOLS_PREFIX=mcp/

# S3 Configuration (Sensor Data Bucket - Phase 2+)
S3_SENSOR_DATA_BUCKET=agentic-ai-poc-3-1-sensor-data
S3_SENSOR_DATA_PREFIX=devices/

# AgentCore Configuration
AGENTCORE_ENDPOINT=https://agent.agentcore-gateway.us-east-1.amazonaws.com
AGENTCORE_MEMORY_NAMESPACE=agentic-ai-poc-3-1

# Tool Configuration
MCP_TOOL_TIMEOUT=30
MCP_TOOL_RETRY_COUNT=3

# Logging
LOG_LEVEL=INFO
```

---

## Testing Strategy

### Test 1: S3 Setup Verification

```bash
# Verify S3 bucket creation and uploads
python -m pytest test_s3_setup.py -v

# Check:
# - Bucket created
# - All 18 files uploaded
# - File count matches
# - File sizes correct
# - Metadata present
```

### Test 2: Tool Schema Validation

```bash
# Verify MCP tool schemas are valid
python -m pytest test_tools_schemas.py -v

# Check:
# - All schemas valid JSON
# - Input/output schemas present
# - Required fields defined
# - Example requests/responses valid
```

### Test 3: Lambda Function Testing

```bash
# Test Lambda functions locally
python -m pytest test_lambda_functions.py -v

# Check:
# - Lambda can read from S3
# - get_spare_parts returns correct data
# - schedule_maintenance generates IDs correctly
# - Error handling works
```

### Test 4: ECS Container Testing

```bash
# Build and test ECS container locally
docker build -t mcp-create-work-order src/ecs_tasks/create_work_order/
docker run -p 8000:8000 mcp-create-work-order
curl -X POST http://localhost:8000/create_work_order \
  -d '{"device_id": "DEV001", "issue_type": "motor_failure"}'

# Check:
# - Container builds without errors
# - Endpoint responds correctly
# - Work orders created with proper IDs
```

### Test 5: AgentCore Registration Test

```bash
# Verify tools registered with AgentCore
python -m pytest test_agentcore_registration.py -v

# Check:
# - All 3 tools registered
# - Schemas uploaded correctly
# - Tools accessible via AgentCore endpoint
```

---

## Summary: What's Deployed in Phase 1 Week 2 Day 1-4

| Component | Location | Status | Notes |
|-----------|----------|--------|-------|
| Spare Parts Inventory | `data/generated/spare_parts_inventory.json` locally | ✅ Local | Used by MCP tools |
| Device Sensor Data | `data/generated/device-*.json` locally | ✅ Local | Used by agents (stays local Phase 1) |
| Spare Parts Inventory | S3 `agentic-ai-poc-3-1-mcp-tools/mcp/` | ✅ AWS (Phase 1) | MCP tools read from here |
| Device Sensor Data | S3 `agentic-ai-poc-3-1-sensor-data/devices/` | ⏸️ Phase 2+ | Agents will read from here later |
| get_spare_parts | Lambda in AWS | ✅ AWS | Reads from MCP tools bucket |
| schedule_maintenance | Lambda in AWS | ✅ AWS | Executes scheduling |
| create_work_order | ECS in AWS | ✅ AWS | Creates records |
| Tool Schemas | AgentCore Registry | ✅ AWS | All 3 registered |
| Cognito Identity | AWS | ✅ AWS | For agent auth |
| AgentCore Memory | AWS | ✅ AWS | For agent state |
| Local Agents | Local machine | ⏸️ Ready | Connected in Day 5-7 |

---

## Next Steps (Week 2 Day 5-7)

1. Agents connect to AgentCore Gateway
2. Agents authenticate with AgentCore Identity
3. Agents call tools via AgentCore
4. Dashboard built to visualize results
5. End-to-end integration testing

See [PHASE1_WEEK2_DAY5_7_SETUP.md](PHASE1_WEEK2_DAY5_7_SETUP.md) for Day 5-7 details.

    "input": {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "..."},
            "param2": {"type": "integer", "description": "..."}
        },
        "required": ["param1"]
    },
    "output": {
        "type": "object",
        "properties": {
            "result": {"type": "array", "description": "..."}
        }
    }
}
```

**Key Line Range:** 1-280

---

### 3. `src/tools/tool_registry.py` (120 lines)

**Purpose:** Central registry mapping tool names to implementations.

**Contains:**
- `ToolRegistry` class with singleton pattern
- Tool registration mechanism
- Tool lookup by name
- Validation of tool calls against schemas

**Key Methods:**
1. `register_tool(name, schema, implementation)` - Add tool
2. `get_tool(name)` - Retrieve tool by name
3. `list_tools()` - Get all registered tools
4. `validate_call(tool_name, params)` - Validate input before execution
5. `execute_tool(tool_name, params)` - Call tool (validates + executes)

**Registry Pattern:**
```python
class ToolRegistry:
    _instance = None
    _tools = {}
    
    @staticmethod
    def instance():
        if ToolRegistry._instance is None:
            ToolRegistry._instance = ToolRegistry()
        return ToolRegistry._instance
    
    def register_tool(self, name, schema, implementation):
        # Store tool definition
        self._tools[name] = {
            'schema': schema,
            'implementation': implementation
        }
    
    def validate_call(self, tool_name, params):
        # Validate params against schema
        # Raise exception if invalid
        pass
    
    def execute_tool(self, tool_name, params):
        # Validate, then execute
        self.validate_call(tool_name, params)
        impl = self._tools[tool_name]['implementation']
        return impl(params)
```

**Key Line Range:** 1-120

---

### 4. `src/tools/implementations.py` (450 lines)

**Purpose:** Implement each MCP tool - read data from JSON files locally (Week 2 POC).

**Contains:**
- 5 tool implementation functions
- JSON file reading and filtering
- Data transformation/formatting
- Error handling
- Logging

**Data Source Architecture:**

```
Week 2 (POC - Local):
  Tool → Read from data/generated/{device_id}.json
         (17 device files, 720 readings each)

Week 3+ (Production - Cloud):
  Tool → Read from S3: s3://bucket/devices/{device_id}.json
         (same code, different file path)
         
Interface stays the same, only data location changes
```

**Key Functions:**

1. **get_maintenance_history(params)**
   - Read device JSON file
   - Filter by date range (start_date, end_date)
   - Extract relevant fields
   - Return formatted records
   - Week 3: Change file path from local to S3

2. **get_device_alerts(params)**
   - Read device JSON file
   - Extract sensor readings with anomalies
   - Filter by severity if provided
   - Return alert list

3. **schedule_maintenance(params)**
   - Read maintenance history file
   - Generate task_id
   - Append to history
   - Return confirmation
   - Week 3: Write to S3 instead of local

4. **get_spare_parts(params)**
   - Read inventory JSON (or generate mock)
   - Filter by equipment_type and part_type
   - Return availability + lead times

5. **create_work_order(params)**
   - Generate work_order_id
   - Create work order record
   - Store in local file or S3
   - Return confirmation

**Tool Implementation Pattern (Week 2 - JSON Files):**

```python
import json
from pathlib import Path

def get_maintenance_history(params):
    """
    Fetch maintenance records from JSON file
    
    Args:
        params: {
            'device_id': 'pump-001',
            'start_date': '2026-05-01',
            'end_date': '2026-05-26'
        }
    
    Returns:
        {
            'records': [
                {'date': '2026-05-15', 'action': '...', 'status': '...'},
                ...
            ]
        }
    """
    try:
        device_id = params.get('device_id')
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        
        if not device_id:
            raise ValueError("device_id required")
        
        # Week 2: Read from local JSON file
        json_file = Path(f'data/generated/{device_id}.json')
        if not json_file.exists():
            return {'records': [], 'error': f"Device {device_id} not found"}
        
        # Load all readings
        with open(json_file) as f:
            readings = json.load(f)
        
        # Filter by date range
        records = []
        for reading in readings:
            reading_date = reading.get('timestamp', '')[:10]  # YYYY-MM-DD
            if start_date <= reading_date <= end_date:
                # Extract maintenance-relevant fields
                records.append({
                    'date': reading_date,
                    'action': f"Reading recorded - Degradation: {reading.get('degradation_score')}",
                    'status': 'recorded'
                })
        
        return {
            'status': 'success',
            'records': records,
            'error': None
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'records': [],
            'error': str(e)
        }

def get_device_alerts(params):
    """Fetch alerts by reading sensor anomalies from JSON"""
    try:
        device_id = params.get('device_id')
        severity = params.get('severity', 'all')  # all, warning, critical
        
        # Read JSON file
        json_file = Path(f'data/generated/{device_id}.json')
        with open(json_file) as f:
            readings = json.load(f)
        
        # Extract anomalies (sensors outside normal range)
        alerts = []
        latest_reading = readings[-1] if readings else {}
        
        for sensor_name, sensor_data in latest_reading.get('readings', {}).items():
            value = sensor_data.get('value', 0)
            normal_range = sensor_data.get('normal_range', [0, 100])
            
            if value < normal_range[0] or value > normal_range[1]:
                # Determine severity
                deviation = max(
                    abs(value - normal_range[0]),
                    abs(value - normal_range[1])
                ) / max(normal_range)
                
                alert_severity = 'critical' if deviation > 0.3 else 'warning'
                
                if severity == 'all' or severity == alert_severity:
                    alerts.append({
                        'timestamp': latest_reading.get('timestamp', ''),
                        'sensor': sensor_name,
                        'value': value,
                        'threshold': normal_range,
                        'severity': alert_severity
                    })
        
        return {
            'status': 'success',
            'alerts': alerts,
            'error': None
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'alerts': [],
            'error': str(e)
        }
```

**Week 3+ Pattern (S3 Version - Reference Only):**

```python
# Week 3: Same function, reads from S3 instead
import boto3

def get_maintenance_history_s3(params):
    """Same interface, reads from S3 in cloud"""
    try:
        device_id = params.get('device_id')
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        
        # Download from S3 instead of local file
        s3 = boto3.client('s3')
        obj = s3.get_object(
            Bucket='agentic-ai-poc-3-1-data',
            Key=f'devices/{device_id}.json'
        )
        
        # Same filtering logic as local version
        readings = json.loads(obj['Body'].read())
        records = [...]
        
        return {'status': 'success', 'records': records, 'error': None}
    
    except Exception as e:
        return {'status': 'error', 'records': [], 'error': str(e)}
```

**Error Handling Pattern:**
```python
try:
    # Validation
    if not device_id:
        raise ValueError("device_id required")
    
    # File I/O
    with open(json_file) as f:
        data = json.load(f)
    
    # Processing
    results = process_data(data)
    
    # Return success
    return {
        'status': 'success',
        'data': results,
        'error': None
    }

except FileNotFoundError:
    return {'status': 'error', 'data': None, 'error': 'Device not found'}
except Exception as e:
    return {'status': 'error', 'data': None, 'error': str(e)}
```

**Key Line Range:** 1-450

---

### 5. `src/api/gateway.py` (350 lines)

**Purpose:** AgentCore Gateway - central hub for tool invocation.

**Contains:**
- `Gateway` class (FastAPI application)
- HTTP endpoints for tool invocation
- Tool registry integration
- Credential passing
- Request/response handling

**Key Endpoints:**

1. **POST /tools/invoke** - Main tool invocation endpoint
   - Input: `{tool_name: str, params: dict}`
   - Output: `{status: str, result: dict, error: str}`
   - Validates input, executes tool, returns response
   - Handles credential passing to tool

2. **GET /tools/list** - List all available tools
   - Returns: `{tools: [{name, description, input_schema, output_schema}]}`
   - Agents use to discover available tools

3. **GET /tools/{tool_name}/schema** - Get tool schema
   - Returns tool's input/output schema
   - For client-side validation

4. **GET /health** - Health check
   - Returns: `{status: "healthy", tools_registered: int}`
   - For orchestration/monitoring

**Gateway Implementation Pattern:**
```python
from fastapi import FastAPI, HTTPException
from src.tools.tool_registry import ToolRegistry

app = FastAPI()
tool_registry = ToolRegistry.instance()

@app.post("/tools/invoke")
async def invoke_tool(request: ToolInvocationRequest):
    """
    Agent calls this to invoke a tool
    Gateway handles schema validation and execution
    """
    try:
        # 1. Get tool from registry
        tool = tool_registry.get_tool(request.tool_name)
        
        # 2. Validate input
        tool_registry.validate_call(request.tool_name, request.params)
        
        # 3. Execute tool (with credentials)
        result = tool_registry.execute_tool(
            request.tool_name,
            request.params,
            credentials=request.credentials  # If provided
        )
        
        # 4. Return response
        return {
            "status": "success",
            "result": result,
            "error": None
        }
    
    except Exception as e:
        return {
            "status": "error",
            "result": None,
            "error": str(e)
        }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "tools_registered": len(tool_registry.list_tools())
    }
```

**Security Features:**
- Input schema validation before execution
- Error handling (doesn't expose internal errors)
- Credential passing (agents provide credentials)
- Logging of all tool invocations
- Rate limiting ready (can add later)

**Key Line Range:** 1-350

---

### 6. `src/identity/cognito_identity.py` (150 lines)

**Purpose:** Set up and configure Cognito Identity Pool for agent credentials.

**Contains:**
- Cognito Identity Pool creation (if not exists)
- IAM role creation for agents
- Trust relationship setup
- Credential issuing mechanism

**Key Methods:**

1. `create_identity_pool(pool_name)` - Create or get pool
   - Input: Pool name from .env
   - Output: Pool ID
   - Idempotent (no error if exists)

2. `create_agent_role(role_name)` - Create agent service role
   - Input: Role name
   - Output: Role ARN
   - Attaches inline policy for tool permissions

3. `set_trust_relationship(identity_pool_id, role_arn)` - Trust setup
   - Allows Cognito Identity Pool to assume role
   - Enables credential issuance

4. `get_identity_config()` - Get pool configuration
   - Returns: Pool ID, role ARN, client ID
   - Used by agent_credentials.py

**Configuration Structure:**
```python
{
    'identity_pool_id': 'us-east-1:12345...',
    'agent_role_arn': 'arn:aws:iam::123456789012:role/agentic-ai-poc-3-1-agent-role',
    'client_id': '...',
    'region': 'us-east-1'
}
```

**Agent Role Policy (inline):**
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:Query",
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem"
            ],
            "Resource": "arn:aws:dynamodb:us-east-1:*:table/agentic-ai-poc-3-1-*"
        },
        {
            "Effect": "Allow",
            "Action": ["lambda:InvokeFunction"],
            "Resource": "arn:aws:lambda:us-east-1:*:function/agentic-ai-poc-3-1-*"
        }
    ]
}
```

**Key Line Range:** 1-150

---

### 6. `src/identity/cognito_identity.py` (150 lines)

**Purpose:** Mechanism for agents to obtain and refresh AWS credentials.

**Contains:**
- `AgentCredentialManager` class
- Credential request from Identity Pool
- Credential caching/refresh logic
- Credential lifecycle management

**Key Methods:**

1. `get_credentials()` - Get current credentials (auto-refresh if expired)
   - Check if cached credentials valid
   - If expired, request new ones
   - Return credentials

2. `request_credentials(identity_pool_id, role_arn)` - Get from Cognito
   - Call Cognito Identity Pool
   - Parse response
   - Return: AccessKeyId, SecretKey, SessionToken

3. `is_expired(expiration_time)` - Check credential validity
   - Compare expiration with current time
   - Add 5-minute buffer for safety

4. `configure_aws_session(credentials)` - Set up Boto3 session
   - Pass credentials to Boto3
   - Create session for agent use

**Credential Lifecycle Diagram:**
```
Agent starts
    ↓
Agent calls: agent.get_credentials()
    ↓
AgentCredentialManager checks cache
    ├─ Valid? → Return cached credentials
    └─ Expired? → Request new credentials from Cognito
        ↓
    Cognito Identity Pool
        ├─ Validates request
        └─ Issues temporary credentials (1 hour)
    ↓
Credentials cached locally
    ↓
Agent uses credentials for tool calls
    ↓
Credentials expire → Auto-refresh on next call
```

**Credential Format (from Cognito):**
```python
{
    'AccessKeyId': 'ASIA...',
    'SecretKey': 'wJal...',
    'SessionToken': 'IQoDYXdzE...',
    'Expiration': 1748282400  # Unix timestamp
}
```

**Key Line Range:** 1-200

---

## Test Files

### 7. `src/identity/agent_credentials.py` (200 lines)

**Purpose:** Unit tests for tool schemas and implementations.

**Tests:**

1. **Schema Validation Tests**
   - Verify each tool has valid JSON schema
   - Test with sample valid inputs
   - Test rejection of invalid inputs

2. **Tool Implementation Tests**
   - Mock data retrieval
   - Verify output format matches schema
   - Test error conditions

3. **Tool Registry Tests**
   - Register tool
   - Retrieve tool
   - List all tools
   - Validate tool calls

**Example Test:**
```python
def test_get_maintenance_history_valid_input():
    params = {
        'device_id': 'pump-001',
        'start_date': '2026-05-01',
        'end_date': '2026-05-26'
    }
    result = implementations.get_maintenance_history(params)
    
    assert 'records' in result
    assert isinstance(result['records'], list)
    # Verify schema compliance
```

**Run:**
```bash
python test_tools.py
```

**Expected:** ✅ All tests pass

**Key Line Range:** 1-180

---

### 8. `test_tools.py` (180 lines)

**Purpose:** Test credential flow from Identity Pool.

**Tests:**

1. **Identity Pool Setup**
   - Verify pool created
   - Verify agent role created
   - Verify trust relationship

2. **Credential Request**
   - Request credentials from Cognito
   - Verify format correct
   - Verify fields present

3. **Credential Refresh**
   - Cache credentials
   - Verify cache hit
   - Simulate expiration
   - Verify auto-refresh

4. **AWS Session Configuration**
   - Create Boto3 session with credentials
   - Verify session valid
   - Test STS GetCallerIdentity (verify credentials work)

**Example Test:**
```python
def test_get_credentials():
    manager = AgentCredentialManager()
    creds = manager.get_credentials()
    
    assert 'AccessKeyId' in creds
    assert 'SecretKey' in creds
    assert 'SessionToken' in creds
    
    # Verify credentials are valid
    sts = boto3.client('sts', 
        aws_access_key_id=creds['AccessKeyId'],
        aws_secret_access_key=creds['SecretKey'],
        aws_session_token=creds['SessionToken']
    )
    identity = sts.get_caller_identity()
    assert identity['Account']  # Should be valid
```

**Run:**
```bash
python test_agent_credentials.py
```

**Expected:** ✅ All tests pass

**Key Line Range:** 1-140

---

### 9. `test_gateway.py` (200 lines)

**Purpose:** Test gateway HTTP endpoints and tool invocation.

**Tests:**

1. **Gateway Startup Tests**
   - Verify gateway starts on localhost:8000
   - Verify /health endpoint returns healthy
   - Verify tool registry loaded

2. **Tool Invocation Tests**
   - HTTP POST to /tools/invoke
   - Valid inputs accepted
   - Invalid inputs rejected with validation error
   - Tool results returned correctly
   - Error responses formatted

3. **Schema Endpoint Tests**
   - GET /tools/list returns all tools
   - GET /tools/{tool_name}/schema returns schema

**Example Test:**
```python
def test_invoke_tool_http():
    response = client.post("/tools/invoke", json={
        "tool_name": "get_maintenance_history",
        "params": {
            "device_id": "pump-001",
            "start_date": "2026-05-01",
            "end_date": "2026-05-26"
        }
    })
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "records" in response.json()["result"]
```

**Run:**
```bash
python test_gateway.py
```

**Expected:** ✅ All tests pass

**Key Line Range:** 1-200

---

### 10. `test_agent_credentials.py` (140 lines)

**Purpose:** End-to-end test - agent calls MCP tools with credentials.

**Tests:**

1. **Agent Initialization**
   - Agent obtains credentials
   - Agent loads tool registry

2. **Tool Invocation**
   - Agent calls get_maintenance_history
   - Tool validates input against schema
   - Tool returns result
   - Agent processes result

3. **Error Handling**
   - Invalid tool name → error
   - Invalid parameters → schema validation error
   - Tool execution error → handled gracefully

4. **Full Workflow**
   - Agent starts health analysis
   - Calls get_device_alerts tool
   - Calls get_maintenance_history tool
   - Processes results
   - Generates recommendation

**Example Test:**
```python
def test_agent_calls_tool_with_credentials():
    # Setup
    agent = HealthAgent()  # Gets credentials in __init__
    registry = ToolRegistry.instance()
    
    # Agent calls tool
    result = registry.execute_tool('get_maintenance_history', {
        'device_id': 'pump-001',
        'start_date': '2026-05-01',
        'end_date': '2026-05-26'
    })
    
    # Verify result
    assert result['status'] == 'success'
    assert len(result['records']) > 0
```

**Run:**
```bash
python test_mcp_integration.py
```

**Expected:** ✅ All tests pass

**Key Line Range:** 1-200

---

### 11. `test_gateway_integration.py` (250 lines)

**Purpose:** End-to-end test - HTTP calls to gateway, tool invocation via gateway endpoints.

**Tests:**

1. **Gateway Startup & Ready**
   - Gateway starts successfully on localhost:8000
   - All tools registered in gateway
   - All endpoints ready
   - Health check passes

2. **Tool Invocation via HTTP**
   - Agent sends HTTP POST to /tools/invoke
   - Gateway validates input against schema
   - Gateway executes tool (stub)
   - Gateway returns response in MCP format
   - Agent receives and processes result

3. **Multiple Tools via Gateway**
   - Call get_maintenance_history through gateway
   - Call get_device_alerts through gateway
   - Call schedule_maintenance through gateway
   - Verify all work correctly

4. **Error Handling**
   - Invalid tool name → gateway returns error
   - Invalid parameters → schema validation error
   - Tool execution error → error response (doesn't crash gateway)
   - Missing required fields → validation error

**Example Test:**
```python
def test_agent_calls_gateway_tool():
    # Gateway running on localhost:8000
    
    # Agent (or test) makes HTTP call
    response = requests.post(
        "http://localhost:8000/tools/invoke",
        json={
            "tool_name": "get_maintenance_history",
            "params": {
                "device_id": "pump-001",
                "start_date": "2026-05-01",
                "end_date": "2026-05-26"
            }
        }
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "records" in data["result"]
```

**Run:**
```bash
python test_gateway_integration.py
```

**Expected:** ✅ Gateway working, tools callable, agents ready to connect

**Key Line Range:** 1-250

---

## Environment Variables

**New variables to add to `.env`:**

```ini
# Cognito Identity Pool (NEW - Week 2)
COGNITO_IDENTITY_POOL_NAME=agentic-ai-poc-3-1-identity-pool
COGNITO_AGENT_ROLE_NAME=agentic-ai-poc-3-1-agent-role

# Agent Credentials (NEW - Week 2)
AGENT_CREDENTIALS_CACHE_TTL=3600  # seconds
AGENT_CREDENTIALS_REFRESH_BUFFER=300  # 5 min before expiry

# MCP Tools (NEW - Week 2)
MCP_TOOLS_ENABLED=true
MCP_TOOL_TIMEOUT=30  # seconds per tool call

# AgentCore Gateway (NEW - Week 2)
GATEWAY_HOST=localhost
GATEWAY_PORT=8000
GATEWAY_LOG_LEVEL=info
```

---

## Data Structures

**Tool Call (MCP JSON-RPC):**
```json
{
    "jsonrpc": "2.0",
    "method": "get_maintenance_history",
    "params": {
        "device_id": "pump-001",
        "start_date": "2026-05-01",
        "end_date": "2026-05-26"
    },
    "id": "unique-call-id"
}
```

**Tool Response:**
```json
{
    "jsonrpc": "2.0",
    "result": {
        "records": [
            {
                "date": "2026-05-15",
                "action": "Oil change",
                "status": "completed"
            }
        ]
    },
    "id": "unique-call-id"
}
```

**Error Response:**
```json
{
    "jsonrpc": "2.0",
    "error": {
        "code": -32600,
        "message": "Invalid Request"
    },
    "id": "unique-call-id"
}
```

---

## Data Storage & Migration Strategy

### Week 2 (POC - Local Development)

**Data Location:**
```
/home/skroy/AGENTIC_AI_POC_Phase3_1/data/generated/
├── pump-001.json         (720 readings)
├── pump-002.json
├── motor-001.json
├── ... (17 device files total)
```

**How Tools Access Data:**
```python
# Tools read directly from local JSON files
file_path = Path(f'data/generated/{device_id}.json')
with open(file_path) as f:
    readings = json.load(f)
```

**Pros:**
- ✅ Simple (no cloud setup)
- ✅ Fast (local filesystem)
- ✅ Easy to debug
- ✅ No AWS costs
- ✅ Perfect for POC testing

**Cons:**
- ❌ Only works locally
- ❌ Can't scale beyond local machine
- ❌ Single point of failure

---

### Week 3+ (Production - Cloud Deployment)

**Data Migration to S3:**

**Step 1: Create S3 bucket**
```bash
aws s3api create-bucket \
  --bucket agentic-ai-poc-3-1-data \
  --region us-east-1
```

**Step 2: Upload JSON files**
```bash
aws s3 cp data/generated/ \
  s3://agentic-ai-poc-3-1-data/devices/ \
  --recursive
```

**Step 3: Update tool implementations (same interface, different path)**
```python
# Instead of reading local file:
# file_path = Path(f'data/generated/{device_id}.json')

# Read from S3:
s3 = boto3.client('s3')
obj = s3.get_object(
    Bucket='agentic-ai-poc-3-1-data',
    Key=f'devices/{device_id}.json'
)
readings = json.loads(obj['Body'].read())

# Rest of logic stays the same!
```

**Data Location (Cloud):**
```
S3: s3://agentic-ai-poc-3-1-data/devices/
├── pump-001.json
├── pump-002.json
├── ... (same 17 files)

Access from: Agents running in AWS (Lambda, ECS, etc.)
```

**Pros (S3):**
- ✅ Scalable (unlimited storage)
- ✅ Globally accessible
- ✅ No database complexity
- ✅ Cheap (< $0.01/month for this use case)
- ✅ Direct JSON file access
- ✅ Easy migration from local

**Cons (S3):**
- ❌ Slightly slower than local (network latency)
- ❌ Can't do complex queries (must read whole file)
- ❌ Minimal but not zero cost

---

### Why NOT DynamoDB for This POC?

**DynamoDB Considerations:**

| Factor | DynamoDB | S3 |
|--------|----------|-----|
| Complexity | High (schema, tables, imports) | Low (upload files) |
| Setup Time | 2-3 hours | 15 minutes |
| Learning Curve | Medium | None (just S3) |
| Cost | $1-5/month minimum | < $0.01/month |
| Query Speed | Fast indexed queries | Download entire file |
| Best For | Complex filtering | Simple file retrieval |
| For This POC? | Overkill | Perfect |

**DynamoDB would require:**
- Design table schema
- Parse 12,240 items (17 × 720)
- Set up batch import
- Test queries
- Extra IAM permissions

**S3 just needs:**
- Create bucket (1 command)
- Upload files (1 command)
- Update file path in code (3 lines)

**Decision:** Use S3 for Week 3+. Keep DynamoDB as future optimization if needed.

---

### Cost Comparison (Month)

**Week 2 (Local JSON):**
- Storage: $0
- Compute: $0
- Total: **$0**

**Week 3+ (S3):**
- Storage: ~200 KB = **$0.005**
- Downloads: ~1000/month = **$0.01**
- Total: **~$0.02/month**

**Why NOT DynamoDB (alternative):**
- Storage: 12,240 items = **$0.50**
- Read units: 1000 reads/month = **$0.25**
- Total: **~$0.75/month** (35x more expensive!)

---

## Data Format Reference

**JSON File Structure (data/generated/{device_id}.json):**
```json
[
  {
    "timestamp": "2026-01-01T00:00:00Z",
    "device_id": "pump-001",
    "equipment_type": "PUMP",
    "degradation_score": 0.023,
    "readings": {
      "flow": {
        "value": 95.2,
        "unit": "L/min",
        "normal_range": [80, 120]
      },
      "pressure": {
        "value": 2.1,
        "unit": "bar",
        "normal_range": [1.8, 2.5]
      },
      "temperature": {
        "value": 42.1,
        "unit": "C",
        "normal_range": [30, 50]
      },
      "vibration": {
        "value": 2.3,
        "unit": "mm/s",
        "normal_range": [1.0, 5.0]
      },
      "suction_pressure": {
        "value": 1.05,
        "unit": "bar",
        "normal_range": [0.9, 1.1]
      }
    }
  },
  ... (719 more readings for this device)
]
```

**Tools filter and extract from this structure.**

---

```
┌─ Agent Starts ─┐
│               │
├─ Calls: AgentCredentialManager.get_credentials()
│
├─ Manager checks cache
│  ├─ Valid + not expired? → Return cached
│  └─ Expired or missing? → Request new
│
├─ Call to Cognito Identity Pool
│  ├─ Endpoint: cognito-identity.us-east-1.amazonaws.com/GetCredentialsForIdentity
│  ├─ Params: identity_pool_id, agent_role_arn
│  └─ Returns: {AccessKeyId, SecretKey, SessionToken, Expiration}
│
├─ Cache credentials locally
│
├─ Configure Boto3 session with credentials
│
├─ Agent uses credentials for all tool calls
│
└─ Credentials expire (default 1 hour)
   └─ Auto-refresh on next credential request
```

---

## Tool Implementation Pattern

**Each tool follows same pattern:**

```python
def tool_name(params):
    """
    Description of what tool does
    
    Args:
        params (dict): {
            'param1': 'value1',
            'param2': 'value2'
        }
    
    Returns:
        dict: {
            'status': 'success' or 'error',
            'data': {...},
            'error_message': '' or 'error text'
        }
    """
    try:
        # 1. Validate inputs
        if 'device_id' not in params:
            raise ValueError("device_id required")
        
        # 2. Call AWS service (or mock data)
        result = query_dynamodb(params)
        
        # 3. Format response
        return {
            'status': 'success',
            'data': result,
            'error_message': ''
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'data': None,
            'error_message': str(e)
        }
```

---

## Code Statistics

| Component | Lines | Purpose |
|-----------|-------|---------|
| schemas.py | 280 | Tool definitions |
| tool_registry.py | 120 | Tool registry (owns tools) |
| implementations.py | 450 | Tool implementations |
| gateway.py | 350 | HTTP gateway server |
| cognito_identity.py | 150 | Identity Pool setup |
| agent_credentials.py | 200 | Credential mechanism |
| Package inits | 39 | Module setup |
| **Production Total** | **1,589** | Gateway + Tools + Identity |
| **Tests Total** | **770** | Unit + gateway + integration |
| **Grand Total** | **2,359** | All code |

---

## Integration with Agents

**How agents will use gateway in Week 2 Day 5-7:**

```python
# In agent's execute() method:

class HealthAgent(BaseAgent):
    def __init__(self):
        super().__init__("HealthAgent", "health_analysis")
        self.gateway_url = "http://localhost:8000"  # Gateway endpoint
        self.creds = AgentCredentialManager().get_credentials()
    
    async def execute(self, input_data):
        # ... analyze device health ...
        
        # Call tool THROUGH GATEWAY
        maintenance_history = await self._call_gateway_tool(
            'get_maintenance_history',
            {
                'device_id': device_id,
                'start_date': '2026-05-01',
                'end_date': '2026-05-26'
            }
        )
        
        # Use result in analysis
        if maintenance_history['status'] == 'success':
            records = maintenance_history['result']['records']
            # ... incorporate into diagnosis ...
        
        return {...}
    
    async def _call_gateway_tool(self, tool_name, params):
        """Call tool through gateway HTTP endpoint"""
        response = requests.post(
            f"{self.gateway_url}/tools/invoke",
            json={
                "tool_name": tool_name,
                "params": params,
                "credentials": self.creds  # Pass credentials
            }
        )
        return response.json()
```

**Data Flow (Week 2 → Week 3+):**

```
Week 2 (POC - Local):
  Agent
    ↓ HTTP POST to gateway
  Gateway
    ↓ Route to tool
  Tool reads: data/generated/{device_id}.json (local file)
    ↓
  Tool returns data to agent

Week 3+ (Production - Cloud):
  Agent (AWS)
    ↓ HTTP POST to gateway (AWS)
  Gateway (AWS)
    ↓ Route to tool
  Tool reads: s3://agentic-ai-poc-3-1-data/devices/{device_id}.json (S3)
    ↓
  Tool returns data to agent

CODE STAYS THE SAME!
Only the file path changes in tool implementation
```

**Key Difference:**
- Agents always call gateway endpoints (same everywhere)
- Gateway routes to tools (same everywhere)
- Tools read data (local vs S3 - only implementation changes)
- No changes needed to agent code for cloud migration

---

## Next Steps

**After Week 2 Day 1-4 (when all tests pass):**

1. **Week 2 Day 5-7:** Integrate with AgentCore Gateway
   - Create FastAPI endpoints
   - Connect agents to gateway
   - Add agent credentials to requests
   - Tools read from `data/generated/*.json` locally

2. **Week 3: Cloud Migration (Optional)**
   - Create S3 bucket: `agentic-ai-poc-3-1-data`
   - Upload JSON files: `s3://bucket/devices/{device_id}.json`
   - Update tool implementations to read from S3 instead of local files
   - **KEY:** Function signatures don't change, only data source!
   - Deploy gateway to AWS
   - Test with S3 data

3. **Dashboard Layer (Later):**
   - Create Flask dashboard
   - API endpoints for agent results
   - Real-time updates

---

## Common Issues & Solutions

**Issue: Cognito Identity Pool not found**
```bash
# Verify pool was created in Week 1 setup
python scripts/main_setup.py verify

# If missing, create manually or update setup script
```

**Issue: Agent role has no permissions**
```bash
# Check inline policy attached to role
# Verify resource ARNs match DynamoDB/Lambda resources
# Test permissions with AWS CLI first
```

**Issue: Credentials not refreshing**
```bash
# Check token expiration time
# Verify AGENT_CREDENTIALS_REFRESH_BUFFER is reasonable
# Check Cognito Identity Pool configuration
```

**Issue: Tool schema validation fails**
```bash
# Verify JSON schema syntax is valid
# Check parameter names match implementation
# Test with sample data before running tests
```

---

## References

**MCP Specification:** https://modelcontextprotocol.io/
**Cognito Identity:** https://docs.aws.amazon.com/cognitoidentity/
**JSONSchema:** https://json-schema.org/
**Boto3 STS:** https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sts.html
