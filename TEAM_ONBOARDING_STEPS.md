# New Team Onboarding — Deployment Script Order

Reference checklist for standing up a new team's environment (Cognito → MCP
Gateway → AgentCore Runtimes → Lambda/API Gateway → CloudFront dashboard).
Verified against the live team01/Frankfurt (`eu-central-1`) setup on 2026-08-28,
updated 2026-08-30 for the team-specific env-file model.

## Model: fully isolated per team (Cognito + Gateway + Runtimes all per-team)

We're deliberately **not** reusing the shared original Cognito pool/Gateway
per team — each team gets its own Cognito User Pool, its own MCP Gateway, and
its own AgentCore Runtimes, fully isolated from every other team and from the
original North Virginia reference setup.

## Assumptions

- All teams can be deployed from **the same repo checkout** (this repo/branch),
  because env files are now **team-specific by filename**, not shared:
  - `.env` / `.agentcore.env` (plain names) = the **original, non-team-specific
    reference config** — for this machine these are symlinks to
    `/home/skroy/agentic_ai_poc_project_env_files/`. Never edited by any
    team-specific run; always available to re-run the original setup.
  - `.env.<team_id>` / `.agentcore.env.<team_id>` (e.g. `.env.team01`,
    `.agentcore.env.team01`) = **real, gitignored, team-specific files**,
    one pair per team. Seed each from `.env.example` / `.agentcore.env.example`
    and fill in that team's values.
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

## Which env file does each step read?

| Step(s) | Env file | Why |
|---|---|---|
| 1 (`cognito_setup.py`) | `.env.<team_id>` | Uses the `Config(env_file=...)` loader (separate from the `.agentcore.env` convention used by every other script) |
| 2–6 (`setup_cognito_token_flow.py`, `create_agentcore_gateway_starter.py`, `register_mcp_tools_starter.py`, `build_and_push.sh`, `deploy_to_agentcore_boto3.py`) | `.agentcore.env.<team_id>` | All read/write Cognito, Gateway, and Runtime values via this file; step 1 auto-persists `COGNITO_USER_POOL_ID` into it so step 2 onward never needs manual copying |
| 3a/3b (work-order App Runner scripts) | none (CLI flags only: `--region`/`--profile`/`--service-name`) | Not env-file driven — pass `--region`/`--profile` explicitly |
| 3c (`setup_dynamodb_for_mcp_tools.py`) | none (CLI flag: `--team-id`, falls back to `$TEAM_ID`) | Not env-file driven — pass `--team-id`/`--region` explicitly |
| 3d (`deploy_mcp_lambdas.py`) | `.agentcore.env.<team_id>` | Reads `TEAM_ID`, `AWS_REGION`, `AWS_PROFILE`, `AWS_ACCOUNT_ID`, `PERMISSION_BOUNDARY` to build every resource name/ARN it creates |
| 7–8 (`deploy_lambda_api_gateway_fastapi.py`, `deploy_cloudfront.py`) | none (CLI args / shell env vars only) | Read prior steps' JSON output files instead |

## Script order

| # | Command | Purpose | Reads | Produces / manual follow-up |
|---|---|---|---|---|
| 1 | `python scripts/cognito_setup.py --env-file .env.<team_id>` | Create this team's own Cognito User Pool | `.env.<team_id>`: `COGNITO_USER_POOL_NAME`, `AWS_REGION`, etc. (via `Config(env_file=...)`) | Automatically persists `COGNITO_USER_POOL_ID` into `.agentcore.env.<team_id>` (derived from `--env-file`, or override with `--agentcore-env-file`) — no manual copy step needed. |
| 2 | `python scripts/setup_cognito_token_flow.py --env-file .agentcore.env.<team_id>` | Create resource server (`agentcore/invoke` scope) + hosted domain + confidential app client | `.agentcore.env.<team_id>`: `AWS_REGION`, `AWS_PROFILE`, `COGNITO_USER_POOL_ID` (auto-persisted by step 1), `COGNITO_DOMAIN_PREFIX`, `COGNITO_CLIENT_NAME` (all pre-filled during Phase B env prep, so no CLI flags are required — `--region`/`--user-pool-id`/`--domain-prefix`/`--client-name` remain available as one-off overrides if you need to deviate from the env file) | Merges `COGNITO_APP_CLIENT_ID`, `COGNITO_APP_CLIENT_SECRET`, `COGNITO_TOKEN_ENDPOINT`, `COGNITO_SCOPE`, `COGNITO_DOMAIN_PREFIX` directly into `.agentcore.env.<team_id>` (targeted line-replace, doesn't touch other keys) |
| 3 | `python scripts/create_agentcore_gateway_starter.py --env-file .agentcore.env.<team_id>` | Create this team's own MCP Gateway, authorized for the new client | `.agentcore.env.<team_id>`: `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID`, `AWS_REGION`, `AWS_PROFILE`, `PERMISSION_BOUNDARY`, `AWS_ACCOUNT_ID`, `TEAM_ID` | Writes `gateway_info.<team_id>.json` (team-specific since 2026-08-30 — `GATEWAY_NAME` derives from `TEAM_ID`); prints `GATEWAY_URL` — **manual step:** add `GATEWAY_URL=<value>` to `.agentcore.env.<team_id>` |
| 3a | `docker build -t create-work-order:latest src/ecs_tasks/create_work_order/` then `bash scripts/push_create_work_order_to_ecr.sh --region <region> --profile <profile>` | Push the `create-work-order` FastAPI image to an ECR repo **in the new team's region** (a private ECR image must be in the same region as the App Runner service pulling it — can't reuse the `us-east-1` repo cross-region) | Local Docker image `create-work-order:latest` | Creates/uses ECR repo `create-work-order` in `<region>`, pushes `:latest` |
| 3b | `bash scripts/deploy_create_work_order_apprunner.sh --region <region> --service-name <team>-create-work-order-apprunner <ECR_IMAGE_URL> <ECR_PULL_ROLE_ARN> <profile>` | Deploy that image as an App Runner service in `<region>` | Step 3a's ECR image URL; the existing `apprunner-ecr-pull-role` ARN (IAM roles are account-wide — **reuse it, do not re-run `create_apprunner_ecr_pull_role.py`**) | **Manual step:** poll `aws apprunner describe-service --service-arn <arn> --region <region>` until `Status` is `RUNNING`, then add `CREATE_WORK_ORDER_URL=https://<ServiceUrl>` to `.agentcore.env.<team_id>` |
| 3c | `python scripts/setup_dynamodb_for_mcp_tools.py --team-id <team> --region <region>` | Create this team's own `<team>-maintenance-schedules` and `<team>-work-orders` DynamoDB tables (fully isolated model — since 2026-08-30, generalized from the old hardcoded `team01-*` names via `--team-id`) | Nothing (pure AWS API calls) | Two tables in `<region>`; safe to re-run (skips creation if the table already exists) |
| 3d | `python scripts/deploy_mcp_lambdas.py --env-file .agentcore.env.<team_id>` | Deploy this team's own `<team>-get-spare-parts` and `<team>-schedule-maintenance` Lambda functions + `<team>-mcp-tools-lambda-role` IAM role (fully isolated model — since 2026-08-30, generalized from the old hardcoded `team01-*` names via `TEAM_ID`) | `.agentcore.env.<team_id>`: `TEAM_ID`, `AWS_REGION`, `AWS_PROFILE`, `AWS_ACCOUNT_ID`, `PERMISSION_BOUNDARY`; packages code from `tools/lambdas/get_spare_parts_handler.py` / `schedule_maintenance_handler.py` | Creates/updates the 2 Lambda functions, tests each with a sample invocation. **Manual step:** copy the printed Lambda ARNs into `.agentcore.env.<team_id>` as `GET_SPARE_PARTS_LAMBDA_ARN` / `SCHEDULE_MAINTENANCE_LAMBDA_ARN` (replacing the old cross-region `us-east-1` placeholder values) |
| 4 | `python scripts/register_mcp_tools_starter.py --env-file .agentcore.env.<team_id>` | Register the 3 MCP tool targets: `get-spare-parts`, `schedule-maintenance`, `create-work-order` | `.agentcore.env.<team_id>`: `GET_SPARE_PARTS_LAMBDA_ARN`, `SCHEDULE_MAINTENANCE_LAMBDA_ARN` (now this team's own Lambdas from step 3d, same region), `CREATE_WORK_ORDER_URL`, `TEAM_ID`; also reads `gateway_info.<team_id>.json` (step 3 output) | All 3 MCP tools are now deployed per-team, per-region (steps 3a/3b for `create-work-order`, steps 3c/3d for the other two) — no more cross-region shared-infra assumption |
| 5 | `deployment/agentcore-runtime/build_and_push.sh --env-file .agentcore.env.<team_id> [agent-name]` | Build ARM64 Docker images, push to ECR tagged `:<team_id>` | `.agentcore.env.<team_id>`: `TEAM_ID`, `AWS_ACCOUNT_ID`, `AWS_REGION` | Pushes images to ECR — skip if reusing unchanged images |
| 6 | `python scripts/deploy_to_agentcore_boto3.py --team-id <team> --region <region> --env-file .agentcore.env.<team_id>` | Deploy/update the 3 AgentCore Runtimes (health_agent, diagnosis_agent, orchestrator) | `.agentcore.env.<team_id>`: `TEAM_ID`, `COGNITO_APP_CLIENT_ID/SECRET`, `COGNITO_TOKEN_ENDPOINT`, `COGNITO_SCOPE`, `GATEWAY_URL` | Writes `agent_endpoints.<team_id>.json` (runtime IDs) — already team-specific and gitignored |
| 7 | `python scripts/deploy_lambda_api_gateway_fastapi.py --team-id <team> --region <region>` *(new script, added 2026-08-28)* | Deploy the FastAPI+Mangum orchestrator Lambda + REST API Gateway | `agent_endpoints.<team_id>.json` (step 6 output); creates its own IAM role `<team>-lambda-execution-role` | Writes `api_gateway_endpoints.<team_id>.json` (`domain`, `stage`, `invoke_url`) |
| 8 | `RESOURCE_PREFIX="<team>-" API_GATEWAY_DOMAIN="<domain from step 7>" API_GATEWAY_STAGE_PATH="/prod" python scripts/deploy_cloudfront.py` | Deploy CloudFront + S3 + React dashboard | Env vars only (no file) | Prints the CloudFront dashboard URL. **Must run after step 7** — API Gateway's domain is a fixed CloudFormation parameter baked in at stack-create time |

## Known gaps / not yet automated

- ~~`gateway_info.json` is not yet team-specific~~ **Fixed 2026-08-30:**
  `create_agentcore_gateway_starter.py` now derives `GATEWAY_NAME` from
  `TEAM_ID` (e.g. `team01-mcp-gateway`) and writes `gateway_info.<team_id>.json`
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
  `TEAM_ID`/`--team-id` instead of a literal `"team01"` string, and are now
  wired into the script order as steps 3c/3d, ahead of step 4's Gateway
  registration.
- **DynamoDB table** `<team_id>-conversation-memory` and **S3 bucket**
  `<team_id>-synthetic-data` (referenced by step 7's IAM policy) are not
  created by any script verified this session — check
  `scripts/dynamodb_setup.py` / `scripts/setup_s3_synthetic_data.py` or create
  manually before step 7. (Note: this is separate from the
  `<team_id>-maintenance-schedules`/`<team_id>-work-orders` tables, which
  step 3c now creates.)
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

