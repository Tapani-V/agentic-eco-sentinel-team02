# Phase 1 Week 2 Implementation Checklist

**Architecture:** Deploy Lambda/ECS tools to AWS with S3 data. Agents stay local reading local files.

---

## Pre-Week 2: What's Already Done ✅

- ✅ Equipment simulator script (`src/data/equipment_simulator.py`)
- ✅ Inventory data generator script (`src/data/inventory_data_generator.py`)
- ✅ AGENT_UPGRADE_GUIDE.md with complete agent patterns
- ✅ DiagnosisAgent enhanced with spare parts checking

---

## Week 2 Day 1-4: What You Need to Do

### Phase 1a: Generate & Upload Data (Day 1 - ~20 minutes)

- [ ] **Generate device sensor data locally**
  ```bash
  python -m src.data.equipment_simulator --output-dir data/generated
  ```
  Expected output: 16 device JSON files (device-*.json)

- [ ] **Generate spare parts inventory locally**
  ```bash
  python -m src.data.inventory_data_generator --output-dir data/generated
  ```
  Expected output: spare_parts_inventory.json

- [ ] **Create S3 bucket and upload data**
  ```bash
  python scripts/setup_s3_for_mcp_tools.py \
    --bucket-name agentic-ai-poc-3-1-data \
    --data-dir data/generated \
    --region us-east-1 \
    --output-summary s3_setup_summary.txt
  ```
  Expected: All 18 JSON files uploaded to S3, summary file created

- [ ] **Verify S3 upload**
  - Check s3_setup_summary.txt
  - Confirm all 18 files listed
  - Note S3 URLs for tools

### Phase 1b: Deploy MCP Tools to AWS (Day 1-4)

#### Step 1: Define MCP Tool Schemas (Day 1 - ~1 hour)

- [ ] Create `src/tools/schemas.py` with 3 tools:
  - `get_spare_parts` 
    - Input: `{issue_type: str}`
    - Output: `{available: bool, part_name: str, ...}`
    - Data source: S3 spare_parts_inventory.json
  - `schedule_maintenance`
    - Input: `{device_id: str, maintenance_type: str, ...}`
    - Output: `{id: str, scheduled_date: str, ...}`
  - `create_work_order`
    - Input: `{device_id: str, issue_type: str, ...}`
    - Output: `{id: str, created_date: str, ...}`

#### Step 2: Create Lambda Functions (Day 2-3 - ~2 hours)

- [ ] Create `src/lambda_functions/get_spare_parts.py`
  - Reads from S3: `s3://agentic-ai-poc-3-1-data/data/spare_parts_inventory.json`
  - Returns spare part info or 404

- [ ] Create `src/lambda_functions/schedule_maintenance.py`
  - Generates maintenance IDs
  - Returns scheduled date

- [ ] Deploy both Lambda functions to AWS
  - Create IAM role with S3 read permissions
  - Package code as ZIP
  - Create Lambda functions in AWS
  - Test locally first

#### Step 3: Deploy create_work_order with App Runner (Day 3-4 - ~1.5 hours)

- [ ] Create `src/ecs_tasks/create_work_order/app.py`
  - FastAPI application
  - POST endpoint for work order creation
  - Returns work order with ID

- [ ] Create `src/ecs_tasks/create_work_order/Dockerfile`
  - Python 3.11 base image
  - Install FastAPI, uvicorn
  - Copy app.py
  - Expose port 8000

- [ ] Create `src/ecs_tasks/create_work_order/requirements.txt`
  - fastapi
  - uvicorn
  - boto3 (if needed)

- [x] Build and deploy App Runner service
  - Build Docker image
  - Push to ECR
  - Create IAM role for App Runner ECR pull (AmazonEC2ContainerRegistryReadOnly + permission boundary)
  - Deploy with App Runner using the correct port (8000)
  - Get public ServiceUrl for testing
  - ✅ ServiceUrl: `https://tisvuktmqa.us-east-1.awsapprunner.com`

#### Step 4: Register Tools with AgentCore (Day 4 - ~1 hour) ✅ DONE

- [x] Create AgentCore Gateway using starter kit script
  - Command: `python scripts/create_agentcore_gateway_starter.py`
  - Expected: `gateway_info.json` created with gateway ID and URL

- [x] Register all MCP tools using starter kit script
  - Command: `python scripts/register_mcp_tools_starter.py`
  - Uses values from `.agentcore.env`
  - Lambda tools (`get-spare-parts`, `schedule-maintenance`): registered via starter toolkit `create_mcp_gateway_target()` with `GATEWAY_IAM_ROLE`
  - App Runner tool (`create-work-order`): registered via direct boto3 `bedrock-agentcore-control` client (toolkit crashes on public `openApiSchema` targets); uses `GATEWAY_IAM_ROLE` + `iamCredentialProvider {service: apprunner}`
  - Script is idempotent: already-registered tools are skipped automatically
  - Target names use hyphens (AWS constraint: no underscores allowed in target names)

- [x] Test gateway + tool invocation using starter kit script
  - Command: `python scripts/test_agentcore_gateway_starter.py`
  - Expected (default): `Registered targets: [...]` appears (control-plane verification)
  - Data-plane test: `COGNITO_APP_CLIENT_SECRET` + `COGNITO_TOKEN_ENDPOINT` configured; `tools/list` and `tools/call` all pass ✅

- [x] Prepare runtime auth config for agents (required for Day 5-7)
  - Available in `.agentcore.env`:
    - `COGNITO_APP_CLIENT_ID`
    - `COGNITO_APP_CLIENT_SECRET`
    - `COGNITO_TOKEN_ENDPOINT`
    - `GATEWAY_URL` (from `gateway_info.json`)
  - `.agentcore.env` is in `.gitignore` — secrets not committed

#### Step 5: Configure Agent Authentication (Day 4 - ~1 hour) ✅ DONE

> **Note:** The original tasks in this step were superseded by the `setup_cognito_token_flow.py` script and the data-plane test. The items below reflect what was actually implemented.

- [x] Set up Cognito token flow for agents (confidential client with `client_credentials` grant)
  - Command: `python scripts/setup_cognito_token_flow.py`
  - Creates: resource server (`agentcore`), scope (`invoke`), Cognito domain, confidential app client
  - Automatically updates `.agentcore.env` with `COGNITO_APP_CLIENT_ID`, `COGNITO_APP_CLIENT_SECRET`, `COGNITO_TOKEN_ENDPOINT`, `COGNITO_SCOPE`

- [x] Recreate gateway with new confidential client in `allowedClients`
  - Delete old gateway targets + gateway (section 6g in step-by-step doc)
  - Command: `python scripts/create_agentcore_gateway_starter.py`
  - Command: `python scripts/register_mcp_tools_starter.py`

- [x] Test full data-plane flow (agent token → gateway → tools)
  - Command: `python scripts/test_agentcore_gateway_starter.py`
  - Expected: `tools/list` returns all 3 tools, `tools/call` succeeds for each tool
  - ✅ Passed on June 9, 2026

- [ ] *(Optional, not required for Phase 1)* Configure AgentCore Memory
  - Create memory namespace: `agentic-ai-poc-3-1`
  - Set retention policy
  - Can be added later if agents need persistent conversation state

### Session Notes (June 3, 2026) — Quick Reminder

- Gateway creation/registration/testing scripts are working with current setup.
- `register_mcp_tools_starter.py` is idempotent (already-registered targets are skipped).
- App Runner target is registered using direct `boto3 bedrock-agentcore-control` path due to toolkit limitation for public `openApiSchema` targets.
- Gateway deletion is **optional** (only for intentional clean re-creation or auth-config reset).
- `test_agentcore_gateway_starter.py`:
  - Always validates control-plane (`Registered targets: [...]`).
  - Runs data-plane token + sample `tools/call` only when `COGNITO_APP_CLIENT_SECRET` and `COGNITO_TOKEN_ENDPOINT` are configured.
- Authentication design summary:
  - There are **two separate hops** in the final design.
  - **Hop 1: caller -> agent service**
    - Example callers: local `curl`, dashboard, backend API, scheduler.
    - This hop may be open in local development, or protected later by API auth.
    - This hop is only about reaching your agent service.
  - **Hop 2: agent service -> AgentCore Gateway**
    - This hop uses Cognito bearer-token authentication.
    - Gateway `customJWTAuthorizer` is configured with Cognito OIDC discovery URL + allowed client ID.
    - Agent runtime uses Cognito `client_credentials` flow to fetch the token.
    - Gateway calls use `Authorization: Bearer <token>` for `tools/list` and `tools/call`.
  - **What triggers token fetch?**
    - A normal request reaches the agent service.
    - The agent starts processing.
    - When the agent reaches a point where it needs a tool call, it checks token cache.
    - If a valid token is already cached, it reuses it.
    - If token is missing or expired, it requests a new token from Cognito, stores expiry time, then calls the gateway.
  - **Failure handling expectation:**
    - If token fetch fails, agent should stop MCP tool call and return a clear auth error.
    - If gateway returns `401`/`403`, agent should refresh token once and retry once, then fail gracefully.
  - **Implementation guidance:**
    - Keep token acquisition, caching, and refresh in one shared gateway client/auth module.
    - Do not duplicate token logic across agents.
- Keep `COGNITO_APP_CLIENT_SECRET` out of git (env/secret manager only).

### Session Notes (June 9, 2026) — Data-Plane Test Passing

- ✅ Full data-plane test now passes (`tools/list` + `tools/call` for all 3 tools).
- **Fix 1:** `spare_parts_inventory.json` restructured from flat dict (`{issue_type: {...}}`) to array format (`{spare_parts: [{part_type, part_id, ...}]}`) to match Lambda filter logic. Re-uploaded to S3.
- **Fix 2:** Test script tool name resolution updated — gateway returns names in `<target>___<tool>` format (e.g., `get-spare-parts___get_spare_parts`). Script now uses substring matching via `resolve_tool_name()`.
- **Cognito token flow** fully working: `setup_cognito_token_flow.py` created resource server, domain, confidential client. Gateway recreated with new `allowedClients`.
- **Searchable `part_type` values:** bearing, seal, valve, component, coil, fan, regulator, impeller.
- **S3 re-upload command:** `aws s3 cp data/mcp-tools/spare_parts_inventory.json s3://agentic-ai-poc-3-1-mcp-tools/data/spare_parts_inventory.json --profile StandardAccess-450410489798 --region us-east-1`

---

## Week 2 Day 5-7: Agent Integration (Next Step)

This is done AFTER tools are deployed and working.

- [ ] Update HealthAgent
  - Add GatewayClient for tool calls
  - Call schedule_maintenance tool when needed
  - Add error handling

- [ ] Update DiagnosisAgent
  - Add GatewayClient for tool calls
  - Call get_spare_parts tool before scheduling
  - Call schedule_maintenance or create_work_order based on parts availability
  - Add error handling

- [ ] Create 3-Container Architecture
  - Orchestrator service (FastAPI + LangGraph)
  - HealthAgent service (FastAPI + POST /analyze)
  - DiagnosisAgent service (FastAPI + POST /diagnose)
  - Docker Compose for local development

- [ ] Test agents with tools
  - Unit tests (mock tools)
  - Integration tests (real AgentCore)
  - End-to-end tests with Docker Compose
  - Verify agent runtime can: get token -> `tools/list` -> `tools/call`

- [ ] Build dashboard (optional)
  - Flask UI
  - Display agent decisions
  - Show tool call history

---

## Architecture Summary

```
┌─────────────────────────────────────┐
│ Local Machine (Your Computer)       │
├─────────────────────────────────────┤
│ data/generated/                     │
│  ├─ device-*.json                   │
│  └─ spare_parts_inventory.json      │
│                                     │
│ Agents (Day 5-7):                   │
│  ├─ Read from data/generated/       │
│  └─ Call tools via AgentCore        │
└─────────────────────────────────────┘
              ↓ HTTPS
┌─────────────────────────────────────┐
│ AWS (Day 1-4 Deployment)            │
├─────────────────────────────────────┤
│ S3 Bucket:                          │
│  └─ agentic-ai-poc-3-1-data/data/   │
│      ├─ device-*.json               │
│      └─ spare_parts_inventory.json  │
│                                     │
│ Lambda Functions:                   │
│  ├─ get_spare_parts                 │
│  └─ schedule_maintenance            │
│                                     │
│ App Runner Service:                 │
│  └─ create_work_order               │
│                                     │
│ AgentCore Gateway:                  │
│  └─ Routes tool calls & auth        │
│                                     │
│ AgentCore Memory:                   │
│  └─ Persists agent state            │
└─────────────────────────────────────┘
```

---

## Key Files to Create/Reference

| File | Purpose | Created By |
|------|---------|-----------|
| `scripts/setup_s3_for_mcp_tools.py` | S3 setup automation | GitHub Copilot (DONE) |
| `src/tools/schemas.py` | MCP tool schemas | You (Day 1) |
| `src/lambda_functions/get_spare_parts.py` | Spare parts tool | You (Day 2) |
| `src/lambda_functions/schedule_maintenance.py` | Scheduling tool | You (Day 2-3) |
| `src/ecs_tasks/create_work_order/` | Work order service | You (Day 3-4) |
| `PHASE1_WEEK2_DAY1_4_SETUP.md` | Architecture & concepts | GitHub Copilot (UPDATED) |
| `PHASE1_WEEK2_DAY1_4_IMPLEMENTATION.md` | Implementation details | GitHub Copilot (UPDATED) |
| `PHASE1_ARCHITECTURE_CORRECTED.md` | Architecture clarification | GitHub Copilot (NEW) |

---

## Success Criteria: Phase 1 Complete

- ✅ Data generated locally (18 JSON files)
- ✅ Data uploaded to S3 (via setup script)
- ✅ MCP tool schemas defined (3 tools)
- ✅ Lambda functions deployed (2 functions)
- ✅ App Runner service deployed (1 service)
- ✅ Tools registered with AgentCore
- ✅ Agents can authenticate with AgentCore
- ✅ Tools can read from S3
- ✅ Test: Local agent calls tool → gets result
- ✅ Ready for Day 5-7 agent integration

---

## Troubleshooting

### S3 Upload Fails
```bash
# Check AWS credentials configured
aws sts get-caller-identity

# Re-run with verbose logging
python scripts/setup_s3_for_mcp_tools.py \
  --bucket-name agentic-ai-poc-3-1-data \
  --data-dir data/generated \
  --verbose
```

### Lambda Deploy Fails
```bash
# Check IAM role has S3 permissions
aws iam list-role-policies --role-name lambda-mcp-role

# Test Lambda locally with mock S3
python -m pytest test_lambda_functions.py -v
```

### Tool Registration Fails
```bash
# Validate Cognito OAuth settings first
python scripts/check_cognito_app_client_oauth.py --profile StandardAccess-450410489798 --region us-east-1

# Create gateway + register tools via scripts
python scripts/create_agentcore_gateway_starter.py
python scripts/register_mcp_tools_starter.py
python scripts/test_agentcore_gateway_starter.py
```

### Agent Credentials Fail
```bash
# Refresh SSO login if needed
aws sso login --profile StandardAccess-450410489798

# Auto-fix Cognito OAuth app-client settings (if needed)
python scripts/fix_cognito_app_client_oauth.py --profile StandardAccess-450410489798 --region us-east-1 --callback-url http://localhost:3000/callback --logout-url http://localhost:3000/logout

# Test credential refresh
python test_agentcore_connection.py --verbose
```

---

## Next Actions

1. **Generate data** (5 min)
   ```bash
   python -m src.data.equipment_simulator --output-dir data/generated
   python -m src.data.inventory_data_generator --output-dir data/generated
   ```

2. **Upload to S3** (2 min)
   ```bash
   python scripts/setup_s3_for_mcp_tools.py --bucket-name agentic-ai-poc-3-1-data --data-dir data/generated
   ```

3. **Deploy tools** (Days 1-4)
   - Follow PHASE1_WEEK2_DAY1_4_SETUP.md
   - Create schemas, Lambda, ECS
   - Register with AgentCore

4. **Connect agents** (Days 5-7)
   - Follow PHASE1_WEEK2_DAY5_7_SETUP.md
   - Update agent code
   - Test integration

---

Everything is documented. You're ready to start! ✅
