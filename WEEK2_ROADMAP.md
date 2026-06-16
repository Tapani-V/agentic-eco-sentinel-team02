# Phase 1 Week 2: Complete Roadmap

Full overview of Week 2 Day 1-4 and Day 5-7 work.

---

## Week 2 Overview

Transform agents from self-sufficient to tool-enhanced through AWS AgentCore integration.

### Timeline

| Phase | Dates | Focus | Status |
|-------|-------|-------|--------|
| **Day 1-4** | May 27-30 | Create and register MCP tools | 📋 Planning |
| **Day 5-7** | May 31-Jun 2 | Upgrade agents to use tools | 📋 Planning |

---

## Day 1-4: Build MCP Tools & Register with AgentCore

**Deliverables:** Tools deployed and registered on AWS

### What You'll Create

```
Lambda Functions (Python):
├─ get_maintenance_history (reads DynamoDB)
├─ get_device_alerts (reads DynamoDB)
├─ schedule_maintenance (writes to DynamoDB)
└─ get_spare_parts (reads S3/external)

ECS Container (Python + FastAPI):
└─ create_work_order (custom business logic)

Infrastructure:
├─ IAM roles for Lambda/ECS
├─ AgentCore Memory namespace
└─ Tool registration with AgentCore Gateway
```

### Documentation
- 📄 [PHASE1_WEEK2_DAY1_4_SETUP.md](PHASE1_WEEK2_DAY1_4_SETUP.md) - Planning (high-level)
- 📄 [PHASE1_WEEK2_DAY1_4_IMPLEMENTATION.md](PHASE1_WEEK2_DAY1_4_IMPLEMENTATION.md) - Implementation (detailed code)

### Success Criteria Day 1-4
- ✅ All 5 tools deployed to AWS
- ✅ Tools registered with AgentCore Gateway
- ✅ AgentCore Identity configured
- ✅ AgentCore Memory namespace created
- ✅ Can invoke tools successfully

---

## Day 5-7: Connect Agents to Tools

**Deliverables:** Agents using tools through AgentCore

### What You'll Do

```
Agent Upgrades:
├─ HealthAgent → Add tool calls
├─ DiagnosisAgent → Add tool calls
└─ EscalationAgent → Add tool calls

Infrastructure:
├─ AgentCoreGateway client class
├─ AgentCoreCredentialManager class
└─ Dashboard integration with tools

Testing:
├─ Unit tests (mock tools)
├─ Integration tests (fake AgentCore)
├─ End-to-end tests (real AWS)
└─ Workflow integration tests
```

### Documentation
- 📄 [PHASE1_WEEK2_DAY5_7_SETUP.md](PHASE1_WEEK2_DAY5_7_SETUP.md) - Planning (high-level)
- 📄 PHASE1_WEEK2_DAY5_7_IMPLEMENTATION.md - Implementation (created after Day 1-4)

### Success Criteria Day 5-7
- ✅ All agents upgraded to use tools
- ✅ Agents can authenticate with AgentCore Identity
- ✅ Agents invoke tools through AgentCore Gateway
- ✅ Tool responses integrated into decisions
- ✅ Fallback logic working (if tools fail)
- ✅ All tests passing
- ✅ Dashboard displays tool results

---

## Reference Documents

### Agent Upgrade Details
- 📄 [AGENT_UPGRADE_GUIDE.md](AGENT_UPGRADE_GUIDE.md) - Exact code changes for each agent

### Data Storage Strategy
- 📄 [PHASE1_WEEK2_DAY1_4_SETUP.md](PHASE1_WEEK2_DAY1_4_SETUP.md) - S3 data migration path (Week 3+)

---

## Week 2 Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           Week 2 Integration                             │
└──────────────────────────────────────────────────────────────────────────┘

Local Machine (Your Laptop)
┌────────────────────────────────────────────────────────────────────────┐
│ Agents (upgraded with tool support)                                    │
│ ├─ HealthAgent (calls tools when needed)                              │
│ ├─ DiagnosisAgent (calls tools when needed)                           │
│ └─ EscalationAgent (calls tools when needed)                          │
│                          ↓                                             │
│ LangGraph Workflow (agents communicate + call tools)                  │
│                          ↓                                             │
│ AgentCore Identity (obtains credentials)                              │
└────────────────────────────────────────────────────────────────────────┘
                            ↓ HTTPS
                   AgentCore Gateway (AWS)
                   (routes tool calls)
                            ↓
        ┌───────────────────┼───────────────────┐
        ↓                   ↓                   ↓
   Lambda Fns           Lambda Fns         ECS Container
   (read ops)           (write ops)        (complex ops)
        ↓                   ↓                   ↓
   DynamoDB          DynamoDB            External APIs
   (maintenance)     (scheduling)        (work orders)
```

---

## Dependency Chain

```
Day 1-4 Outputs → Day 5-7 Inputs
    ↓
Tools deployed on AWS
    ↓
Tools registered with AgentCore
    ↓
AgentCore endpoints available
    ↓
Day 5-7: Agents connect and use tools
```

**If Day 1-4 is incomplete, Day 5-7 cannot proceed.**

---

## Key Files by Phase

### Day 1-4 Outputs
```
AWS Lambda:
  └─ get_maintenance_history function
  └─ get_device_alerts function
  └─ schedule_maintenance function
  └─ get_spare_parts function

AWS ECS:
  └─ create_work_order service

AWS Configuration:
  └─ AgentCore Gateway registered tools
  └─ AgentCore Identity pool
  └─ AgentCore Memory namespace
```

### Day 5-7 Outputs
```
Python Code:
  └─ src/identity/agentcore_credentials.py
  └─ src/api/agentcore_gateway.py
  └─ src/agents/health_agent.py (updated)
  └─ src/agents/diagnosis_agent.py (updated)
  └─ src/agents/escalation_agent.py (updated)

Tests:
  └─ test_*_with_tools.py (all agents)
  └─ test_agent_agentcore_integration.py
  └─ test_agent_with_real_agentcore.py
  └─ test_dashboard_agentcore.py

Configuration:
  └─ Updated .env with AgentCore endpoints
```

---

## Testing Strategy Across Phases

### Day 1-4: Tool Validation
```
Unit Tests (Python)
  ├─ Lambda function logic
  ├─ ECS container logic
  └─ MCP schemas

Integration Tests
  ├─ Lambda invokes DynamoDB
  ├─ ECS calls external APIs
  └─ Tools return proper MCP format

Deployment Tests
  ├─ Tools deployed successfully
  ├─ Tools registered with AgentCore
  └─ Manual tool invocation works
```

### Day 5-7: Agent Integration
```
Unit Tests (with mocks)
  ├─ Agent tool invocation logic
  ├─ Agent decision with tool data
  └─ Fallback logic

Integration Tests (with fake AgentCore)
  ├─ Agent → Gateway → Tool → Agent
  ├─ Multiple tool calls from one agent
  └─ Parallel tool calls

End-to-End Tests (with real AWS)
  ├─ Agent credentials from AgentCore
  ├─ Real tool invocation through AgentCore
  └─ Complete workflow with tools

Workflow Tests
  ├─ LangGraph agents use tools
  ├─ Agent escalation with tools
  └─ Memory persistence with tools
```

---

## Prerequisites

### For Day 1-4
- AWS CLI configured
- IAM permissions (create Lambda, ECS, DynamoDB)
- Python 3.9+ locally
- FastAPI knowledge helpful

### For Day 5-7
- Day 1-4 tools fully deployed
- AgentCore endpoints available
- AWS credentials working
- Understanding of agent patterns

---

## Success Metrics

### After Day 1-4
- Tool test success rate: 100%
- AgentCore registration: Complete
- Tool latency: < 500ms (median)
- Tool availability: 100%

### After Day 5-7
- Agent test success rate: 100%
- Agent tool invocation success: 100%
- Fallback logic success rate: 100%
- End-to-end workflow success: 100%
- Dashboard integration: Complete

---

## Rollback Plan (if needed)

### If Day 1-4 fails
- Delete Lambda/ECS deployments
- Delete IAM roles
- Retry with updated code

### If Day 5-7 fails
- Revert agent code to Week 1 version
- Agents work without tools (Day 1-4 intact)
- Fix agent integration issues
- Redeploy agents

**Key:** Week 1 agents still work if Week 2 tools aren't available.

---

## What Happens If You Skip Week 2

### Agents Work As-Is
- All Week 1 agents still function
- No tool data available
- Decisions based on local data only
- Less intelligent (no external context)

### You Miss Out
- Enhanced decision making
- Maintenance history context
- Real-time alerting integration
- Work order automation
- Spare parts inventory integration

---

## Next Phase Preview (Week 3+)

After Week 2 completes:
- Monitor tool performance
- Add observability (CloudWatch, X-Ray)
- Migrate tool data to S3 (optional)
- Add more sophisticated tools
- Multi-agent coordination patterns
- Production hardening

---

## Quick Navigation

| Need | Document |
|------|-----------|
| Week 2 Day 1-4 high-level plan | [PHASE1_WEEK2_DAY1_4_SETUP.md](PHASE1_WEEK2_DAY1_4_SETUP.md) |
| Week 2 Day 1-4 detailed code | [PHASE1_WEEK2_DAY1_4_IMPLEMENTATION.md](PHASE1_WEEK2_DAY1_4_IMPLEMENTATION.md) |
| Week 2 Day 5-7 high-level plan | [PHASE1_WEEK2_DAY5_7_SETUP.md](PHASE1_WEEK2_DAY5_7_SETUP.md) |
| Agent upgrade patterns | [AGENT_UPGRADE_GUIDE.md](AGENT_UPGRADE_GUIDE.md) |
| Week 1 agents (reference) | `src/agents/` |
| Architecture decisions | [ARCHITECTURE.md](docs/ARCHITECTURE.md) |
