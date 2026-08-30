# Local Docker Compose Demo With Team01 Frankfurt MCP Services

Run the three agents locally while keeping Cognito, AgentCore Gateway, and MCP
backends in the team01 Frankfurt environment.

## Start Local Agents

Run from the repository root:

```bash
AGENT_ENV_FILE=.agentcore.env.team01 docker compose up -d --build
```

This starts the local FastAPI containers:

```text
Orchestrator:   http://localhost:8000
HealthAgent:    http://localhost:8001
DiagnosisAgent: http://localhost:8002
```

The selected team env file supplies the Frankfurt configuration to all
containers, including:

```text
AWS_REGION=eu-central-1
GATEWAY_URL=https://team01-mcp-gateway-xuuwo764wu.gateway.bedrock-agentcore.eu-central-1.amazonaws.com/mcp
COGNITO_APP_CLIENT_ID
COGNITO_APP_CLIENT_SECRET
COGNITO_TOKEN_ENDPOINT
COGNITO_SCOPE
```

Confirm container health:

```bash
AGENT_ENV_FILE=.agentcore.env.team01 docker compose ps

curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
```

## Local Swagger UI

```text
Orchestrator:   http://localhost:8000/docs
HealthAgent:    http://localhost:8001/docs
DiagnosisAgent: http://localhost:8002/docs
```

For the end-to-end demo flow, use the Orchestrator Swagger UI and call:

```text
GET /devices/{device_id}
```

A warning or critical device can exercise the local agents and the team01
Frankfurt Gateway/MCP path.

## Start Local Python Dashboard

In a second terminal from the repository root:

```bash
ORCHESTRATOR_URL="http://localhost:8000" python3 -m src.dashboard.app
```

Open:

```text
http://localhost:8080
```

## Stop Local Demo

```bash
AGENT_ENV_FILE=.agentcore.env.team01 docker compose down
```

This stops only local Docker Compose containers. It does not delete or change
Frankfurt AgentCore Runtimes, Cognito, Gateway, Lambda, App Runner, DynamoDB,
or S3 resources.

The host `~/.aws` directory is mounted read-only. Refresh the AWS SSO profile
on the host before starting containers if its session has expired.

## Image Separation

Docker Compose builds local images named by the Compose project, for example:

```text
agentic_ai_poc_phase3_1-orchestrator
agentic_ai_poc_phase3_1-health-agent
agentic_ai_poc_phase3_1-diagnosis-agent
```

AgentCore deployment builds separate ARM64 images and pushes them to Frankfurt
ECR with the `team01` tag, for example:

```text
450410489798.dkr.ecr.eu-central-1.amazonaws.com/orchestrator:team01
450410489798.dkr.ecr.eu-central-1.amazonaws.com/health-agent:team01
450410489798.dkr.ecr.eu-central-1.amazonaws.com/diagnosis-agent:team01
```

The local Compose build can reuse Docker cache layers, but it does not overwrite
or deploy the ECR images. Running or stopping local containers does not affect
the AgentCore Runtime containers.
