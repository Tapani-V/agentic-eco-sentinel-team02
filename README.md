# Agentic Eco-Sentinel

Multi-agent equipment health & diagnostics system built with **LangGraph**, deployable
either locally (Docker Compose) or on **AWS Bedrock AgentCore Runtime**.

Given a device's sensor reading, the system classifies its health, and — only if
something looks wrong — runs a deeper diagnosis that can call real tools (check spare
parts, schedule maintenance, create a work order).

Start with the document that matches your goal:

- [HACKATHON_README.md](HACKATHON_README.md): participant setup and demo steps.
- [AWS_AGENTCORE_TEAM_ONBOARDING_STEPS.md](AWS_AGENTCORE_TEAM_ONBOARDING_STEPS.md): mentor/admin AWS provisioning runbook.
- [ARCHITECTURE.md](ARCHITECTURE.md): agent and deployment architecture.

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

functions/                       Lambda handler(s) behind the dashboard's API Gateway
infra/                           CloudFormation template for the CloudFront + S3 dashboard stack
frontend/                        React dashboard, built and deployed to S3/CloudFront per team
tools/lambdas/                   Real AWS Lambda functions (MCP tool implementations)
scripts/                         Deployment, IAM, Cognito, DynamoDB, S3, Gateway setup scripts
tests/                           Integration/e2e test suite (pytest)
```

## Quick Start

For the standard participant workflow, follow [HACKATHON_README.md](HACKATHON_README.md).
In brief, authenticate with AWS SSO, start the local agents with the team environment,
and use the local Python dashboard:

```bash
aws configure sso  # name the local profile StandardAccess-450410489798
aws sso login --profile StandardAccess-450410489798
AGENT_ENV_FILE=.agentcore.env.<team_id> docker compose up -d
ORCHESTRATOR_URL=http://localhost:8000 python3 -m src.dashboard.app
```

The containers read your host AWS SSO credentials through a read-only mount. If an AWS
call fails with a read-only SSO cache error, refresh the SSO session on the host and
restart the containers:

```bash
aws sso login --profile <your-profile>
docker compose restart
```

The local dashboard is available at `http://localhost:8080`. It is intended to work
with the local Docker Compose agents only.

For a hosted team demo, use that team's CloudFront React dashboard. Team02's current
dashboard is `https://d107b5iy48yfw5.cloudfront.net`.

## Development and Deployment

- Agent code changes: run locally with Docker Compose first.
- Hosted AgentCore redeployment: follow the commands in
  [HACKATHON_README.md](HACKATHON_README.md).
- New team infrastructure: use the mentor/admin
  [AWS_AGENTCORE_TEAM_ONBOARDING_STEPS.md](AWS_AGENTCORE_TEAM_ONBOARDING_STEPS.md).

Automated tests are available under `tests/`, but they are optional and not required
for the standard hackathon participant workflow.

