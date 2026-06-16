# Phase 1 Implementation - Week-by-Week Roadmap

**Duration:** 1-2 weeks  
**Goal:** Complete working system with all components integrated

---

## How to Use This Document

1. **Find your current week**
2. **Read the task description** to understand what you're building
3. **Ask for code generation:** "Generate code for [Week X] Day [Y-Z]: [Task Name]"
4. **Integrate the code** into your project
5. **Run tests** to verify
6. **Move to next task**

Each week builds one complete feature end-to-end.

---

## Week 1: Setup + Local Agents + AWS Connections

### Day 1-2: Project Setup + AWS Resources

**Build:**
- Directory structure: `src/`, `tests/`, `scripts/`, `dashboard/`, `data/`
- Python virtual environment + requirements.txt
- AWS Cognito User Pool
- DynamoDB table for memory/history
- IAM roles for agents
- `.env` configuration

**Why:**
- Cognito needed for authentication (used in all requests)
- DynamoDB needed for conversation storage
- IAM roles needed before agents can call tools
- Structure determines code organization

**Deliverables:**
- ✅ Project structure ready
- ✅ Virtual environment created
- ✅ Cognito User Pool deployed
- ✅ DynamoDB table created
- ✅ IAM roles created
- ✅ `.env` with AWS credentials

**Next Ask:** "Generate code for Week 1 Day 1-2: Project initialization with AWS resources"

---

### Day 3-4: Synthetic Sensor Data Generator

**Build:**
- `src/data/equipment_simulator.py` - Generate realistic sensor readings
- Pre-generated test data in `data/generated/`
- Test data covers 30 days per equipment
- Includes vibration, temperature, pressure readings

**Why:**
- Agents need realistic data to analyze
- Synthetic data allows testing without IoT devices
- 30 days provides degradation patterns for testing
- Used by all agents in their analysis

**Deliverables:**
- ✅ `EquipmentSimulator` class
- ✅ Pre-generated JSON files (PUMP, MOTOR, COMPRESSOR, GENERATOR)
- ✅ Test data loading functions
- ✅ Unit tests for data generation

**Next Ask:** "Generate code for Week 1 Day 3-4: Equipment simulator and synthetic data generation"

---

### Day 5-7: Local Agents + AgentCore Connection

**Build:**
- `src/core/agentcore_gateway.py` - AWS SDK wrapper for tool discovery and calling
- `src/agents/supervisor.py` - Main orchestrator
- `src/agents/health.py` - Health analysis agent
- `src/agents/router.py` - Action recommendation agent
- `src/agents/diagnosis.py` - Root cause analysis agent
- Unit tests for each agent

**Why:**
- AgentCore gateway is mandatory for all tool access
- Supervisor routes requests to specialists
- Each agent focuses on one analysis type
- Local execution allows debugging
- Agents NEVER call Lambda/ECS directly

**Agent Responsibilities:**
- **Supervisor:** Load sensor data → decide which agents to call → orchestrate execution
- **Health:** Analyze metrics → call AgentCore Gateway → return health score
- **Router:** Suggest actions → assess risk → call AgentCore Gateway → return recommendations
- **Diagnosis:** Find root causes → call AgentCore Gateway → return repairs needed

**Critical:** At this stage, tools aren't deployed yet. Agents will be built to:
1. Connect to AgentCore Gateway
2. Call gateway.discover_tools() (will be empty until Week 2)
3. Prepare for tool calls (will work after tools registered)

**Deliverables:**
- ✅ All agents implemented and tested locally
- ✅ AgentCore gateway connection verified
- ✅ Agent code structure ready for tool calls (to be enabled after Week 2 Day 13)
- ✅ DynamoDB integration for memory
- ✅ Integration tests passing

**Next Ask:** "Generate code for Week 1 Day 5-7: Agents + AgentCore gateway"

---

## Week 2: Deploy MCP Tools + FastAPI Backend

### Day 8-10: Deploy Lambda Tools (MCP-1, MCP-2)

**Build:**
- `src/tools/mcp1_health_rules.py` - Health thresholds lookup
- `src/tools/mcp2_device_manual.py` - Device specifications
- `scripts/deploy_lambda_mcp1.py` - Deploy to AWS
- `scripts/deploy_lambda_mcp2.py` - Deploy to AWS
- CloudWatch logging
- IAM execution roles

**Why:**
- Health Agent needs equipment thresholds (MCP-1)
- Router Agent needs device specifications (MCP-2)
- Lambda for fast operations (~50-100ms)
- Deployed before agents, agents call them

**Tool Functionality:**
- **MCP-1:** Returns health thresholds (temp max, vibration max, pressure max)
- **MCP-2:** Returns device specs (model, maintenance schedule, safe operating range)

**Deliverables:**
- ✅ MCP-1 Lambda deployed and callable
- ✅ MCP-2 Lambda deployed and callable
- ✅ CloudWatch logs verified
- ✅ IAM roles with permission boundaries
- ✅ Local test calls to Lambda working

**Next Ask:** "Generate code for Week 2 Day 8-10: Deploy MCP-1 and MCP-2 Lambda functions"

---

### Day 11-12: Deploy ECS Tools (MCP-3, MCP-4)

**Build:**
- `src/tools/mcp3_diagnosis_engine.py` - Diagnosis rules + LLM integration
- `src/tools/mcp4_external_api.py` - Knowledge base queries
- Docker containers for both
- `scripts/deploy_ecs_mcp3.py` - Deploy MCP-3
- `scripts/deploy_ecs_mcp4.py` - Deploy MCP-4
- Load balancer for HTTP access
- Azure OpenAI configuration

**Why:**
- Diagnosis Agent needs complex processing (MCP-3)
- Diagnosis Agent needs external knowledge (MCP-4)
- ECS for longer operations (5-60s)
- Containers allow custom logic + LLM integration
- LLM used internally by MCP-3 (transparent to agents)

**Tool Functionality:**
- **MCP-3:** Rule engine + optional LLM (Rule-based first, LLM if confidence low)
- **MCP-4:** External APIs (takes query → returns recommendations)

**LLM Integration (MCP-3):**
- Model: GPT-4o (Azure)
- Called only if: rule confidence < 75% OR score critical
- Configuration: Add to `.env` before deployment
- Optional: Can disable via config (falls back to rules only)

**Deliverables:**
- ✅ MCP-3 ECS container deployed
- ✅ MCP-4 ECS container deployed
- ✅ HTTP endpoints accessible
- ✅ Azure OpenAI configured (if using LLM)
- ✅ Local test calls working
- ✅ Docker logs verified

**Next Ask:** "Generate code for Week 2 Day 11-12: Deploy MCP-3 and MCP-4 ECS containers with LLM integration"

---

### Day 13: Register Tools with AgentCore Gateway

**CRITICAL STEP:** Before agents can call tools, they must be registered with AgentCore.

**Build:**
- `scripts/register_tools_with_agentcore.py` - Registration script
- Tool metadata JSON files (input/output schemas, timeouts)
- Verification tests

**Why:**
- AgentCore Gateway needs to know about deployed tools
- Agents discover available tools from Gateway
- Schema validation happens at Gateway (not in agents)
- Gateway manages retry logic and timeouts per tool

**Registration includes:**
- Lambda endpoints (MCP-1, MCP-2) → Gateway
- ECS endpoints (MCP-3, MCP-4) → Gateway
- Input/output schemas for each tool
- Timeout policies (Lambda: 5s, ECS: 60s)
- Retry counts (Lambda: 3, ECS: 2)

**Tool Schema Example (MCP-1):**
```json
{
  "tool_name": "mcp-1-health-rules",
  "type": "lambda",
  "endpoint": "arn:aws:lambda:us-east-1:ACCOUNT:function:mcp-1",
  "timeout_seconds": 5,
  "max_retries": 3,
  "input_schema": {
    "equipment_id": "string",
    "current_metrics": {"temperature": "float", "vibration": "float"}
  },
  "output_schema": {
    "health_score": "float (0-1)",
    "status": "string (healthy|degraded|critical)"
  }
}
```

**Deliverables:**
- ✅ All 4 tools registered with AgentCore Gateway
- ✅ Agents can discover tools via gateway.discover_tools()
- ✅ Agent calls route through Gateway
- ✅ Test verification of registration

**Next Ask:** "Generate code for Week 2 Day 13: Register tools with AgentCore Gateway"

---

### Day 13-14: FastAPI Backend

**Build:**
- `src/api/main.py` - FastAPI application
- Routes: `/analyze`, `/results/{session_id}`, `/history`
- Cognito JWT validation middleware
- Calls to local agents
- CORS for React frontend
- Error handling and logging

**Why:**
- REST API interface for React
- JWT validation on every request
- FastAPI auto-generates `/docs` for testing
- Middleware handles cross-cutting concerns

**Endpoints:**
- **POST /analyze** - Submit analysis request (calls Supervisor Agent)
- **GET /results/{session_id}** - Retrieve results from DynamoDB
- **GET /history** - Get user's analysis history
- **GET /docs** - Auto-generated Swagger UI

**Deliverables:**
- ✅ FastAPI running on port 8000
- ✅ All endpoints working
- ✅ JWT validation working
- ✅ `/docs` endpoint accessible
- ✅ Integration tests passing

**Next Ask:** "Generate code for Week 2 Day 13-14: FastAPI backend with all endpoints"

---

## Week 3: React Dashboard + E2E Testing

### Day 15-18: React Dashboard

**Build:**
- `dashboard/src/App.jsx` - Main routing component
- `dashboard/src/pages/LoginPage.jsx` - Cognito login
- `dashboard/src/pages/AnalysisPage.jsx` - Equipment form + submit
- `dashboard/src/pages/ResultsPage.jsx` - Display analysis results
- `dashboard/src/pages/HistoryPage.jsx` - Past analyses
- `dashboard/src/api/client.js` - API communication

**Why:**
- React provides responsive UI
- Cognito integration for secure login
- API client abstracts FastAPI calls
- Pages separated by concern

**Pages:**
- **Login:** Authenticate with Cognito
- **Analysis:** Form to input equipment data, submit request
- **Results:** Display analysis results (health, actions, diagnosis)
- **History:** List past analyses with timestamps

**Deliverables:**
- ✅ React running on port 3000
- ✅ Login working with Cognito
- ✅ Analysis form submitting to API
- ✅ Results displaying correctly
- ✅ History page showing past analyses
- ✅ Navigation working between pages

**Next Ask:** "Generate code for Week 3 Day 15-18: React dashboard with all pages"

---

### Day 19-21: E2E Testing + Verification

**Build:**
- End-to-end test scenarios
- Verify complete flow: React → API → Agents → Tools → Results
- Performance benchmarks
- Documentation of test cases

**Test Scenarios:**
1. Login → Analysis → Results
2. Multiple requests in sequence
3. Error handling (invalid equipment ID)
4. History retrieval
5. Tool timeout handling
6. Concurrent requests

**Deliverables:**
- ✅ E2E tests passing
- ✅ Performance metrics documented
- ✅ Error scenarios handled
- ✅ Ready for Phase 2 transition

**Next Ask:** "Generate code for Week 3 Day 19-21: E2E tests and verification"

---

## Quick Command Reference

### Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure AWS
aws configure
```

### Deployment
```bash
# Deploy Lambda tools
python scripts/deploy_lambda_mcp1.py
python scripts/deploy_lambda_mcp2.py

# Deploy ECS tools
python scripts/deploy_ecs_mcp3.py
python scripts/deploy_ecs_mcp4.py

# Setup AWS resources
python scripts/setup_cognito_dynamodb.py
```

### Running Locally
```bash
# Terminal 1: Start FastAPI
python -m src.api.main
# Server on http://localhost:8000/docs

# Terminal 2: Start React
cd dashboard && npm start
# Dashboard on http://localhost:3000

# Terminal 3: Run tests
python -m pytest tests/ -v
```

---

## Success Criteria

✅ All agents implemented and tested  
✅ Lambda tools deployed and callable  
✅ ECS tools deployed and callable  
✅ FastAPI running with all endpoints  
✅ React dashboard functional  
✅ E2E flow verified (React → API → Agents → Tools → Results)  
✅ Cognito authentication working  
✅ DynamoDB storing conversation history  
✅ All tests passing  

---

## Common Issues & Fixes

**"Lambda not found"**
- Verify deployment: `aws lambda list-functions`
- Check IAM role permissions
- Check CloudWatch logs

**"DynamoDB access denied"**
- Verify IAM role has DynamoDB permissions
- Check table name in `.env`

**"Cognito token invalid"**
- Verify User Pool ID in `.env`
- Check token hasn't expired
- Clear browser cache

**"Agents not responding"**
- Check local ports (8000, 8001-8004)
- Verify AWS credentials configured
- Check CloudWatch logs for errors

---

**Next:** Move to Phase 2 when Week 3 complete and E2E tests passing.
