---
marp: true
title: Hackathon Kickoff — Agentic AI Equipment Diagnostics
paginate: true
---

# Agentic AI Equipment Diagnostics
### Hackathon Kickoff
Extend a real multi-agent system: new agents, tools, dashboards, data

---

## Slide 1 — Title / Welcome

- Project: multi-agent equipment health & diagnostics platform
- Today: understand the pipeline, then pick a track and start building
- This deck + the 1-pager are your reference for the whole event

---

## Slide 2 — The Problem

- Industrial equipment (pumps, motors, etc.) streams sensor data
- Question the system answers: **is this device healthy? if not, why, and what do we do about it?**
- Pipeline: sensor data → health verdict → root-cause diagnosis → action (work order / parts / schedule)

---

## Slide 3 — High-Level Architecture

```
Dashboard/Client → Orchestrator → HealthAgent → DiagnosisAgent
                                                      │
                                          LLM Gate (only if ambiguous)
                                                      │
                                     MCP Tools via AgentCore Gateway
                                     (schedule-maintenance, work-orders, spare-parts)
```

- Everything is orchestrated as a **LangGraph workflow**
- Agents never call tools directly — always through the Gateway

---

## Slide 4 — Step 1: Orchestrator

- Entry point for all requests (`src/services/orchestrator`)
- Loads device + sensor data (`DeviceLoader`, backed by S3 synthetic data)
- Dispatches into the LangGraph workflow (`src/graph/workflow.py`)

---

## Slide 5 — Step 2: HealthAgent

- File: `src/agents/health_agent.py`
- Analyzes sensor readings → `health_status` + `confidence`
- **Fast path:** if healthy → return immediately, no LLM, no tools (~20-80ms)
- If warning/alert/critical → hands off to DiagnosisAgent

---

## Slide 6 — Step 3: DiagnosisAgent

- File: `src/agents/diagnosis_agent.py`
- Pattern-matches the failure signature → diagnosis + confidence + recommended action
- Confidence drives the next decision (Slide 7)

---

## Slide 7 — The LLM Gate (key design decision)

- If `confidence >= 0.85` → rules-based decision, **no LLM call** (cheap, fast)
- If `confidence < 0.85` → invoke Azure OpenAI GPT-4o (`src/llm/llm_client.py`) for refined reasoning
- This is a deliberate **cost/latency optimization** — see `LLM_DECISION_LOGIC.md`
- Any new feature should state which side of this gate it lives on

---

## Slide 8 — MCP Tools & AgentCore Gateway

- Tools live in `tools/lambdas/` (e.g. `schedule_maintenance_handler.py`, `get_spare_parts_handler.py`)
- Called only via the Gateway — handles routing + identity (Cognito)
- Tools themselves write to DynamoDB/S3 (real business data) — that's separate from "agent memory," which isn't wired up yet
- Gateway client: `src/gateway/client.py`

---

## Slide 9 — Dashboard

- Backend routes: `src/dashboard/routes/api.py` (`/fleet-summary`, `/maintenance-schedule`, `/work-orders`, `/spare-parts`)
- Frontend: `src/dashboard/templates/index.html` + `static/`
- All endpoints serve **real** MCP/agent data, not mocks

---

## Slide 10 — Code Map (cheat sheet)

| Concept | Path |
|---|---|
| Agents | `src/agents/` |
| Workflow | `src/graph/workflow.py` |
| LLM client | `src/llm/llm_client.py` |
| Gateway client | `src/gateway/client.py` |
| MCP tools | `tools/lambdas/` |
| Dashboard API | `src/dashboard/routes/api.py` |
| Dashboard UI | `src/dashboard/templates/` |
| Deployment scripts | `scripts/` (shared infra — coordinate!) |

---

## Slide 11 — 4 Extension Points

1. **New agent** — subclass `base_agent.py`, wire into `workflow.py`
2. **New MCP tool** — add handler in `tools/lambdas/`, register with Gateway
3. **New dashboard feature** — new route in `api.py` + UI in `templates/`
4. **New data/device type** — extend `DeviceLoader` + `HealthAgent` rules

---

## Slide 12 — Two Runtimes: Local vs AWS AgentCore

- Same agent **logic** (`src/agents/health_agent.py`, `diagnosis_agent.py`) is reused by both — only the outer "wrapper" differs
- **Local:** each agent is a plain FastAPI app (`src/services/<agent>/app.py`), run with `uvicorn` on 8000/8001/8002, talking over plain HTTP (`src/graph/workflow.py`)
- **AgentCore Runtime (AWS):** the same agent's `handler.py` (Lambda-style) is wrapped by `agentcore_entrypoint.py` + `BedrockAgentCoreApp`, serving `POST /invocations` / `GET /ping` on port 8080, invoked via `boto3` (`src/graph/workflow_agentcore.py`)

---

## Slide 13 — ⚠️ Known Gotcha: docker-compose vs Dockerfiles

- Each agent actually has **two Dockerfiles**: `src/services/<agent>/Dockerfile` (local, runs `app.py`, port 8001/8002/8000) vs root `Dockerfile.health_agent` / `Dockerfile.diagnosis_agent` / `Dockerfile.orchestrator` (AgentCore-only, runs `agentcore_entrypoint.py`, port 8080)
- `docker-compose.yml` currently points `dockerfile:` at the **root AgentCore ones** — but still expects port 8001/8002/8000 and `/health` checks. **This mismatch means `docker-compose up` will not work correctly as-is.**
- **For the hackathon:** skip Docker for local dev — run each service directly:
  ```bash
  python -m uvicorn src.services.health_agent.app:app --port 8001
  python -m uvicorn src.services.diagnosis_agent.app:app --port 8002
  python -m uvicorn src.services.orchestrator.app:app --port 8000
  ```
- Only use the root `Dockerfile.*` files when actually building images for AWS AgentCore Runtime

---

## Slide 14 — Deploying to AgentCore Runtime (only if your idea needs it)

- Images **must** be `linux/arm64` (Graviton): `docker buildx build --platform linux/arm64 -f Dockerfile.X -t NAME:arm64 --load .`
- Deploy/update via `scripts/deploy_to_agentcore_boto3.py` (updates the runtime in place, doesn't recreate it)
- ARM64 builds under emulation are slow (~15 min) — don't rebuild per commit, only when ready to test on AWS
- **Ask a facilitator first** — this touches shared AWS infra used by other teams

---

## Slide 15 — Local Dev Loop (day-to-day)

```bash
python -m uvicorn src.services.health_agent.app:app --port 8001
python -m uvicorn src.services.diagnosis_agent.app:app --port 8002
python -m uvicorn src.services.orchestrator.app:app --port 8000   # localhost:8000/docs
cd src/dashboard && python app.py                                  # dashboard
python -m pytest tests/ -v                                         # tests
```

**Build and test locally before touching AWS deployment.**

---

## Slide 16 — Gotchas (save yourself hours)

- Sensor payload shape: don't double-wrap `{"readings": {...}}` — silently breaks anomaly detection, no error thrown
- AgentCore Runtime images **must** be `linux/arm64` — plain `docker build` silently produces the wrong arch
- Public API Gateway has **no auth** today — fine for demo, don't assume it's production-safe
- Session IDs need left-padding to 33 chars in orchestrator action dispatch — copy the existing pattern

---

## Slide 17 — Hackathon Rules & Tracks

- Work on feature branches; don't push to shared AWS resources without a facilitator check
- Prefer the extension points over rewriting core agent logic
- **Tracks:** (1) New Agent, (2) New MCP Tool, (3) Dashboard/UX, (4) Data & Prompt Tuning

---

## Slide 18 — Judging Criteria

- Working demo / correctness
- Clean integration with the existing pipeline (used extension points vs. rewrote core)
- Clarity of the real-world maintenance-ops value

---

## Slide 19 — Let's Build

- Docs: `README.md`, `docs/`, `HACKATHON_PRESENTATION_GUIDE.md`, `HACKATHON_QUICK_REFERENCE.md`
- Questions welcome anytime — go pick a track!
