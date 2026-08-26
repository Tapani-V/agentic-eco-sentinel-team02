# Hackathon Guide

Welcome! This project is a working example of a multi-agent system (LangGraph +
AWS Bedrock AgentCore) built around equipment health monitoring. The event theme is
**Sustainability & Waste Reduction in Manufacturing Using Multi-Agent AI on AWS** — treat
this repo as a set of reusable building blocks and one worked reference example, not a
single graph everyone must extend the same way.

Read [README.md](README.md) to get it running, and [ARCHITECTURE.md](ARCHITECTURE.md) to
understand how the pieces fit together before you start changing things.

## Set up your Python environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

## Before you start: AWS access

Everything here calls real AWS resources under the hood, even Docker Compose — you need
a working AWS SSO profile first. Ask your mentors for this event's SSO start URL /
account / permission set, then:

```bash
aws configure sso   # follow the prompts; name the profile to match AWS_PROFILE below
aws sso login --profile <your-profile>
aws sts get-caller-identity --profile <your-profile>   # sanity check
```

Set that profile name as `AWS_PROFILE` in `.agentcore.env` (copy from
`.agentcore.env.example` if you don't have one yet) — Docker Compose, the deploy
scripts, and the tests all read credentials from `AWS_PROFILE`, never hardcoded keys.
SSO sessions expire after a few hours; re-run `aws sso login` if you start seeing
`ExpiredToken`/`UnauthorizedAccess` errors.

> **Known issue (Linux/WSL):** Docker Compose mounts your real `~/.aws` folder
> read-write into the containers so they can resolve the `AWS_PROFILE` SSO session.
> Because containers run as `root`, a background SSO token refresh from inside a
> container can leave a **root-owned** file under `~/.aws/sso/cache/`, which your
> host `aws` CLI then can't read. Symptoms: `aws sts get-caller-identity`, `aws ecr
> get-login-password`, or any AWS call on your host suddenly fails with a cryptic
> error referencing a cache file hash (e.g. `password is empty`, or the hash printed
> alone). If this happens: `ls -la ~/.aws/sso/cache/` to spot the file owned by
> `root` (not you), then remove just that file and re-authenticate:
> ```bash
> rm ~/.aws/sso/cache/<hash>.json   # the one owned by root, not your user
> aws sso login --profile <your-profile>
> ```
> This only clears a cached token — it's safe and doesn't affect any running
> containers or AWS resources.

## How to run it (do this first)

Use **Docker Compose** for day-to-day development — it's the fastest local loop for
iterating on agent code:

```bash
docker-compose up -d --build
curl http://localhost:8000/health
```

Docker Compose only installs dependencies **inside the containers** — anything you run
directly on your host, like the `tests/` suite below, needs the venv you set up above
(`source venv/bin/activate`):

```bash
python -m pytest tests/ -v
```

This still talks to the same real, shared AWS resources as everyone else (Gateway, Lambda
tools, DynamoDB, S3, Cognito, Bedrock) — see the next section for what's shared. What it
doesn't do is deploy anything to AWS Bedrock AgentCore Runtime (`deployment/agentcore-runtime/`)
— that's a separate, later step, covered in "Deploying to AgentCore Runtime" below, for when
you want your agent hosted there instead of run locally.

## Important: shared AWS resources — don't recreate, don't collide

The AgentCore Gateway, MCP tools (Lambda + App Runner), Cognito, and DynamoDB tables are
**already deployed and shared by everyone** at the event — local Docker Compose runs hit
the exact same real AWS resources as everyone else's. There's no per-team or local/mock
copy of any of this. Practical implications:
- **Don't** try to redeploy the Gateway, Cognito pool, or DynamoDB tables — they exist.
- The synthetic device data S3 bucket (`agentic-ai-poc-synthetic-data`) is also shared and
  read-only for agents — no per-team copy needed there either.

## Deploying to AgentCore Runtime — set TEAM_ID first

Unlike the resources above, **AgentCore Runtime deployments are namespaced per team** via
a `TEAM_ID` variable, so multiple teams can deploy/redeploy their own agents at the same
time without overwriting each other (or the original shared runtimes):

1. Set `TEAM_ID=yourteam` in `.agentcore.env` (copy `.agentcore.env.example` if you don't
   have one yet — everything else in it is the same shared config for everyone).
2. Build, push, and register/update all 3 agents:
   ```bash
   export AWS_PROFILE=<your-profile>
   ./scripts/deploy_team_agents.sh
   ```
   The `export` is required — `build_and_push.sh`'s `aws ecr` calls read the profile
   from the `AWS_PROFILE` environment variable (no `--profile` flag), so without it
   they fall back to no profile at all and fail.
   This creates/updates runtimes named `<agent>_runtime_<TEAM_ID>` from images tagged
   `:<TEAM_ID>` in ECR — it never touches the shared `<agent>_runtime` runtimes or
   `:latest` images.
3. Only changed one agent? Redeploy just that one:
   ```bash
   ./scripts/deploy_team_agents.sh health_agent
   ```
4. Check your runtimes are `READY` (deployment can take a minute after the script exits):
   ```bash
   aws bedrock-agentcore-control list-agent-runtimes --region us-east-1 \
     --query "agentRuntimes[?contains(agentRuntimeId, '<TEAM_ID>')].{Name:agentRuntimeId,Status:status,Updated:lastUpdatedAt}" \
     --output table
   ```
5. Smoke-test your deployment (actually invokes the agent, not just a status check):
   ```bash
   python3 scripts/invoke_agentcore_runtime.py orchestrator
   ```
6. Endpoints/runtime IDs are written to `agent_endpoints.<TEAM_ID>.json` (gitignored, not
   the shared tracked `agent_endpoints.json`).

Both `scripts/deploy_to_agentcore_boto3.py` and `deployment/agentcore-runtime/build_and_push.sh`
refuse to run if `TEAM_ID` isn't set — this is intentional so a forgotten `TEAM_ID` can never
silently overwrite the shared runtime.

## LLM verification tier

`DiagnosisAgent` falls back to an LLM (Amazon Bedrock, `amazon.nova-lite-v1:0`, see
[`src/llm/llm_client.py`](src/llm/llm_client.py)) to double-check its diagnosis whenever
rule-based confidence is below 0.85. It's a fully-managed AWS model — nothing to deploy,
no API key to set up, and no extra IAM work (the shared `AgentCoreExecutionRole` already
allows `bedrock:InvokeModel`). It just works locally (via your `AWS_PROFILE`) and once
deployed (via the execution role).

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
5. **AgentCore Runtime** — add `deployment/agentcore-runtime/<your_agent>.Dockerfile`,
   then update these three hardcoded lists (all three currently only know about
   `orchestrator`/`health_agent`/`diagnosis_agent`):
   - `deployment/agentcore-runtime/build_and_push.sh` — add `"your_agent:your-agent"` to
     the `IMAGES` array.
   - `scripts/deploy_to_agentcore_boto3.py` — add a `"your_agent": {...}` entry to the
     `agents_config` dict in `deploy_all()` (ecr image, cpu/memory/timeout), and add
     `'your_agent'` to the `--agent` argparse `choices=[...]`.
   - `scripts/invoke_agentcore_runtime.py` — add `"your_agent"` to the `choices=[...]` and
     a sample payload, so you can smoke-test it the same way as the others.
   Once those are updated, `./scripts/deploy_team_agents.sh your_agent` works automatically
   — it just forwards whatever agent name you pass to the two scripts above.

That's it — no shared "lambda_handler" naming convention to work around, no generic entry
point script to understand. Each agent is self-contained and readable top to bottom.

If your new agent needs a brand-new AWS IAM role (not just reusing the shared
`AgentCoreExecutionRole`), read [IAM_ROLE_CREATION_GUARDRAILS.md](IAM_ROLE_CREATION_GUARDRAILS.md)
first — this AWS account blocks the normal/console way of creating IAM roles.

## Adding a new MCP tool

A new tool needs a real backend plus a registration on the shared AgentCore Gateway so
agents can discover/call it via `GatewayClient`:

1. **Backend** — either:
   - A Lambda: add a handler under `tools/lambdas/` (mirror
     [`tools/lambdas/get_spare_parts_handler.py`](tools/lambdas/get_spare_parts_handler.py)),
     then deploy it with `scripts/deploy_mcp_lambdas.py`.
   - An HTTP service: mirror [`src/ecs_tasks/create_work_order/`](src/ecs_tasks/create_work_order/)
     (its own Dockerfile) and deploy to App Runner (use
     `scripts/deploy_create_work_order_apprunner.sh` as a template).
2. **Tool schema** — add a JSON input/output schema under `tools/schemas/` (mirror the
   3 existing files there).
3. **Register it on the Gateway** — add your tool's ARN/URL + schema to
   `scripts/register_mcp_tools_starter.py` (`register_lambda_tool` for Lambdas,
   `register_http_tool` for HTTP services), then re-run it:
   ```bash
   python3 scripts/register_mcp_tools_starter.py
   ```
   This only adds a target to the Gateway that **already exists** — don't re-run
   `create_agentcore_gateway_starter.py`, that creates the Gateway itself.
4. **Call it from agent code** via the existing client
   ([`src/gateway/client.py`](src/gateway/client.py)):
   ```python
   result = gateway_client.call_tool("your_tool_name", {"param": "value"})
   ```

The Gateway is shared by everyone at the event, so coordinate with mentors before
registering a new tool name, and test a new Lambda/App Runner backend on its own
(`aws lambda invoke` / `curl`) before wiring it into the Gateway.

## Suggested team tracks

- **New agent** — e.g. an energy-efficiency agent, a waste/scrap-rate agent.
- **New MCP tool** — a new Lambda behind the Gateway, or a local "mock tool" if you don't
  want to touch the shared Gateway mid-event.
- **New equipment type** — extend the synthetic data + thresholds for a new machine type.
- **Dashboard feature** — extend `src/dashboard/` (Jinja2 + FastAPI) with a new view.
- **AgentCore Runtime deployment** — get your own agent running end to end on AgentCore
  Runtime, not just Docker Compose.

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
| Deployment/setup scripts (Cognito, DynamoDB, S3, Gateway, IAM) | `scripts/` (see [scripts/README.md](scripts/README.md) for what each one does) |
| Tests | `tests/` |

## Getting help

Ask your mentors before touching anything under `scripts/` that provisions shared AWS
infrastructure (Cognito, DynamoDB, IAM, Gateway) — those are already set up for the event
and don't need to be re-run.
