# Hackathon Kickoff Presentation Guide

Audience: 3-4 teams who will extend this project (Agentic AI equipment-diagnostics POC) during the hackathon.
Goal of the talk: give them just enough of the mental model + code map to start building in the first hour, not a full architecture deep-dive.

Suggested length: ~35-40 min talk + 10 min Q&A, using this doc as the leave-behind cheat sheet.

---

## 1. The problem this project solves (2 min)

- Domain: **predictive/reactive maintenance for industrial equipment** (pumps, motors, etc.) — a fleet of devices streams sensor readings, the system decides if a device is healthy, and if not, diagnoses the likely cause and can trigger maintenance actions (work orders, spare parts, scheduling).
- Frame it as: "sensor data in → health verdict → root-cause diagnosis → action" — this is the pipeline every team will extend.

## 2. The agent pipeline, end to end (10 min)

Walk this diagram live, pointing at real files as you go:

```
Client / Dashboard
      │  GET/POST /orchestrate...
      ▼
Orchestrator  (src/services/orchestrator, src/agents/orchestrator? -> LangGraph workflow: src/graph/workflow.py)
      │  loads device data (DeviceLoader -> S3 synthetic data)
      ▼
HealthAgent   (src/agents/health_agent.py)
      │  analyzes sensor readings -> health_status + confidence
      │
      ├─ IF healthy → return immediately (fast path, no LLM, no tools)
      │
      ▼ (if warning/alert/critical)
DiagnosisAgent (src/agents/diagnosis_agent.py)
      │  pattern-matches the failure -> diagnosis + confidence + recommended action
      │
      ├─ IF confidence >= 0.85 → rules-based decision (no LLM call)
      │
      ▼ (if confidence < 0.85)
LLM Gate (Azure OpenAI GPT-4o, src/llm/llm_client.py)
      │  only invoked for ambiguous cases — cost/latency optimization
      ▼
MCP Tools via AgentCore Gateway (tools/lambdas/*, Cognito-authenticated)
      - schedule-maintenance, create-work-order, get-spare-parts
      ▼
Response → Dashboard (src/dashboard) renders KPIs, work orders, schedules, parts
```

Key teaching points:
- **Cost/latency gating is a deliberate design pattern**, not an accident — cite [LLM_DECISION_LOGIC.md](LLM_DECISION_LOGIC.md). Healthy devices short-circuit before any LLM/tool call; only ambiguous diagnoses (<0.85 confidence) pay for an LLM call.
- Tools are never called directly by agents — everything goes through the **AgentCore Gateway**, which owns tool routing and identity (Cognito). This indirection is *the* extension seam for new tools.
- The LangGraph workflow ([src/graph/workflow.py](src/graph/workflow.py)) is the state machine wiring these agents together — new agents get added as new nodes/edges here.
- **DynamoDB is used for two unrelated things — don't confuse them:**
  1. `maintenance_schedules` table: real, live data written by the `schedule-maintenance` Lambda tool ([tools/lambdas/schedule_maintenance_handler.py](tools/lambdas/schedule_maintenance_handler.py)). Actively used today.
  2. A "conversation memory" table (`DYNAMODB_TABLE_NAME` in [.env](.env)) was provisioned early in planning for agent session/conversation history, but **no code in `src/` or `functions/` actually reads or writes it** — agents don't persist conversation history anywhere right now. Treat any "memory" mention in older docs as aspirational, not current behavior.

## 3. Where the code actually lives (5 min) — the map

| Concept | Path | Notes |
|---|---|---|
| Agents | [src/agents/](src/agents) (`base_agent.py`, `health_agent.py`, `diagnosis_agent.py`) | Subclass `base_agent.py` to add a new agent |
| Orchestrator service | [src/services/orchestrator/](src/services/orchestrator) | Owns device loading + action dispatch |
| LangGraph workflow | [src/graph/workflow.py](src/graph/workflow.py) / `workflow_agentcore.py` | Wire new agents in here |
| LLM client | [src/llm/llm_client.py](src/llm/llm_client.py) | Azure OpenAI GPT-4o wrapper |
| Gateway client (MCP/Cognito) | [src/gateway/client.py](src/gateway/client.py) | Auth + tool invocation |
| MCP tools (Lambda) | [tools/lambdas/](tools/lambdas) (`schedule_maintenance_handler.py`, `get_spare_parts_handler.py`) | Add a new file here + register with Gateway |
| Dashboard backend | [src/dashboard/routes/api.py](src/dashboard/routes/api.py) | New REST endpoints go here |
| Dashboard frontend | [src/dashboard/templates/](src/dashboard/templates), `static/` | Server-rendered templates + JS |
| Synthetic device data | `data/` (S3-backed in AWS, local fallback) | 17 sample devices, sensors per device |
| Deployment scripts | `scripts/` (build/push ARM64 images, deploy to AgentCore, add API routes) | Shared infra — coordinate before touching |

## 3.5. AWS SDK / toolkit layers used in this repo (3 min)

Three different AWS layers show up in the code. Only two of them run at request time — don't let teams conflate them:

| Layer | Package | Used for | Where | Runs at request time? |
|---|---|---|---|---|
| **boto3** (raw AWS SDK) | `boto3>=1.26.0` | Lambda tool handlers hitting S3/DynamoDB, `src/utils/device_loader.py` (S3), and `boto3.client('bedrock-agentcore').invoke_agent_runtime()` used by the orchestrator to invoke agent containers | `tools/lambdas/*.py`, [src/utils/device_loader.py](src/utils/device_loader.py), [src/graph/workflow_agentcore.py](src/graph/workflow_agentcore.py) | **Yes** |
| **bedrock-agentcore** (runtime SDK) | `bedrock-agentcore>=0.1.0` | Wraps each agent as an HTTP service AgentCore Runtime can call (`BedrockAgentCoreApp` — handles `POST /invocations`, `GET /ping` on port 8080) | [agentcore_entrypoint.py](agentcore_entrypoint.py), all three Dockerfiles | **Yes** |
| **bedrock-agentcore-starter-toolkit** | `bedrock-agentcore-starter-toolkit==0.3.9` | **One-time admin only**: creating the AgentCore Gateway and registering Lambda tools as MCP tools, via its own `GatewayClient`/`MemoryManager` classes | [scripts/create_agentcore_gateway_starter.py](scripts/create_agentcore_gateway_starter.py), [scripts/register_mcp_tools_starter.py](scripts/register_mcp_tools_starter.py) | **No** — setup-only, never imported by the running agents |

**Gotcha worth calling out explicitly:** there are **two different classes both named `GatewayClient`**:
- `bedrock_agentcore_starter_toolkit.operations.gateway.client.GatewayClient` — admin SDK, used once during setup scripts to create the Gateway/register tools.
- [src/gateway/client.py](src/gateway/client.py)'s own `GatewayClient` — a hand-written class using plain `requests` + Cognito OAuth token, imported by the actual agents ([src/agents/health_agent.py](src/agents/health_agent.py), [src/agents/diagnosis_agent.py](src/agents/diagnosis_agent.py)) to call MCP tools at runtime. This is the one teams should use/extend for new tool calls — not the starter toolkit's.

Rule of thumb: **boto3 = talk to AWS services directly at runtime; `bedrock_agentcore` = make your agent container runtime-compliant; `bedrock_agentcore_starter_toolkit` = one-time Gateway/tool-registration admin, not part of the live request path.**

## 4. The 4 concrete extension points (10 min) — this is the core of the talk

Present these as "if your idea fits one of these shapes, here's exactly what to touch":

1. **New agent** (e.g., a "CostAgent" that estimates repair cost, or an "AnomalyForecastAgent")
   - Subclass `base_agent.py`, implement `execute()`.
   - Add a node + edge in [src/graph/workflow.py](src/graph/workflow.py) to wire it into the pipeline (e.g., run after DiagnosisAgent).
   - Test locally first via `python -m pytest tests/` or the existing `test_agent_workflow.py` / `invoke_agent_test.py` scripts before touching any deployment.

2. **New MCP tool** (e.g., "get-warranty-status", "order-replacement-part", "notify-technician")
   - Add a handler in [tools/lambdas/](tools/lambdas) following `get_spare_parts_handler.py` as a template.
   - Tools are invoked *through the Gateway*, never directly — check [src/gateway/client.py](src/gateway/client.py) for the calling convention.
   - New tools need Gateway registration (ask a facilitator — this touches shared AWS infra).

3. **New dashboard feature** (e.g., a trend chart, a filter, an export button)
   - Add an endpoint in [src/dashboard/routes/api.py](src/dashboard/routes/api.py) following the existing `/fleet-summary`, `/maintenance-schedule` pattern (real MCP-tool-backed data, not mocks).
   - Add the UI in [src/dashboard/templates/index.html](src/dashboard/templates/index.html).

4. **New data source / device type** (e.g., new sensor type, new equipment category)
   - Extend the synthetic data generator / `DeviceLoader` and the anomaly rules in `HealthAgent`.
   - Watch the sensor-payload shape carefully — see gotcha below.

## 5. Local dev loop — and the Local vs AgentCore Runtime split (5 min)

Each agent actually has **two separate outer wrappers around the same core logic** ([src/agents/health_agent.py](src/agents/health_agent.py), `diagnosis_agent.py`):
- **Local:** [src/services/health_agent/app.py](src/services/health_agent/app.py) (and the equivalent `diagnosis_agent`/`orchestrator` `app.py`) — a plain FastAPI app run with `uvicorn` on ports 8001/8002/8000, wired together over plain HTTP via [src/graph/workflow.py](src/graph/workflow.py).
- **AWS AgentCore Runtime:** the same agent's `handler.py` (Lambda-style `lambda_handler(event, context)`) gets wrapped by [agentcore_entrypoint.py](agentcore_entrypoint.py) + `BedrockAgentCoreApp`, serving `POST /invocations` / `GET /ping` on port 8080, invoked via `boto3` from [src/graph/workflow_agentcore.py](src/graph/workflow_agentcore.py).

**⚠️ Verified current mismatch — flag this explicitly so teams don't lose time on it:** each agent also has two *Dockerfiles* — the local one at `src/services/<agent>/Dockerfile` (runs `app.py`, matches ports 8001/8002/8000) vs the root-level `Dockerfile.health_agent` / `Dockerfile.diagnosis_agent` / `Dockerfile.orchestrator` (AgentCore-only, runs `agentcore_entrypoint.py` on port 8080). [docker-compose.yml](docker-compose.yml) currently points its `dockerfile:` fields at the **root AgentCore ones**, while still expecting port 8001/8002/8000 and `/health` checks — so `docker-compose up` will not work correctly as committed today. This is a real inconsistency in the repo, not just something to explain away.

**Recommended hackathon workflow — skip Docker for local dev entirely:**
```bash
python -m uvicorn src.services.health_agent.app:app --port 8001
python -m uvicorn src.services.diagnosis_agent.app:app --port 8002
python -m uvicorn src.services.orchestrator.app:app --port 8000   # http://localhost:8000/docs

# Dashboard
cd src/dashboard && python app.py

# Tests
python -m pytest tests/ -v
```
Only build/use the root `Dockerfile.*` files (with `--platform linux/arm64`) when actually deploying to AWS AgentCore Runtime — treat them as deployment-only, not local-dev images, until `docker-compose.yml` is fixed to point at the per-service Dockerfiles.

## 6. Known gotchas / guardrails (5 min) — save teams hours

- **docker-compose vs Dockerfiles mismatch (see above)** — don't rely on `docker-compose up` for local dev right now; run each `app.py` directly with `uvicorn` instead.
- **Sensor payload shape bug (fixed once already):** if you touch `current_reading`/`readings` handling in `HealthAgent`, double-check you're not double-wrapping — a previous bug wrapped `{"readings": {...}}` twice, silently zeroing out all anomaly detection with no error. Trace exact shapes at each hop.
- **ARM64 only for AgentCore Runtime:** any Docker image deployed to AgentCore must be built with `--platform linux/arm64`. Plain `docker build` produces the wrong architecture and fails silently/misbehaves.
- **No auth on the public API Gateway today** (`authorizationType='NONE'`) — fine for a hackathon demo, but call this out explicitly so no team assumes it's production-secure or copies the pattern into something that will be exposed later.
- **Session IDs / padding quirks** in orchestrator action dispatch — short action names need padding (`session_id.ljust(33, '0')`); copy the existing pattern rather than reinventing.
- **Don't hand-edit deployment scripts under time pressure** — `scripts/deploy_to_agentcore_boto3.py` updates runtimes in place; mistakes here affect the shared environment for all teams.

## 7. Hackathon logistics slide (3 min)

- **Rules of engagement:** work on feature branches, don't push directly to shared AWS resources without a quick sanity check with a facilitator, keep new work under `src/` (or new tool folders) rather than editing existing agent files unless fixing a bug you found.
- **Judging criteria (suggested):** correctness/working demo, how cleanly it plugs into the existing pipeline (used the extension points vs. rewrote core logic), and clarity of the "why" (does it solve a real maintenance-ops problem).
- **Team track suggestions** (assign or let teams pick, to avoid overlap):
  1. **New agent track** — add a new reasoning step (cost estimation, technician recommendation, failure-forecast).
  2. **New tool track** — add an MCP tool that talks to a new "system of record" (warranty DB, technician roster, parts ordering).
  3. **Dashboard/UX track** — new visualizations, exports, alerts/notifications UI.
  4. **Data/quality track** — new device/sensor types, better synthetic data, or LLM prompt/confidence-threshold tuning with before/after metrics.

## 8. Closing (2 min)

- Point to `README.md` and `docs/` for deeper architecture reading.
- Remind them: **the fast path (healthy device, no LLM) and the LLM gate (confidence < 0.85) are the two design decisions everything else hangs off of** — any new feature should say which side of that gate it lives on.
