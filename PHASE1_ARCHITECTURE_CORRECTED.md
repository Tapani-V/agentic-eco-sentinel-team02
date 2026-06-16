# Phase 1 Architecture: Corrected Model

**Updated:** May 27, 2026

This document clarifies the **actual Phase 1 architecture** that has been implemented for Week 2.

---

## Key Clarification: Where Data Lives vs Where Tools Run

### ❌ Wrong Model (What We Avoided)
```
Local agents → Local MCP tools → Local data files → Then migrate to AWS
```
**Problem:** Extra work rebuilding tools for AWS later

### ✅ Correct Model (Phase 1)
```
Local agents → AWS MCP tools → S3 data
                (Lambda/ECS)    (uploaded now)
```
**Advantage:** Deploy tools once to AWS, agents stay local, data already in S3

---

## Phase 1 Week 2 Architecture

### Local Machine
```
data/generated/
  ├─ device-001.json through device-016.json (agent reads these)
  ├─ motor-*.json
  ├─ pump-*.json
  ├─ compressor-*.json
  ├─ generator-*.json
  └─ spare_parts_inventory.json (agent reads this too)

HealthAgent, DiagnosisAgent, EscalationAgent
  ├─ Read device data from: data/generated/*.json
  ├─ Read spare parts from: data/generated/spare_parts_inventory.json
  └─ Call MCP tools via HTTPS to: https://agent.agentcore-gateway.us-east-1.amazonaws.com
```

### AWS (Tools & Data)
```
S3 Bucket: agentic-ai-poc-3-1-data
  └─ data/
      ├─ device-001.json through device-016.json
      ├─ motor-*.json
      ├─ pump-*.json
      ├─ compressor-*.json
      ├─ generator-*.json
      └─ spare_parts_inventory.json

Lambda Functions:
  ├─ mcp-get-spare-parts
  │   └─ Reads: s3://agentic-ai-poc-3-1-data/data/spare_parts_inventory.json
  └─ mcp-schedule-maintenance
      └─ Reads: s3://agentic-ai-poc-3-1-data/data/ (if needed)

ECS Container:
  └─ mcp-create-work-order

AgentCore Gateway:
  ├─ Routes tool calls from local agents to Lambda/ECS
  ├─ Handles authentication
  └─ Returns results back to agents

AgentCore Identity:
  └─ Provides temporary credentials for agents

AgentCore Memory:
  └─ Persists agent state across runs
```

---

## Data Flow: Example Tool Call

```
Local Agent (running on your machine)
  │
  ├─ Needs to check spare parts availability
  ├─ Calls: get_spare_parts(issue_type="motor_bearing_failure")
  │
  └─→ HTTPS Request to AgentCore Gateway
      │
      └─→ AWS AgentCore Gateway
          │
          ├─ Authenticates agent credentials
          ├─ Validates input schema
          └─ Routes to: Lambda function mcp-get-spare-parts
             │
             └─→ Lambda mcp-get-spare-parts
                 │
                 ├─ Reads: s3://agentic-ai-poc-3-1-data/data/spare_parts_inventory.json
                 ├─ Looks up: motor_bearing_failure
                 └─ Returns: {available: true, part_name: "Motor Bearing Assembly", ...}
                    │
                    └─→ HTTPS Response back through AgentCore
                        │
                        └─→ Local Agent receives result
                            │
                            └─ Uses result to make decision (schedule or escalate)
```

---

## Implementation Schedule: Phase 1 Week 2

### Day 1-4: Deploy Tools to AWS + Setup S3

**Steps:**

1. **Generate Data Locally** (takes ~5 minutes)
   ```bash
   python -m src.data.equipment_simulator --output-dir data/generated
   python -m src.data.inventory_data_generator --output-dir data/generated
   ```

2. **Upload Data to S3** (takes ~2 minutes)
   ```bash
   python scripts/setup_s3_for_mcp_tools.py \
     --bucket-name agentic-ai-poc-3-1-data \
     --data-dir data/generated
   ```

3. **Define MCP Tool Schemas** (takes ~1 hour)
   - Create `src/tools/schemas.py`
   - Define 3 tools: get_spare_parts, schedule_maintenance, create_work_order

4. **Create Lambda Functions** (takes ~2 hours)
   - Lambda 1: get_spare_parts (reads S3)
   - Lambda 2: schedule_maintenance (reads S3 if needed)
   - Deploy to AWS

5. **Create ECS Task Definition** (takes ~1.5 hours)
   - FastAPI container for create_work_order
   - Deploy to AWS

6. **Register Tools with AgentCore Gateway** (takes ~1 hour)
   - Register Lambda functions
   - Register ECS task
   - Configure schemas
   - Test endpoints

7. **Configure Agent Authentication** (takes ~1.5 hours)
   - Set up AgentCore Identity
   - Configure Cognito
   - Create agent credentials
   - Test connection

**Total Time: ~8-10 hours spread over 4 days**

### Day 5-7: Connect Agents to Tools

1. **Update Agents** (takes ~3 hours)
   - Add AgentCore Gateway client
   - Add credential manager
   - Integrate tool calls
   - Add error handling

2. **Test Agents with Tools** (takes ~2 hours)
   - Unit tests (mock tools)
   - Integration tests (real AgentCore)
   - End-to-end tests

3. **Build Dashboard** (takes ~2 hours)
   - Flask UI showing results
   - Connect to agents
   - Display data

**Total Time: ~7 hours spread over 3 days**

---

## Why This Architecture?

| Aspect | Phase 1 | Why? |
|--------|---------|-----|
| **Agents Location** | Local | Can test quickly, no AWS compute cost |
| **Agents Data Source** | Local files | Developers can modify/debug easily |
| **Tools Location** | AWS Lambda/ECS | Production-ready, scalable |
| **Tools Data Source** | S3 | Same location as tools (no network latency), simulates production |
| **Data Flow** | Agents → AgentCore → Tools | Same architecture as production (when agents move to AWS later) |

**Benefits:**
- Tools deployed once to AWS (no rebuilding later)
- Agents can test locally first
- Data already in S3 (ready for Phase 2)
- Minimal changes when agents move to AWS (only agent code changes, tools stay same)

---

## Phase 1 to Phase 2 Migration (Next Week)

When moving to Phase 2 (agents on AWS):

**What Changes:**
1. Deploy agents to AWS (Fargate or Lambda)
2. Agents read from S3 instead of local files
3. Everything else stays the same

**What Doesn't Change:**
- Tools (Lambda/ECS) - already in AWS
- Tool schemas - unchanged
- Tool logic - unchanged
- AgentCore Gateway - unchanged

**Agent Code Change (only this):**
```python
# Phase 1 (Local)
device_data = json.load(open('data/generated/device-001.json'))

# Phase 2 (AWS)
s3 = boto3.client('s3')
obj = s3.get_object(Bucket='agentic-ai-poc-3-1-data', Key='data/device-001.json')
device_data = json.loads(obj['Body'].read())

# Rest of agent code: IDENTICAL
```

---

## Critical Files for Phase 1

### Created This Week

1. **`scripts/setup_s3_for_mcp_tools.py`** (NEW)
   - 350+ lines
   - Creates S3 bucket
   - Uploads generated data
   - Configures permissions
   - Generates summary

2. **`src/data/equipment_simulator.py`** (EXISTING - used as-is)
   - Generates 16 device sensor files
   - 720 readings per device

3. **`src/data/inventory_data_generator.py`** (EXISTING - used as-is)
   - Generates spare parts inventory
   - 8 part types with metadata

### To Create (Days 1-4)

4. **`src/tools/schemas.py`** (NEW)
   - MCP tool schema definitions
   - 3 tools: get_spare_parts, schedule_maintenance, create_work_order

5. **`src/lambda_functions/`** (NEW)
   - Lambda function implementations
   - Each reads from S3 as needed

6. **`src/ecs_tasks/`** (NEW)
   - ECS task Dockerfile + app.py
   - FastAPI-based work order service

### Updated This Week

7. **`PHASE1_WEEK2_DAY1_4_SETUP.md`** - CORRECTED
   - Reflects S3 upload step
   - Clarifies tool deployment to AWS
   - Shows data flow

8. **`PHASE1_WEEK2_DAY1_4_IMPLEMENTATION.md`** - CORRECTED
   - S3 script documentation
   - Tool implementation examples
   - IAM configuration

---

## Success Criteria for Phase 1

✅ Data generated locally (18 JSON files)  
✅ Data uploaded to S3 (verified via script output)  
✅ Lambda functions deployed and tested  
✅ ECS container deployed and tested  
✅ Tools registered with AgentCore Gateway  
✅ Agents can call tools via AgentCore  
✅ Tools can read data from S3  
✅ Agent credentials working  
✅ AgentCore Memory configured  
✅ End-to-end test passes (agent → tool → result)  

---

## Questions? Clarifications

### Q: Why not keep everything local in Phase 1?
**A:** Because:
1. Tools need to be in AWS anyway (for scalability)
2. S3 data simulates production (agents will read from S3 in Phase 2)
3. No extra work building local tools, then rebuilding for AWS
4. Cleaner separation: local agents, AWS tools

### Q: Why upload data to S3 so early?
**A:** Because:
1. Tools run in AWS (Lambda/ECS can't access local files)
2. No point waiting - data is already generated
3. S3 access is free to test (no data transfer costs)
4. Simulates Phase 2 architecture (agents will use S3 later)

### Q: What if my S3 upload fails?
**A:** The script handles errors and tells you exactly what went wrong. You can re-run it - it will skip files already uploaded.

### Q: Can I test without AWS?
**A:** Yes:
1. Local agents can run without AWS
2. Just don't call tools (they're in AWS)
3. In Day 5-7, integrate with tools

---

## Summary

**Phase 1 Week 2 Deployment Model:**

| Component | Location | Used By | Notes |
|-----------|----------|---------|-------|
| Agents | Local machine | You (developer) | Read from local data/generated/ |
| Agent Data | `data/generated/` | Agents | Local files, no upload to S3 |
| MCP Tools | AWS Lambda/ECS | Agents via AgentCore | Deployed this week |
| Tool Data | S3 bucket | Lambda/ECS tools | Uploaded this week |
| Tool Coordination | AWS AgentCore Gateway | Agents + Tools | Authentication + routing |

**Key Point:** Tools are in AWS reading from S3. Agents are local reading from local files. Both can coexist and communicate via AgentCore. No local tool rebuilding needed.
