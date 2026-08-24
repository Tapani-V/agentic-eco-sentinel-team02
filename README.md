# Agentic Eco-Sentinel

Multi-agent equipment health & diagnostics system built with **LangGraph**, deployable
either locally (Docker Compose) or on **AWS Bedrock AgentCore Runtime**.

Given a device's sensor reading, the system classifies its health, and — only if
something looks wrong — runs a deeper diagnosis that can call real tools (check spare
parts, schedule maintenance, create a work order).

See [ARCHITECTURE.md](ARCHITECTURE.md) for how it all fits together, and
[HACKATHON_README.md](HACKATHON_README.md) if you're here for the hackathon.

## Repository layout

```
src/
  agents/            Core agent logic (HealthAgent, DiagnosisAgent) - pure Python, no HTTP
  graph/             LangGraph orchestration (workflow.py = local, workflow_agentcore.py = AWS)
  services/          Per-agent service wrappers
    health_agent/    app.py (local FastAPI) + handler.py (AgentCore entrypoint)
    diagnosis_agent/ app.py (local FastAPI) + handler.py (AgentCore entrypoint)
    orchestrator/    app.py (local FastAPI) + handler.py (AgentCore entrypoint)
  gateway/           Client for calling MCP tools via the AgentCore Gateway
  dashboard/         Local Jinja2 + FastAPI monitoring dashboard
  data/, utils/      Device data loading helpers

deployment/
  docker-compose/    Dockerfiles used by docker-compose.yml (local dev)
  agentcore-runtime/ Dockerfiles + build/push script for AWS Bedrock AgentCore Runtime

tools/lambdas/                  Real AWS Lambda functions (MCP tool implementations)
scripts/                        Deployment, IAM, Cognito, DynamoDB, S3, Gateway setup scripts
tests/                          Integration/e2e test suite (pytest)
```

## Run locally (Docker Compose)

This is the recommended way to develop and test agent changes.

```bash
docker-compose up -d --build
curl http://localhost:8000/health
```

- Orchestrator: `http://localhost:8000`
- HealthAgent: `http://localhost:8001`
- DiagnosisAgent: `http://localhost:8002`

Local containers still call the **real, shared** AWS AgentCore Gateway (MCP tools),
Cognito, and DynamoDB — there is no local/mock version of these. They authenticate using
your host machine's AWS credentials (`~/.aws` is mounted read-only into each container)
and `.agentcore.env` (copy from `.agentcore.env.example` if you don't have one).

## Run on AWS Bedrock AgentCore Runtime

Each agent (`health-agent`, `diagnosis-agent`, `orchestrator`) is deployed as its own
AgentCore Runtime, built from `deployment/agentcore-runtime/<agent>.Dockerfile`.

```bash
./deployment/agentcore-runtime/build_and_push.sh          # build + push arm64 images to ECR
python3 scripts/deploy_to_agentcore_boto3.py --profile <your-profile>   # register/update runtimes
```

## Run the dashboard

```bash
cd src/dashboard
pip install -r requirements.txt
python app.py     # http://localhost:8080
```

## Tests

```bash
python -m pytest tests/ -v
```

## Verify this branch works

### 1. Local (Docker Compose) — do this first

```bash
docker-compose up -d --build
docker-compose ps                      # all 3 containers should be "healthy"
curl http://localhost:8000/health      # orchestrator
curl http://localhost:8001/health      # health-agent
curl http://localhost:8002/health      # diagnosis-agent
python -m pytest tests/ -v             # runs against the containers above
python tests/test_e2e_all_stories.py   # exercises all 4 story scenarios end to end
```
`test_e2e_all_stories.py`'s "Ambiguous"/"Emergency" stories route through DiagnosisAgent
and call the real MCP tools — a pass there confirms the Gateway/Cognito/DynamoDB path is
working, not just the two agents talking to each other.

### 2. AWS Bedrock AgentCore Runtime

```bash
./deployment/agentcore-runtime/build_and_push.sh
python3 scripts/deploy_to_agentcore_boto3.py --profile <your-profile>   # writes agent_endpoints.json

# Invoke each deployed runtime directly to confirm the container/entrypoint works:
python scripts/invoke_agentcore_runtime.py health_agent
python scripts/invoke_agentcore_runtime.py diagnosis_agent
python scripts/invoke_agentcore_runtime.py orchestrator
```
A `statusCode: 200` response with a populated `body` means that runtime's container
booted, `BedrockAgentCoreApp` served the request, and (for orchestrator/diagnosis_agent)
any nested `invoke_agent_runtime`/MCP tool calls succeeded. Check
`scripts/preflight_check.sh` if you hit a setup error before getting that far.

### 3. Dashboard

```bash
cd src/dashboard && python app.py   # http://localhost:8080
```
Requires the orchestrator to be reachable (local on :8000, or point it at deployed
AgentCore endpoints — see `src/dashboard/config.py`).

### What "working" means, component by component

| Component | How to check |
|---|---|
| HealthAgent logic | `curl localhost:8001/health` returns 200 (local) or `invoke_agentcore_runtime.py health_agent` returns `statusCode: 200` (AWS) |
| DiagnosisAgent logic + MCP tools | Same as above for `diagnosis_agent`; check the response's `tool_results`/`action_taken` fields are populated, not empty |
| LangGraph routing | `tests/test_e2e_all_stories.py`'s 4 stories — healthy devices should **not** show diagnosis fields, warning/critical ones should |
| AgentCore Gateway + Cognito | Any diagnosis call that reaches `get_spare_parts`/`schedule_maintenance`/`create_work_order` without an auth error |
| DynamoDB writes | After a `schedule_maintenance` call, check the `agentic-maintenance-schedule` table in the AWS console for a new item |
| Dashboard | Loads device list/health data from the orchestrator without errors in the browser console |
| Docker Compose wiring | `docker-compose ps` shows all 3 containers healthy, `docker-compose logs -f` shows no crash loops |
| AgentCore Runtime deployment | `agent_endpoints.json` has fresh runtime IDs after `deploy_to_agentcore_boto3.py`, and `invoke_agentcore_runtime.py` succeeds for all 3 agents |

Yes — you should run both the local Docker Compose checks and (at least once) the
AgentCore Runtime invocation checks before considering the branch verified, since they
exercise different code paths (`app.py` vs `handler.py`) that share business logic but not
transport code.


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
