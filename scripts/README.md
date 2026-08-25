# scripts/ Reference

Purpose of every script in this folder, grouped by what part of the system they set up or deploy.

## One-time infra bootstrap (run once per AWS account)

| Script | Purpose |
|---|---|
| `main_setup.py` | Orchestrates initial setup — calls `iam_setup.py`, `cognito_setup.py`, `dynamodb_setup.py` in order. |
| `iam_setup.py` | Creates the shared IAM roles (e.g. `AgentCoreExecutionRole`) used by agents/Lambdas. |
| `cognito_setup.py` | Creates the Cognito user pool + app client used for API auth. |
| `dynamodb_setup.py` | Creates the core DynamoDB tables (sessions, etc.). |
| `config.py` | Shared config/env loader imported by the setup scripts above — not run directly. |

## MCP tools + Gateway (Lambdas, App Runner service, Gateway registration)

| Script | Purpose |
|---|---|
| `setup_s3_synthetic_data.py` | Uploads the synthetic device sensor data to S3 (used by `list_devices`/`get_device`). |
| `setup_s3_for_mcp_tools.py` | Creates the S3 bucket/prefix used by MCP tools for supporting data. |
| `setup_dynamodb_for_mcp_tools.py` | Creates the `maintenance_schedules` and `work_orders` DynamoDB tables. |
| `deploy_mcp_lambdas.py` | Deploys/updates the `get_spare_parts` and `schedule_maintenance` Lambda functions. |
| `create_apprunner_ecr_pull_role.py` | One-time: creates the IAM role App Runner uses to pull the `create_work_order` image from ECR. |
| `push_create_work_order_to_ecr.sh` | Builds and pushes the `create_work_order` FastAPI service (`src/ecs_tasks/create_work_order/app.py`) image to ECR. |
| `deploy_create_work_order_apprunner.sh` | Deploys that image as an App Runner service (this is the currently-used path — see `CREATE_WORK_ORDER_URL` in `.env.example`). |
| `create_agentcore_gateway_starter.py` | One-time: creates the shared AgentCore Gateway that all MCP tools are registered under. |
| `register_mcp_tools_starter.py` | Registers/updates Lambda + HTTP tools as targets on the shared Gateway. **This is the script to use** when adding a new tool. |
| `setup_cognito_token_flow.py` | Wires up the Cognito client-credentials flow the Gateway uses for machine-to-machine auth; documents the end-to-end setup order (Gateway → Lambdas → registration). |

## Dashboard backend (`/orchestrate` Lambda + API Gateway — separate from AgentCore Runtime)

| Script | Purpose |
|---|---|
| `deploy_lambda_api_gateway_boto3.py` | Deploys the orchestrator Lambda + API Gateway that the dashboard calls (`ORCHESTRATOR_URL` in `src/dashboard/config.py`). |
| `add_devices_api_routes.py` | Adds the `/orchestrate/devices*` routes onto that same API Gateway. |
| `test_device_endpoint.py` | Manual smoke test for the deployed device endpoints. |

## Cognito troubleshooting utilities (run manually as needed)

| Script | Purpose |
|---|---|
| `check_cognito_app_client_oauth.py` | Inspects a Cognito app client's OAuth config (callback/logout URLs, flows). |
| `fix_cognito_app_client_oauth.py` | Fixes a Cognito app client's OAuth config if it's misconfigured. |
| `list_cognito_pools_and_clients.py` | Lists all Cognito user pools/app clients in the account — useful when you don't know the pool ID. |

## AgentCore Runtime deployment (multi-agent, team-namespaced)

| Script | Purpose |
|---|---|
| `deploy_to_agentcore_boto3.py` | Builds/deploys an agent (health/diagnosis/orchestrator) as an AgentCore Runtime, namespaced by `TEAM_ID`. |
| `deploy_team_agents.sh` | Convenience wrapper: builds+pushes the image, then calls `deploy_to_agentcore_boto3.py`, for one team. |
| `invoke_agentcore_runtime.py` | Manually invoke a deployed AgentCore Runtime agent for testing. |

## Verification / testing

| Script | Purpose |
|---|---|
| `verify_branch.sh` | End-to-end sanity check of a branch — local Docker Compose, or `--agentcore` to also check the deployed runtimes. |
| `preflight_check.sh` | Quick checks for common setup mistakes (missing env vars, credentials, etc.) before running `verify_branch.sh`. |
| `run_e2e_tests.sh` | Runs the Docker Compose end-to-end test suite (`build`/`test`/`clean`/`logs`). |

## Removed (2026-08-25)

These were deleted as confirmed unused/superseded — kept here as a note in case anyone goes looking for them:
- `create_agentic_ai_roy_vpc.sh` + `deploy_create_work_order_ecs.sh` — an earlier ECS Fargate deployment path for `create_work_order`, superseded by the App Runner path above. Confirmed no ECS cluster ever existed in the account (`aws ecs list-clusters` returned empty) before deleting.
- `register_tools_with_agentcore.py` — an early draft of tool registration against a generic REST `/tools/register` endpoint, written before the real AgentCore Gateway API was integrated. Its required config file (`agentcore_tools_config.json`) never existed in the repo. Fully superseded by `register_mcp_tools_starter.py`.
