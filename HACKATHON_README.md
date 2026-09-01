# Hackathon Participant Guide

This project is a working multi-agent predictive-maintenance example using
LangGraph, AWS Bedrock AgentCore, Cognito, AgentCore Gateway, and MCP tools.

Participants work from their team's branch. A mentor/admin prepares the AWS
infrastructure first; the provisioning runbook is
[AWS_AGENTCORE_TEAM_ONBOARDING_STEPS.md](AWS_AGENTCORE_TEAM_ONBOARDING_STEPS.md).

## What You Need

- Python 3.10+
- Docker with the modern `docker compose` plugin
- AWS CLI with the event SSO profile
- Node.js/npm only if you change the React/CloudFront dashboard

## AWS Login

```bash
aws configure sso
aws sso login --profile <your-profile>
aws sts get-caller-identity --profile <your-profile> --region eu-central-1
```

Your mentor provides `.agentcore.env.<team_id>`. It contains real team settings and
secrets, so do not commit it.

## Run Local Agents

Docker Compose runs the agents locally, but they still call real AWS services:
Cognito, AgentCore Gateway, MCP Lambda/App Runner tools, DynamoDB, S3, and Nova Lite.

```bash
AGENT_ENV_FILE=.agentcore.env.<team_id> docker compose up -d --build
```

For this team02 branch:

```bash
AGENT_ENV_FILE=.agentcore.env.team02 docker compose up -d --build
```

Check the services:

```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
```

Swagger UI:

```text
http://localhost:8000/docs   Orchestrator
http://localhost:8001/docs   HealthAgent
http://localhost:8002/docs   DiagnosisAgent
```

Use the Orchestrator `GET /devices/{device_id}` endpoint to demo the full flow:
HealthAgent -> DiagnosisAgent -> AgentCore Gateway -> MCP tools.

## Run Local Dashboard

```bash
ORCHESTRATOR_URL=http://localhost:8000 python3 -m src.dashboard.app
```

Open:

```text
http://localhost:8080
```

## Hosted AgentCore Deployment

Participants should not rerun Cognito, Gateway, IAM, DynamoDB, S3, Lambda, or
CloudFront provisioning unless a mentor asks. Those steps live in
[AWS_AGENTCORE_TEAM_ONBOARDING_STEPS.md](AWS_AGENTCORE_TEAM_ONBOARDING_STEPS.md).

After changing agent code, redeploy the hosted AgentCore runtimes:

```bash
deployment/agentcore-runtime/build_and_push.sh --env-file .agentcore.env.<team_id>
python3 scripts/deploy_to_agentcore_boto3.py --env-file .agentcore.env.<team_id>
```

For one changed agent:

```bash
deployment/agentcore-runtime/build_and_push.sh --env-file .agentcore.env.<team_id> diagnosis_agent
python3 scripts/deploy_to_agentcore_boto3.py --env-file .agentcore.env.<team_id> --agent diagnosis_agent
```

Smoke-test a deployed runtime:

```bash
python3 scripts/invoke_agentcore_runtime.py orchestrator --team-id <team_id> --region eu-central-1 --profile <your-profile>
```

## LLM Verification

DiagnosisAgent calls Amazon Nova Lite when rule confidence is below `0.85`. In
Frankfurt this project uses the inference profile `eu.amazon.nova-lite-v1:0`. No
model deployment or API key is needed.

## Adding A New Agent

1. Add core logic in `src/agents/<agent_name>.py`, subclassing `BaseAgent`.
2. Add local FastAPI service code in `src/services/<agent_name>/app.py`.
3. Add AgentCore Runtime entrypoint code in `src/services/<agent_name>/handler.py`.
4. Add a Docker Compose Dockerfile under `deployment/docker-compose/`.
5. Add an AgentCore Dockerfile under `deployment/agentcore-runtime/`.
6. Wire the agent into `src/graph/workflow.py` and, if hosted, `src/graph/workflow_agentcore.py`.
7. Add the agent to `deployment/agentcore-runtime/build_and_push.sh`,
   `scripts/deploy_to_agentcore_boto3.py`, and `scripts/invoke_agentcore_runtime.py`.

## Adding A New MCP Tool

Coordinate new tool names with mentors first.

1. Add a backend: Lambda under `tools/lambdas/` or an HTTP service like
   `src/ecs_tasks/create_work_order/`.
2. Add or update a schema under `tools/schemas/`.
3. Deploy the backend for your team.
4. Register it on your team's AgentCore Gateway using `scripts/register_mcp_tools_starter.py`
   with your team's env file.
5. Call it from agent code through `src/gateway/client.py`.

Agents call stable logical names such as `get-spare-parts`; the team-specific Gateway
routes them to that team's actual Lambda/App Runner resources.

## Useful Locations

| What | Where |
|---|---|
| Agent logic | `src/agents/` |
| Local and AgentCore service entrypoints | `src/services/<agent>/` |
| LangGraph workflows | `src/graph/` |
| MCP Gateway client | `src/gateway/client.py` |
| Local Python dashboard | `src/dashboard/` |
| React dashboard | `frontend/` |
| Deployment scripts | `scripts/` |
| AWS provisioning runbook | [AWS_AGENTCORE_TEAM_ONBOARDING_STEPS.md](AWS_AGENTCORE_TEAM_ONBOARDING_STEPS.md) |

## Notes

- Prefer local Docker Compose when you want Swagger UI during a demo.
- Use the hosted dashboard for the deployed AWS/AgentCore end-to-end demo.
- Python test files exist, but they are not required for the standard hackathon demo path.
- If AWS SSO expires, run `aws sso login --profile <your-profile>` on the host.
