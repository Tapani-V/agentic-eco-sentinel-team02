# Agentic AI POC - Multi-Agent Equipment Diagnostics

**Phase 1 (Current):** Local agents + real AWS services  
**Phase 2 (Future):** Serverless deployment with auto-scaling

---

## 🎯 What You're Building

A production-grade multi-agent system for equipment diagnostics:

```
┌─────────────────────────────────┐
│  YOUR MACHINE (Phase 1)         │
│  ├─ 4 Local Agents (Python)     │
│  ├─ FastAPI (port 8000)         │
│  └─ React Dashboard (port 3000) │
└──────────┬──────────────────────┘
           │ AgentCore Gateway
           ▼
    ┌────────────────────┐
    │  AWS SERVICES      │
    │  ├─ Lambda Tools   │
    │  ├─ ECS Tools      │
    │  ├─ Cognito        │
    │  ├─ DynamoDB       │
    │  └─ AgentCore      │
    └────────────────────┘
```

**Key Pattern:** Agents call AgentCore Gateway (not tools directly). Gateway handles:
- **Tool Routing** → Lambda/ECS endpoints
- **Memory** → DynamoDB conversation storage
- **Identity** → Cognito token validation

---

## 📚 Documentation

**Start here:**

| Document | Purpose | Time |
|----------|---------|------|
| [PHASE_1_ARCHITECTURE.md](docs/PHASE_1_ARCHITECTURE.md) | System design | 15 min |
| [PHASE_1_IMPLEMENTATION.md](docs/PHASE_1_IMPLEMENTATION.md) | Week-by-week guide | Read as you build |
| [PHASE_2_ARCHITECTURE.md](docs/PHASE_2_ARCHITECTURE.md) | Serverless deployment | 10 min |
| [PHASE_2_IMPLEMENTATION.md](docs/PHASE_2_IMPLEMENTATION.md) | Phase 2 steps | When ready |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node 18+
- AWS account
- `aws configure` completed

### Phase 1 Workflow

1. **Understand:** Read [PHASE_1_ARCHITECTURE.md](docs/PHASE_1_ARCHITECTURE.md)
2. **Follow:** Read current day in [PHASE_1_IMPLEMENTATION.md](docs/PHASE_1_IMPLEMENTATION.md)
3. **Request Code:** Ask AI: *"Generate code for Week 1 Day 1-2: Project setup"*
4. **Integrate:** Copy code, run tests
5. **Next:** Move to next day/week

### Running Phase 1

```bash
# Terminal 1: Backend
python -m src.api.main
# http://localhost:8000/docs

# Terminal 2: Frontend
cd dashboard && npm start
# http://localhost:3000

# Terminal 3: Tests
python -m pytest tests/ -v
```

---

## 🏗️ What Gets Built

**Week 1 (Setup):**
- Project structure + AWS resources (Cognito, DynamoDB)
- Synthetic sensor data generator
- Local agents with AgentCore Gateway integration
- AgentCore SDK setup

**Week 2 (MCP Tools + Registration):**
- Lambda tools deployed (MCP-1, MCP-2)
- ECS tools deployed (MCP-3, MCP-4) with GPT-4o LLM
- **Tools registered with AgentCore Gateway** (critical step)
- FastAPI backend integration

**Week 3 (Frontend + Testing):**
- React dashboard
- End-to-end testing
- Production ready

---

## 💰 Cost Estimate

| Phase | Monthly | Notes |
|-------|---------|-------|
| Phase 1 (local agents) | $35-80 | Includes ~$5-15 for LLM (GPT-4o) if enabled |
| Phase 2 (serverless) | $50-120 | Agents move to Lambda, LLM unchanged |

---

## ✅ Phase 1 Success

- All 4 agents working locally with AgentCore Gateway
- Lambda + ECS tools deployed and registered with Gateway
- FastAPI + React fully functional
- E2E tests passing (agent → Gateway → tools → results)
- Ready for Phase 2

---

## 📋 Tech Stack

| Component | Technology |
|-----------|-----------|
| Agents | Python + LangGraph |
| API | FastAPI |
| UI | React 18+ |
| Tools (Fast) | AWS Lambda |
| Tools (Complex) | ECS Fargate + GPT-4o LLM |
| Auth | Cognito |
| Memory | DynamoDB |
| Gateway | AgentCore |
| LLM | Azure OpenAI (GPT-4o) |

---

## 🎯 Phase 1 vs Phase 2

| Aspect | Phase 1 | Phase 2 |
|--------|---------|---------|
| Agents | Local Python | AWS Lambda/ECS (managed) |
| Tool Access | Via AgentCore Gateway | Via AgentCore Gateway (same) |
| Memory | DynamoDB (via Gateway) | DynamoDB (via Gateway) |
| Identity | Cognito (via Gateway) | Cognito (via Gateway) |
| API | FastAPI | API Gateway |
| Scaling | ~20 req/sec | 1000+ req/sec |
| Deployment | Python scripts | Terraform |
| **Key difference** | **Agents run locally** | **Agents managed by AWS** |

---

**Next:** Read [PHASE_1_ARCHITECTURE.md](docs/PHASE_1_ARCHITECTURE.md) and start Week 1!
