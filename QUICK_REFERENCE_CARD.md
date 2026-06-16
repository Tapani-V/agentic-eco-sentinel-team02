# QUICK REFERENCE CARD - Week 2 Days 5-7

## 🚀 START IN 10 SECONDS

```bash
cd /home/skroy/AGENTIC_AI_POC_Phase3_1
bash run_e2e_tests.sh test
```

Done! All services running + all tests passing.

---

## 📍 SERVICE ENDPOINTS

| Service | Port | Endpoint | Status |
|---------|------|----------|--------|
| Orchestrator | 8000 | POST /process | ✅ Ready |
| HealthAgent | 8001 | POST /analyze | ✅ Ready |
| DiagnosisAgent | 8002 | POST /diagnose | ✅ Ready |

---

## 🧪 TEST COMMANDS

```bash
# All-in-one (recommended)
bash run_e2e_tests.sh test

# Manual Python tester
python run_manual_e2e_test.py

# Async pytest
python tests/test_e2e_all_stories.py

# Pre-flight check
bash preflight_check.sh

# Health check
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
```

---

## 🐳 DOCKER COMMANDS

```bash
# Start all services
docker-compose up -d --build

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Service status
docker-compose ps
```

---

## 📊 EXPECTED RESULTS

| Story | Time | Result |
|-------|------|--------|
| 1: Happy | ~80ms | healthy → no action |
| 2: Simple | ~200ms | warning → schedule |
| 3: Ambiguous | ~450ms | warning → LLM + parts |
| 4: Emergency | ~120ms | critical → work order |

---

## 🔧 TROUBLESHOOTING

| Issue | Fix |
|-------|-----|
| Services won't start | `docker-compose down -v && docker-compose up -d --build` |
| Health check fails | `sleep 10 && curl http://localhost:8000/health` |
| Port in use | `lsof -i :8000 && kill -9 <PID>` |
| Tests timeout | `docker-compose logs orchestrator` |

---

## 📚 DOCUMENTATION

| Guide | Link |
|-------|------|
| Quick Start | [DOCKER_E2E_QUICK_START.md](DOCKER_E2E_QUICK_START.md) |
| Complete | [WEEK2_DAY5_7_COMPLETE.md](WEEK2_DAY5_7_COMPLETE.md) |
| Implementation | [IMPLEMENTATION_WEEK2_DAY5_7_DOCKER_E2E.md](IMPLEMENTATION_WEEK2_DAY5_7_DOCKER_E2E.md) |
| Architecture | [WEEK2_DAY5_7_AGENT_INTEGRATION.md](WEEK2_DAY5_7_AGENT_INTEGRATION.md) |
| Summary | [FINAL_DELIVERY_SUMMARY.md](FINAL_DELIVERY_SUMMARY.md) |

---

## 🎯 KEY FILES

### Services
- `src/agents/health_agent.py` - Health classification
- `src/agents/diagnosis_agent.py` - Root cause analysis
- `src/graph/workflow.py` - Orchestration logic

### Docker
- `docker-compose.yml` - Service orchestration
- `Dockerfile.orchestrator` - Orchestrator image
- `Dockerfile.health_agent` - HealthAgent image
- `Dockerfile.diagnosis_agent` - DiagnosisAgent image

### Testing
- `scripts/run_e2e_tests.sh` - Automated runner
- `scripts/run_manual_e2e_test.py` - Manual tester
- `tests/test_e2e_all_stories.py` - Pytest suite

---

## ✨ ARCHITECTURE IN 30 SECONDS

```
Client Request → Orchestrator (8000)
                    ↓
                HealthAgent (8001)
                    ↓
               Router Decision
                    ↓
        Happy?  →  Return (Cost Optimization)
        Warning/Critical? → DiagnosisAgent (8002)
                    ↓
            Confidence Check
                    ↓
        ≥0.85? → Trust Rule (Fast)
        <0.85? → Call LLM (Accurate)
                    ↓
            Execute Action
                    ↓
        MCP Tool Call (if needed)
                    ↓
        Return Results to Client
```

---

## 💡 SMART DECISIONS

**HealthAgent Never Calls Tools**
- Pure threshold analysis
- 100% local, no AWS dependency
- Super fast response

**DiagnosisAgent Calls Tools Smart**
- High confidence (≥0.85) → Trust rule → 1 tool call
- Low confidence (<0.85) → Ask LLM → 1-2 tool calls

**Router Skips Diagnosis for Healthy**
- Healthy devices → No analysis needed
- Saves LLM costs + response time
- 80ms vs 200+ms

---

## 🎓 3 PATTERNS TO REMEMBER

### Pattern 1: Core + Wrapper
```
Core:     src/agents/health_agent.py (pure Python)
Wrapper:  src/services/health_agent/app.py (FastAPI)
Benefit:  Reusable across any runtime
```

### Pattern 2: Confidence-Based Routing
```
High Conf (≥0.85):  Use rule (fast)
Low Conf (<0.85):   Use LLM (accurate)
Cost Effect:        Save ~80% of LLM calls
```

### Pattern 3: HTTP Between Services
```
No shared state
Stateless design
Easy to scale horizontally
```

---

## 🚀 NEXT STEPS AFTER TESTING

1. Deploy to AWS ECR
2. Run on ECS Fargate
3. Set up CloudWatch monitoring
4. Connect real device streams

---

## ⚡ ONE-LINERS

```bash
# Build only
docker-compose build

# Start only
docker-compose up -d

# Test only (after services running)
python run_manual_e2e_test.py

# Clean up
docker-compose down -v --rmi all

# Check everything
bash preflight_check.sh
```

---

**Status: ✅ READY**

All components working. All tests passing. Ready to deploy.

