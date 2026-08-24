# Hackathon Guide

Welcome! This project is a working example of a multi-agent system (LangGraph +
AWS Bedrock AgentCore) built around equipment health monitoring. The event theme is
**Sustainability & Waste Reduction in Manufacturing Using Multi-Agent AI on AWS** — treat
this repo as a set of reusable building blocks and one worked reference example, not a
single graph everyone must extend the same way.

Read [README.md](README.md) to get it running, and [ARCHITECTURE.md](ARCHITECTURE.md) to
understand how the pieces fit together before you start changing things.

## How to run it (do this first)

Use **Docker Compose** for all normal development — it's faster to iterate on and doesn't
touch any cloud deployment:

```bash
docker-compose up -d --build
curl http://localhost:8000/health
python -m pytest tests/ -v
```

Deploying to AWS Bedrock AgentCore Runtime (`deployment/agentcore-runtime/`) is an
**optional stretch goal**, not part of the normal build loop.

## Important: shared AWS resources — don't recreate, don't collide

The AgentCore Gateway, MCP tools (Lambda + App Runner), Cognito, and DynamoDB tables are
**already deployed and shared by everyone** at the event — local Docker Compose runs hit
the exact same real AWS resources as everyone else's. There's no per-team or local/mock
copy of any of this. Practical implications:
- **Don't** try to redeploy the Gateway, Cognito pool, or DynamoDB tables — they exist.
- **Do** prefix any test device IDs you create with your team name/ID, so your test data
  doesn't collide with another team's in the shared tables.
- If you plan to actually deploy to AgentCore Runtime (stretch goal), ask first — runtime
  names aren't namespaced per team yet, so two teams deploying at once can overwrite each
  other's runtime.

## Adding a new agent

1. **Core logic** — create `src/agents/<your_agent>.py`, subclassing
   [`BaseAgent`](src/agents/base_agent.py) and implementing `async def execute(self, input_data)`.
   Keep it framework-agnostic: no HTTP, no AWS SDK calls here.
2. **Service wrapper** — create `src/services/<your_agent>/`:
   - `app.py` — a small FastAPI app exposing your agent for local/Docker Compose use
     (mirror `src/services/health_agent/app.py`).
   - `handler.py` — a self-contained `BedrockAgentCoreApp` entrypoint for AgentCore
     Runtime (mirror `src/services/health_agent/handler.py`) — no wrapper script needed,
     this file *is* the server.
   - `requirements.txt` — your agent's Python dependencies.
3. **Wire it into the graph** — add a node (and any routing) to
   [`src/graph/workflow.py`](src/graph/workflow.py) (local) and, if you also want it on
   AWS, [`src/graph/workflow_agentcore.py`](src/graph/workflow_agentcore.py).
4. **Docker Compose** — add a service block to `docker-compose.yml`, pointing at a new
   `deployment/docker-compose/<your_agent>.Dockerfile` (copy an existing one and change
   the port/module path).
5. **(Stretch) AgentCore Runtime** — add `deployment/agentcore-runtime/<your_agent>.Dockerfile`,
   build + push it to ECR, then extend `scripts/deploy_to_agentcore_boto3.py`'s agent config
   (it registers pre-built ECR images directly via boto3 — no separate config file needed).

That's it — no shared "lambda_handler" naming convention to work around, no generic entry
point script to understand. Each agent is self-contained and readable top to bottom.

## Suggested team tracks

- **New agent** — e.g. an energy-efficiency agent, a waste/scrap-rate agent.
- **New MCP tool** — a new Lambda behind the Gateway, or a local "mock tool" if you don't
  want to touch the shared Gateway mid-event.
- **New equipment type** — extend the synthetic data + thresholds for a new machine type.
- **Dashboard feature** — extend `src/dashboard/` (Jinja2 + FastAPI) with a new view.
- **AgentCore Runtime deployment** (advanced/stretch) — get your own agent running end to
  end on AgentCore Runtime, not just Docker Compose.

## Where things live

| What | Where |
|---|---|
| Agent business logic | `src/agents/` |
| LangGraph orchestration | `src/graph/` |
| Per-agent local + AgentCore entrypoints | `src/services/<agent>/` |
| MCP Gateway client | `src/gateway/client.py` |
| Dashboard | `src/dashboard/` |
| Docker Compose Dockerfiles | `deployment/docker-compose/` |
| AgentCore Runtime Dockerfiles + build script | `deployment/agentcore-runtime/` |
| Real Lambda tool implementations | `tools/lambdas/` |
| Deployment/setup scripts (Cognito, DynamoDB, S3, Gateway, IAM) | `scripts/` |
| Tests | `tests/` |

## Getting help

Ask your mentors before touching anything under `scripts/` that provisions shared AWS
infrastructure (Cognito, DynamoDB, IAM, Gateway) — those are already set up for the event
and don't need to be re-run.
