# Phase 1 Architecture - Local Agents + Real AWS Services

**Goal:** Build agents locally that connect to real AWS services for testing and validation.

---

## System Overview

```
┌─────────────────────────────┐
│  YOUR MACHINE               │
│  ├─ Supervisor Agent        │
│  ├─ Health Agent            │
│  ├─ Router Agent            │
│  ├─ Diagnosis Agent         │
│  ├─ FastAPI (port 8000)     │
│  └─ React (port 3000)       │
└──────────────┬──────────────┘
               │ AWS SDK
               ▼
    ┌──────────────────────┐
    │  AWS SERVICES        │
    │  ├─ Cognito          │
    │  ├─ DynamoDB         │
    │  ├─ Lambda (MCP-1,2) │
    │  ├─ ECS (MCP-3,4)    │
    │  └─ AgentCore        │
    └──────────────────────┘
```

---

## Why This Architecture?

✅ **Fast iteration** - No Lambda cold starts on every code change  
✅ **Easy debugging** - Local stack traces, print statements work  
✅ **Real AWS integration** - Test with actual services from day 1  
✅ **Decoupled components** - Change agents without touching tools  
✅ **Production patterns** - Same design used in Phase 2  

---

## Component Details

### 1. Local Agents (Your Machine)

Four specialist agents running as Python processes:

**Supervisor Agent**
- Receives user request
- Routes to appropriate specialist(s)
- Orchestrates parallel execution
- Returns combined results

**Health Agent**
- Analyzes equipment metrics
- Calls MCP-1 via AgentCore Gateway (health rules)
- Returns health score + status

**Router Agent**
- Determines recommended actions
- Calls MCP-2 via AgentCore Gateway (device manual)
- Returns action recommendations

**Diagnosis Agent**
- Analyzes root causes
- Calls MCP-3 via AgentCore Gateway (diagnosis engine)
- Calls MCP-4 via AgentCore Gateway (external APIs)
- Returns diagnosis + repair steps

**Key:** All agents call tools through AgentCore Gateway, not directly.

### 2. Real AWS Services

**Cognito**
- User authentication (JWT tokens)
- Manages user sessions
- Same as production

**DynamoDB**
- Stores conversation history
- Session management
- Real database (not mock)

**AgentCore Gateway**
- Central orchestration for all tool calls
- Routes requests from agents to Lambda/ECS endpoints
- Manages tool discovery and registration
- Stores conversation memory in DynamoDB
- Validates Cognito tokens on all requests
- Implements retry logic for transient failures
- **Critical:** Agents never call Lambda/ECS directly; all tool access goes through Gateway

**Lambda (MCP-1, MCP-2)**
- MCP-1: Equipment health rules (~50ms)
- MCP-2: Device specifications (~100ms)
- Fast, stateless operations
- **Registered with AgentCore Gateway** (agents call through Gateway)

**ECS Fargate (MCP-3, MCP-4)**
- MCP-3: Diagnosis rules engine (~10-30s)
- MCP-4: External API queries (~5-60s)
- Complex, stateful operations
- MCP-3 includes optional Azure GPT-4o LLM integration
- **Registered with AgentCore Gateway** (agents call through Gateway)

### 3. Frontend & API

**FastAPI**
- REST API on port 8000
- Routes: /analyze, /results, /history
- JWT token validation
- Calls local agents directly

**React Dashboard**
- UI on port 3000
- Login, analysis form, results display
- Calls FastAPI endpoints

---

## Data Flow

### Request Flow
```
React Dashboard
    ↓ (POST /api/analyze)
FastAPI (port 8000)
    ↓ (Python IPC)
Supervisor Agent
    ├─ Load synthetic sensor data
    ├─ Route to Health Agent
    │   ├─ Process metrics
    │   ├─ Call AgentCore Gateway
    │   │   └─ Gateway routes to MCP-1 Lambda → health rules
    │   └─ Return health score
    ├─ Route to Router Agent
    │   ├─ Analyze metrics
    │   ├─ Call AgentCore Gateway
    │   │   └─ Gateway routes to MCP-2 Lambda → device specs
    │   └─ Return actions
    └─ Route to Diagnosis Agent
        ├─ Process symptoms
        ├─ Call AgentCore Gateway
        │   ├─ Gateway routes to MCP-3 ECS → diagnosis + optional LLM
        │   └─ Gateway routes to MCP-4 ECS → external APIs
        └─ Return diagnosis
    ↓
Results → AgentCore Gateway → DynamoDB (conversation memory)
    ↓ (return session_id)
FastAPI returns session_id
    ↓ (JSON)
React displays results
```

**Key Flow Points:**
- All agent tool calls go through AgentCore Gateway (no direct Lambda/ECS calls)
- Gateway handles tool discovery, routing, and retry logic
- DynamoDB accessed only through Gateway (for memory management)
- Cognito tokens validated by Gateway on every request

---

## Tool Registration with AgentCore

Before agents can call tools, they must be registered with AgentCore Gateway.

**Registration Process:**
```
Week 1-2 Setup:
1. Deploy Lambda functions (MCP-1, MCP-2)
   └─ Register endpoints with AgentCore Gateway
2. Deploy ECS services (MCP-3, MCP-4)
   └─ Register endpoints with AgentCore Gateway
3. Create AgentCore tool definitions (JSON metadata)
   ├─ Input schema (sensor metrics, symptoms, etc.)
   ├─ Output schema (health scores, diagnoses, etc.)
   └─ Timeout and retry policies
4. Agents can now discover and call registered tools
```

**Tool Definition Example:**
```json
{
  "tool_name": "mcp-1-health-rules",
  "type": "lambda",
  "endpoint": "arn:aws:lambda:us-east-1:123456789:function:mcp-1",
  "timeout": 5,
  "retries": 2,
  "input_schema": {
    "equipment_id": "string",
    "metrics": {"temp": "float", "vibration": "float"}
  },
  "output_schema": {
    "health_score": "float",
    "status": "string"
  }
}
```

**Agent Tool Discovery:**
```python
# Agents query AgentCore for available tools
gateway = AgentCoreGateway(cognito_token)
tools = gateway.discover_tools()  # Returns all registered tools

# Call tool through Gateway
result = gateway.call_tool(
    tool_name="mcp-1-health-rules",
    inputs={"equipment_id": "eq-001", "metrics": {...}},
    memory_id="session-123"  # For DynamoDB conversation tracking
)
```

---

## Tool Architecture

### Lambda Tier (Fast)
- **MCP-1 (Health Rules):** Query health thresholds from DynamoDB
- **MCP-2 (Device Manual):** Query device specs from DynamoDB

**Why Lambda:**
- Response time ~50-100ms
- Simple database queries
- No complex logic needed

### ECS Tier (Complex)
- **MCP-3 (Diagnosis Rules + LLM):** Rule-based diagnosis with optional LLM enhancement
- **MCP-4 (External APIs):** Query external knowledge bases

**Why ECS:**
- Response time ~5-60s (acceptable for complex ops)
- Custom business logic
- Long-running operations
- Support for LLM API calls (timeout-friendly)

#### MCP-3 LLM Integration

**Pattern:** Rule-based analysis → LLM enhancement (optional)

```
MCP-3 Execution Flow:
1. Apply rule-based diagnosis (fast)
2. Calculate confidence score
3. If confidence < 0.75 OR score is critical (>0.8):
   └─ Call GPT-4o (Azure) for deeper reasoning
4. Return combined diagnosis + LLM insights
```

**When LLM is called:**
- Rule confidence < 75% (uncertain rule match)
- Degradation score critical (>0.8) - need expert reasoning
- Multiple possible diagnoses - LLM picks best

**LLM Model:** GPT-4o (Azure Foundry)
- Fast response (~2-5s)
- Better reasoning than GPT-4
- Cost: ~$0.015 per call

**Configuration needed in `.env`:**
```
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
```

**Agents remain LLM-agnostic:**
- Diagnosis Agent calls MCP-3 tool
- MCP-3 handles LLM internally
- Agents don't know if LLM was used
- Can disable LLM in MCP-3 config (falls back to rules only)

---

## Security Model

**Authentication**
- Cognito JWT tokens
- Validated on every API call
- Tokens stored securely in React

**Authorization**
- Each agent can call specific tools only
- IAM roles with permission boundaries
- DynamoDB encrypted at rest

**Data Protection**
- HTTPS for all API calls
- DynamoDB encryption enabled
- Cognito handles password security

---

## Technology Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Agents | Python + LangGraph | Flexible, easy to debug |
| API | FastAPI | Modern, fast, auto-docs |
| Frontend | React 18+ | Industry standard, responsive UI |
| Auth | Cognito | Production-grade, no custom auth code |
| Memory | DynamoDB | Serverless, scalable, no management |
| Tools (Fast) | Lambda | Stateless, scales instantly |
| Tools (Complex) | ECS Fargate | Container-based, flexible |
| Gateway | AgentCore | Routes tools, manages state |
| IaC | Python/boto3 | Simple, readable, no new DSL |

---

## Deployment Model

**Phase 1 (Current):** Agents on laptop, tools in AWS  
**Phase 2 (Future):** Agents in Lambda/AgentCore, tools in AWS

Both use same agent code - only execution context changes.

---

## Scalability Notes

**Phase 1 Limits:**
- Single developer laptop
- ~10-20 concurrent requests (before connection limit)
- Good for development and testing

**Phase 2 Options:**
- Move agents to Lambda (auto-scales)
- Move to ECS (for stateful agents)
- Auto-scaling from 0-1000+ concurrent requests
- Cost: ~$100-300/month

---

## Cost Estimate (Phase 1)

| Service | Cost/Month |
|---------|-----------|
| Lambda (MCP-1, MCP-2) | ~$2-5 |
| ECS Fargate (MCP-3, MCP-4) | ~$15-30 |
| Azure OpenAI (GPT-4o, MCP-3) | ~$5-15 (if LLM enabled) |
| DynamoDB | ~$5-10 |
| Cognito | ~$5-10 |
| Data transfer | ~$1-2 |
| **Total** | **$35-80** |

**Note:** LLM costs depend on usage. ~10 diagnosis requests/day with LLM = ~$4/month.

---

## Key Design Decisions

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| Local agents | Fast iteration | Must run on laptop |
| Real AWS tools | Production-ready | AWS costs even in dev |
| Synthetic data | Realistic testing | Not real sensor data |
| DynamoDB for memory | Serverless, managed | Pays for storage |
| Cognito auth | Production-grade | Setup complexity |
| ECS Fargate | Flexible containers | More expensive than Lambda |
| No VPC/SG | Simplified networking | Less fine-grained control |

---

**Next:** Read [PHASE_1_IMPLEMENTATION.md](PHASE_1_IMPLEMENTATION.md) for step-by-step build instructions.
