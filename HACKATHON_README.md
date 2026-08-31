# Hackathon Guide

Welcome! This project is a working example of a multi-agent system (LangGraph +
AWS Bedrock AgentCore) built around equipment health monitoring. The event theme is
**Sustainability & Waste Reduction in Manufacturing Using Multi-Agent AI on AWS** — treat
this repo as a set of reusable building blocks and one worked reference example, not a
single graph everyone must extend the same way.

Read [README.md](README.md) to get it running, and [ARCHITECTURE.md](ARCHITECTURE.md) to
understand how the pieces fit together before you start changing things. If your team's
AWS environment (Cognito, Gateway, AgentCore Runtimes, dashboard) doesn't exist yet, that's
set up by a mentor following [TEAM_ONBOARDING_STEPS.md](TEAM_ONBOARDING_STEPS.md) — see
"Your team's AWS resources" below.

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
`.agentcore.env.team01.example` if you don't have one yet) — Docker Compose, the deploy
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

To connect the dashboard to this local orchestrator, run:
```bash
ORCHESTRATOR_URL=http://localhost:8000 python3 -m src.dashboard.app
```

This still talks to your team's own AWS resources (Gateway, Lambda tools, DynamoDB, S3,
Cognito, Bedrock) — see "Your team's AWS resources" below for what that means. What it
doesn't do is deploy anything to AWS Bedrock AgentCore Runtime (`deployment/agentcore-runtime/`)
— that's a separate, later step, covered in "Redeploying your agents after a code change"
below, for when you want your agent hosted there instead of run locally.

### Viewing logs (incl. LangGraph node execution)

```bash
docker-compose logs -f orchestrator      # follow logs for one service
docker-compose logs -f                   # follow logs for all services
```

`src/graph/workflow.py` logs every LangGraph node transition at INFO level — look for
`[NODE 1] HealthAgent`, `[NODE 2] Router`, `[NODE 3] DiagnosisAgent`, `[NODE 4] Aggregator`
in the `orchestrator` service's logs to see exactly which nodes ran (and which were
skipped) for a given request. `docker-compose.yml` already sets `LOG_LEVEL=INFO`, so no
extra configuration is needed.

## Your team's AWS resources — already deployed for you

Each team at this event is **fully isolated**: your own Cognito user pool, your own MCP
Gateway, your own Lambda/App Runner MCP tools, your own DynamoDB tables, and your own
AgentCore Runtimes — nothing is shared between teams. A mentor deploys all of this once
per team (following [TEAM_ONBOARDING_STEPS.md](TEAM_ONBOARDING_STEPS.md)) and hands your
team's branch off to you, so:
- The connection details you need (`gateway_info.<team_id>.json`,
  `agent_endpoints.<team_id>.json`, `api_gateway_endpoints.<team_id>.json`) are already
  committed on your team's branch — nothing to set up to read them.
- The two files that hold real secrets — `.env.<team_id>` and `.agentcore.env.<team_id>`
  (Cognito client secret, AWS account/profile) — are **not** committed; get them from your
  mentor through a secure channel and place them in the repo root yourself.
- The synthetic device data S3 bucket (`agentic-ai-poc-synthetic-data`) is the one thing
  that genuinely is shared/read-only across teams — no per-team copy needed there.

**Don't** re-run the Cognito/Gateway/DynamoDB setup steps yourself — ask a mentor if you
think your team's infrastructure is missing or broken. `TEAM_ONBOARDING_STEPS.md` is the
mentor-facing runbook for standing up a brand-new team from scratch, not something
participants normally need to run themselves.

## Redeploying your agents after a code change

Once your team's environment exists, redeploying just re-runs two scripts against your
team's env file — this is the same thing `TEAM_ONBOARDING_STEPS.md`'s step 9 does for
first-time setup:

```bash
export AWS_PROFILE=<your-profile>   # matches AWS_PROFILE in your .agentcore.env.<team_id>
./deployment/agentcore-runtime/build_and_push.sh --env-file .agentcore.env.<team_id>
python3 scripts/deploy_to_agentcore_boto3.py --env-file .agentcore.env.<team_id>
```

Both scripts create-if-missing/update-if-exists and refuse to run without a resolvable
`TEAM_ID` — safe to re-run any time, and this never touches another team's runtimes.

Only changed one agent? Redeploy just that one:
```bash
./deployment/agentcore-runtime/build_and_push.sh --env-file .agentcore.env.<team_id> health_agent
python3 scripts/deploy_to_agentcore_boto3.py --env-file .agentcore.env.<team_id> --agent health_agent
```

Check your runtimes are `READY` (deployment can take a minute after the script exits):
```bash
aws bedrock-agentcore-control list-agent-runtimes --region <your-team-region> \
  --query "agentRuntimes[?contains(agentRuntimeId, '<team_id>')].{Name:agentRuntimeId,Status:status,Updated:lastUpdatedAt}" \
  --output table
```

Then smoke-test (actually invokes the agent, not just a status check):
```bash
python3 scripts/invoke_agentcore_runtime.py orchestrator
```

Endpoint/runtime IDs are (re-)written to `agent_endpoints.<team_id>.json`. That file **is
committed** to your team's branch (it holds no secrets, just IDs/URLs) — commit the
update so your teammates see the same IDs.

### Connecting the dashboard to your team's deployment

Your team's dashboard (CloudFront + the FastAPI Lambda behind API Gateway) is deployed as
part of the onboarding runbook — see [TEAM_ONBOARDING_STEPS.md](TEAM_ONBOARDING_STEPS.md),
steps 9–10 (`deploy_to_agentcore_boto3.py` → `deploy_lambda_api_gateway_fastapi.py` →
`deploy_cloudfront.py`). Those scripts read your team's runtime IDs and env file
automatically — no manual editing of Lambda code is needed.

To point a **locally-run** dashboard at your team's deployed AgentCore Runtime instead of
a local Docker Compose orchestrator, set `ORCHESTRATOR_URL` to your team's API Gateway
stage root (the `domain`+stage from `api_gateway_endpoints.<team_id>.json`, no trailing path):
```bash
ORCHESTRATOR_URL=https://<your-api-id>.execute-api.<region>.amazonaws.com/prod python3 -m src.dashboard.app
```
Open `http://localhost:8080`.

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
| Full per-team AWS deployment runbook | [TEAM_ONBOARDING_STEPS.md](TEAM_ONBOARDING_STEPS.md) |
| Tests | `tests/` |

## Getting help

Ask your mentors before touching anything under `scripts/` that provisions your team's AWS
infrastructure (Cognito, DynamoDB, IAM, Gateway) — that's already set up for your team and
doesn't need to be re-run; flag it to a mentor if you think it's missing or broken.
