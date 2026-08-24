# Hackathon Quick Reference (1-Pager)

**Pipeline:** Orchestrator → HealthAgent → DiagnosisAgent → [LLM Gate if confidence < 0.85] → MCP Tools (via AgentCore Gateway) → Dashboard

**Fast path:** healthy device → returns immediately, no LLM/tools. **LLM Gate:** only called when diagnosis confidence < 0.85 (cost/latency optimization).

## Code Map
| Concept | Path |
|---|---|
| Agents (Health/Diagnosis) | `src/agents/` (`base_agent.py`, `health_agent.py`, `diagnosis_agent.py`) |
| Orchestrator service | `src/services/orchestrator/` |
| LangGraph workflow | `src/graph/workflow.py` |
| LLM client (Azure GPT-4o) | `src/llm/llm_client.py` |
| Gateway client (Cognito+MCP) | `src/gateway/client.py` |
| MCP tools | `tools/lambdas/` (`schedule_maintenance_handler.py`, `get_spare_parts_handler.py`) |
| Dashboard backend | `src/dashboard/routes/api.py` |
| Dashboard frontend | `src/dashboard/templates/`, `static/` |
| Device/sensor data | `data/` + `DeviceLoader` (S3-backed) |
| Deployment scripts | `scripts/` — **shared infra, coordinate before editing** |

## 4 Extension Points
1. **New agent** → subclass `base_agent.py`, add node/edge in `workflow.py`
2. **New MCP tool** → new handler in `tools/lambdas/`, register with Gateway
3. **New dashboard feature** → route in `api.py` + UI in `templates/index.html`
4. **New data/device type** → extend `DeviceLoader` + `HealthAgent` anomaly rules

## Local vs AgentCore Runtime
Same agent logic, two wrappers: local = `src/services/<agent>/app.py` (FastAPI/uvicorn, ports 8001/8002/8000); AWS = `handler.py` wrapped by `agentcore_entrypoint.py` + `BedrockAgentCoreApp` (port 8080, via `boto3`).

**Known issue:** `docker-compose.yml` points at the root AgentCore-only `Dockerfile.*` files (port 8080), not the per-service local `src/services/<agent>/Dockerfile` (port 8001/8002/8000) — `docker-compose up` will not work correctly as-is.

## Local Dev Loop (skip Docker, run directly)
```bash
python -m uvicorn src.services.health_agent.app:app --port 8001
python -m uvicorn src.services.diagnosis_agent.app:app --port 8002
python -m uvicorn src.services.orchestrator.app:app --port 8000  # localhost:8000/docs
cd src/dashboard && python app.py  # dashboard
python -m pytest tests/ -v         # tests
```
Build/test locally first. AWS/AgentCore deployment is shared and slow to iterate on.

## Gotchas
- `docker-compose up` is currently broken (see above) — run `app.py` services directly instead.
- Don't double-wrap sensor payload (`{"readings": {...}}`) — breaks anomaly detection silently.
- AgentCore Runtime images must be built `--platform linux/arm64`.
- Public API Gateway has **no auth** — demo-only, don't assume production-safe.
- Orchestrator action dispatch needs `session_id.ljust(33, '0')` — copy existing pattern.

## Tracks
1. New Agent (e.g. cost estimator, failure forecaster)
2. New MCP Tool (e.g. warranty lookup, technician roster)
3. Dashboard/UX (charts, exports, alerts)
4. Data & Prompt Tuning (new sensors/devices, confidence threshold tuning)

## Judging
Working demo · clean use of extension points (not core rewrites) · real maintenance-ops value
