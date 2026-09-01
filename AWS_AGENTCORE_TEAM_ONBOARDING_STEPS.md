# Team02 Frankfurt Deployment Runbook

Runbook for deploying and handing off the team02 Frankfurt environment:
Cognito → AgentCore Gateway → MCP tools → AgentCore Runtimes → dashboard.

## Model: fully isolated per team (Cognito + Gateway + Runtimes all per-team)

Team02 gets its own Cognito User Pool, AgentCore Gateway, MCP tool backends,
AgentCore Runtimes, dashboard Lambda/API Gateway, and CloudFront dashboard.
Synthetic sensor data remains shared by design.

## Assumptions

- Each team is handed its **own branch** (this one is for team02). Env files are
  still **team-specific by filename**, so the branch can safely keep the original
  reference config separate from this team's real deployment config:
  - `.env` / `.agentcore.env` (plain names) = the **original, non-team-specific
    reference config** — for this machine these are symlinks to
    `/home/skroy/agentic_ai_poc_project_env_files/`. Never edited by any
    team-specific run; always available to re-run the original setup.
  - `.env.<team_id>` / `.agentcore.env.<team_id>` (e.g. `.env.team02`,
    `.agentcore.env.team02`) = **real, gitignored, team-specific files**,
    one pair per team. Seed each from `.env.team02.example` /
    `.agentcore.env.team02.example` and fill in that team's values.
- Every script below now accepts a `--env-file` flag (default: the original
  plain filename, for backward compatibility). **Always pass `--env-file
  .agentcore.env.<team_id>` (or `.env.<team_id>` for `cognito_setup.py`) when
  doing team-specific work** — omitting it silently falls back to the
  original file (see "Known gaps" for what happens if you forget).
- AgentCore Memory is **not** part of this setup — skipped entirely (no
  `deploy_agentcore_memory.py` step, no `AGENTCORE_MEMORY_ID`).
- `TEAM_ID` (e.g. `team02`) namespaces AgentCore Runtimes, the Lambda, IAM
  roles, and API Gateway. Under the fully-isolated model it also indirectly
  drives a separate Cognito pool + Gateway per team (via separate env files),
  not just the runtimes.

## IAM role reference

Participants normally do **not** create IAM roles for the standard demo. The
admin/onboarding scripts either reuse shared account-wide roles or create the
team-scoped roles with the required GroupIT permission boundary.

| Role | Used by | Scope |
|---|---|---|
| `AgentCoreExecutionRole` | HealthAgent, DiagnosisAgent, and Orchestrator AgentCore Runtimes | Shared account-wide |
| `AgentCoreGatewayExecutionRole` | AgentCore Gateway when invoking registered MCP targets | Shared account-wide |
| `apprunner-ecr-pull-role` | App Runner when pulling the `create-work-order` image from ECR | Shared account-wide |
| `<team_id>-mcp-tools-lambda-role` | `<team_id>-get-spare-parts` and `<team_id>-schedule-maintenance` Lambdas | Per team |
| `<team_id>-lambda-execution-role` | `<team_id>-orchestrator-handler` dashboard/API Lambda | Per team |

For team02, the per-team roles are:

```text
team02-mcp-tools-lambda-role
team02-lambda-execution-role
```

Any new role created in this account must include the GroupIT permission boundary:

```text
arn:aws:iam::450410489798:policy/GroupIT_ProjectPermissionBoundary
```

If participants need a new role for custom AWS extensions, route that request through
the admin so the role is created with the correct boundary and least-privilege policy.

## Which env file does each step read?

| Step(s) | Env file | Why |
|---|---|---|
| 1 (`cognito_setup.py`) | `.env.<team_id>` | Uses the `Config(env_file=...)` loader (separate from the `.agentcore.env` convention used by every other script) |
| 2, 3, 6, 8, 9 (`setup_cognito_token_flow.py`, `create_agentcore_gateway_starter.py`, `deploy_mcp_lambdas.py`, `register_mcp_tools_starter.py`, `build_and_push.sh`, `deploy_to_agentcore_boto3.py`) | `.agentcore.env.<team_id>` | Stores the team-specific Cognito, Gateway, MCP Lambda, and Runtime values; steps 1, 2, 3, and 6 write their generated values automatically |
| 4 (MCP tools S3) | none (CLI flags: `--bucket-name`/`--region`/`--profile`) | Not env-file driven; uses its explicit AWS CLI profile |
| 7 (App Runner) | `.agentcore.env.<team_id>` via `--env-file` | Waits for the generated service URL and automatically saves it as `CREATE_WORK_ORDER_URL` before step 8 |
| 5 (`setup_dynamodb_for_mcp_tools.py`) | `.agentcore.env.<team_id>` | Reads `TEAM_ID`, `AWS_REGION`, and `AWS_PROFILE`, with CLI flags available as explicit overrides |
| 10 (`deploy_lambda_api_gateway_fastapi.py`, `deploy_cloudfront.py`) | none (CLI args / shell env vars only) | Reads the `agent_endpoints.<team_id>.json` output from step 9 |

## Team02 Frankfurt runbook

Run these commands from the repository root, in order. They use the fixed team02
values: region `eu-central-1`, profile `StandardAccess-450410489798`, and account
`450410489798`. The env files are gitignored because they contain the Cognito client
secret; never commit them.

### 0. Confirm the AWS account

```bash
aws sts get-caller-identity --profile StandardAccess-450410489798 --region eu-central-1
```

The returned account must be `450410489798`.

### 1. Create Cognito User Pool

Before running this step, `.env.team02` must have a non-empty
`COGNITO_TEST_USER_PASSWORD`. This is only needed by the admin/person running the
initial deployment; hackathon participants do not need to set it after the branch is
handed off with Cognito already deployed. If the value is blank, set any temporary
test-user password that satisfies Cognito's policy: at least 8 characters, one
uppercase letter, one lowercase letter, and one number.

```bash
python3 scripts/cognito_setup.py --env-file .env.team02
```

Creates `team02-user-pool` and automatically saves `COGNITO_USER_POOL_ID` to
`.agentcore.env.team02`. This step may also create a public test client named
`team02-public-client`; the confidential machine-to-machine client is created in
step 2 with the separate name `team02-confidential-client`.

### 2. Configure Cognito client-credentials OAuth

```bash
python3 scripts/setup_cognito_token_flow.py --env-file .agentcore.env.team02
```

Creates the `agentcore/invoke` scope, `team02-auth` domain, and
`team02-confidential-client`; automatically saves the client ID, client secret, token
endpoint, and scope to `.agentcore.env.team02`.

### 3. Create the team02 AgentCore Gateway

```bash
python3 scripts/create_agentcore_gateway_starter.py --env-file .agentcore.env.team02
```

Creates `team02-mcp-gateway`, writes `gateway_info.team02.json`, and automatically
saves `GATEWAY_URL`, `AGENTCORE_GATEWAY_ID`, and `AGENTCORE_GATEWAY_ROLE_ARN` to
`.agentcore.env.team02`.

### 4. Upload the spare-parts inventory

```bash
python3 scripts/setup_s3_for_mcp_tools.py \
  --bucket-name team02-mcp-tools \
  --data-dir data/mcp-tools \
  --region eu-central-1 \
  --profile StandardAccess-450410489798
```

Uploads `data/mcp-tools/spare_parts_inventory.json` to
`s3://team02-mcp-tools/data/spare_parts_inventory.json`.

### 5. Create MCP tool DynamoDB tables

```bash
python3 scripts/setup_dynamodb_for_mcp_tools.py --env-file .agentcore.env.team02
```

Creates `team02-maintenance-schedules` and `team02-work-orders`.

### 6. Deploy Lambda-backed MCP tools

```bash
python3 scripts/deploy_mcp_lambdas.py --env-file .agentcore.env.team02
```

Creates `team02-get-spare-parts` and `team02-schedule-maintenance`, tests them, and
automatically saves both Lambda ARNs to `.agentcore.env.team02`.

### 7. Deploy the create-work-order App Runner service

> ⚠️ **Read before running:** `push_create_work_order_to_ecr.sh` pushes to a
> shared ECR repo (`create-work-order`) but tags the image per team
> (`:<team_id>`, derived from `--env-file`), so no team can accidentally
> overwrite another team's image (same convention as
> `deployment/agentcore-runtime/build_and_push.sh`). The ECR repo itself
> doesn't need to be created beforehand — the script creates it automatically
> if it doesn't exist yet. The `docker build` command is identical for every
> team (it's just a local tag); the push and App Runner commands below use
> team02's ECR tag and service name.

```bash
docker build -t create-work-order:latest src/ecs_tasks/create_work_order/
```

**team02** (the shared ECR repository uses this team's `:team02` image tag):

```bash
bash scripts/push_create_work_order_to_ecr.sh \
  --env-file .agentcore.env.team02 \
  --region eu-central-1 \
  --profile StandardAccess-450410489798

bash scripts/deploy_create_work_order_apprunner.sh \
  --region eu-central-1 \
  --service-name team02-create-work-order-apprunner \
  --env-file .agentcore.env.team02 \
  450410489798.dkr.ecr.eu-central-1.amazonaws.com/create-work-order:team02 \
  arn:aws:iam::450410489798:role/apprunner-ecr-pull-role \
  StandardAccess-450410489798
```

The script waits for the service to become `RUNNING` and automatically saves its
generated URL as `CREATE_WORK_ORDER_URL=https://<ServiceUrl>/work_order` in
the selected env file.

### 8. Register all MCP tools

```bash
python3 scripts/register_mcp_tools_starter.py --env-file .agentcore.env.team02
```

Registers `get-spare-parts`, `schedule-maintenance`, and `create-work-order` on
`team02-mcp-gateway`. The script reads the team-specific
`gateway_info.team02.json` file written by step 3.

### 9. Deploy AgentCore Runtimes

```bash
deployment/agentcore-runtime/build_and_push.sh --env-file .agentcore.env.team02

python3 scripts/deploy_to_agentcore_boto3.py \
  --env-file .agentcore.env.team02
```

Builds and deploys the health, diagnosis, and orchestrator AgentCore Runtimes, then
writes `agent_endpoints.team02.json`. The script reads `TEAM_ID`, `AWS_REGION`, and
`AWS_PROFILE` from the selected env file; `--team-id`, `--region`, and `--profile`
remain available as explicit overrides.

### 10. Deploy dashboard Lambda, API Gateway, and CloudFront

CloudFront deployment builds the React dashboard before uploading it to S3, so the
machine running this step must have Node.js and npm available:

```bash
node --version
npm --version
```

If either command is missing on Ubuntu/Linux, install Node.js first:

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
```

```bash
python3 scripts/deploy_lambda_api_gateway_fastapi.py \
  --team-id team02 \
  --region eu-central-1 \
  --profile StandardAccess-450410489798
```

Use the `domain` in `api_gateway_endpoints.team02.json` in the final CloudFront
deployment command. For the current team02 deployment, that value is
`cs6nmu2qjc.execute-api.eu-central-1.amazonaws.com`:

```bash
RESOURCE_PREFIX="team02-" \
API_GATEWAY_DOMAIN="cs6nmu2qjc.execute-api.eu-central-1.amazonaws.com" \
API_GATEWAY_STAGE_PATH="/prod" \
AWS_REGION="eu-central-1" \
AWS_PROFILE="StandardAccess-450410489798" \
python3 scripts/deploy_cloudfront.py
```

The current team02 CloudFront dashboard URL is:

```text
https://d107b5iy48yfw5.cloudfront.net
```

## Known gaps / not yet automated

- ~~`gateway_info.json` is not yet team-specific~~ **Fixed 2026-08-30:**
  `create_agentcore_gateway_starter.py` now derives `GATEWAY_NAME` from
  `TEAM_ID` (e.g. `team02-mcp-gateway`) and writes `gateway_info.<team_id>.json`
  instead of the shared `gateway_info.json` whenever `TEAM_ID` is set (falls
  back to the original shared name/file when `TEAM_ID` is unset).
  `register_mcp_tools_starter.py` reads the matching per-team file the same way.
- **Distribution model (decided 2026-08-30):** teams don't run the initial
  Cognito/Gateway/MCP-tools setup themselves — an admin deploys those on that
  team's own branch first, then hands the branch off; the team builds
  further agents/tools on top. So the JSON output files
  (`gateway_info.<team_id>.json`, `agent_endpoints.<team_id>.json`,
  `api_gateway_endpoints.<team_id>.json`) are **intentionally tracked/committed**
  (removed from `.gitignore`) — they contain no secrets (just resource
  IDs/URLs), so committing them on the team's branch means the team
  automatically has the already-deployed connection details the moment they
  check out that branch, no separate handoff needed. The env files
  (`.env.<team_id>`, `.agentcore.env.<team_id>`) still contain real secrets
  (`COGNITO_APP_CLIENT_SECRET`, AWS account/profile info) and **stay
  gitignored** — hand those off via a secure side channel, never commit them,
  even on a team-only branch (secrets in git history persist even after
  rotation/deletion).
- ~~`deploy_mcp_lambdas.py`/`setup_dynamodb_for_mcp_tools.py` hardcoded `team01-*`~~
  **Fixed 2026-08-30:** both scripts now derive every resource name
  (Lambda functions, IAM role/policy, DynamoDB tables, S3 bucket ARN) from
  `TEAM_ID`/`--team-id` instead of a literal `"team01"` string. They are
  documented as steps 5 and 6 of the Team02 Frankfurt runbook.
- ~~DynamoDB table `<team_id>-conversation-memory`~~ **Removed 2026-08-31:**
  this table was dead infrastructure — no agent code ever read or wrote it.
  Its setup script (`scripts/dynamodb_setup.py`), config entries, and IAM
  policy grants (in `iam_setup.py` and `deploy_lambda_api_gateway_fastapi.py`)
  have all been deleted, so nothing needs to be created for it. (This was
  always separate from the `<team_id>-maintenance-schedules`/
  `<team_id>-work-orders` tables, which step 5 still creates.)
- **S3 bucket** `<team_id>-synthetic-data` (referenced by step 7's IAM
  policy) is not created by any script verified this session — check
  `scripts/setup_s3_synthetic_data.py` or create manually before step 7.
- ~~Step 1 prints but does not persist `user_pool_id`~~ **Fixed 2026-08-30:**
  `cognito_setup.py` now automatically merges `COGNITO_USER_POOL_ID` into the
  paired `.agentcore.env.<team_id>` file (targeted line-replace via the same
  `merge_env_values()` helper `setup_cognito_token_flow.py` uses) — no manual
  copy step needed.
- If `--env-file` is omitted by mistake, scripts fall back to the original
  plain `.env`/`.agentcore.env`. On this machine that's a symlink to the
  shared reference config, so `setup_cognito_token_flow.py` (which *writes*
  Cognito values into its `--env-file`) is the highest-risk script to run
  without the flag — it would silently corrupt the shared original file. The
  other scripts either have explicit guards (`TEAM_ID` check) or fail with a
  clear error (`ValueError`/`FileNotFoundError`/boto3 validation error) since
  required values are missing.

