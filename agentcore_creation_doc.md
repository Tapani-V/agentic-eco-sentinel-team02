# AgentCore Gateway Automation: Step-by-Step Guide

## 1. Scripts Created

- **scripts/create_agentcore_gateway_starter.py**  
  Purpose: Create the AgentCore Gateway using the starter kit, set up Cognito OAuth, and output gateway info.

- **scripts/register_mcp_tools_starter.py**  
  Purpose: Register your Lambda/App Runner MCP tools with the AgentCore Gateway using the starter kit.

- **scripts/test_agentcore_gateway_starter.py**  
  Purpose: Test gateway registration via control-plane (default) and optional data-plane token call when Cognito client secret is configured.

---

## 2. Sequence to Run the Scripts

**Step 1:** Create the AgentCore Gateway and Cognito Auth  
`python scripts/create_agentcore_gateway_starter.py`

**Step 2:** Register MCP tools with the gateway  
`python scripts/register_mcp_tools_starter.py`

**Step 3:** Test the gateway and tools  
`python scripts/test_agentcore_gateway_starter.py`

---

## 3. How It Works Internally

- Uses the `bedrock_agentcore_starter_toolkit` for gateway creation and Lambda tool registration.
- Avoids the toolkit EZ Auth path for gateway auth setup; builds authorizer config from existing Cognito values in `.agentcore.env`.
- Sets up Cognito OAuth authorizer for the gateway using your existing Cognito user pool and app client.
- Creates an IAM execution role for the gateway (idempotent — skips if already exists).
- Registers each MCP tool as a gateway target with schemas and ARNs/URLs.
- The `create_agentcore_gateway_starter.py` script is **idempotent**: if the gateway already exists it fetches it by name and refreshes `gateway_info.json` (including `role_arn`).
- The `register_mcp_tools_starter.py` script is **idempotent**: already-registered tools are silently skipped.
- Uses Cognito to obtain an access token for authenticated gateway calls.
- Test script behavior: always validates registered targets via control-plane; data-plane token call is optional and runs only when `COGNITO_APP_CLIENT_SECRET` and `COGNITO_TOKEN_ENDPOINT` are set.
- All configuration (ARNs, URLs, Cognito info, etc.) is read from `.agentcore.env`.

---

## 3a. App Runner Tool Registration — Special Handling

The App Runner (`create_work_order`) tool is registered **differently** from Lambda tools due to toolkit limitations:

| | Lambda tools | App Runner tool |
|---|---|---|
| Method | `toolkit.create_mcp_gateway_target()` | `boto3 bedrock-agentcore-control` directly |
| Target type | `lambda` | `openApiSchema` |
| Credential type | `GATEWAY_IAM_ROLE` | `GATEWAY_IAM_ROLE` + `iamCredentialProvider` block |
| Schema format | `toolSchema.inlinePayload` | OpenAPI 3.0 JSON spec as `inlinePayload` |

**Why direct boto3?**  
The starter toolkit's `create_mcp_gateway_target()` crashes on `openApiSchema` type when `credentials={}` — it requires a full OAuth or API key config. Since the App Runner endpoint is public (no app-level auth), we bypass the toolkit and call `bedrock-agentcore-control` boto3 client directly.

**Credential config used for App Runner:**
```python
credentialProviderConfigurations=[{
    "credentialProviderType": "GATEWAY_IAM_ROLE",
    "credentialProvider": {
        "iamCredentialProvider": {
            "service": "apprunner",
            "region": REGION
        }
    }
}]
```

**Target name constraint:**  
AWS AgentCore Gateway target names must match `([0-9a-zA-Z][-]?){1,100}` — **no underscores allowed**. All tool names use hyphens: `get-spare-parts`, `schedule-maintenance`, `create-work-order`.

**Gateway tool naming convention (`tools/list` response):**  
When calling `tools/list`, the gateway returns tool names in `<target>___<tool>` format (double underscore separator). For example:
- `get-spare-parts___get_spare_parts`
- `schedule-maintenance___schedule_maintenance`
- `create-work-order___create_work_order`

Your agent code must use these full names when calling `tools/call`. The test script resolves them automatically via substring matching.

---

## 4. Using Your Existing Cognito User Pool

- The scripts use your existing Cognito User Pool and App Client for OAuth.
- You must provide the Cognito User Pool ID and App Client ID in `.agentcore.env`.
- If your App Client does not have the correct callback URLs or OAuth flows enabled, update it in the AWS Console:
  - Enable Authorization code grant.
  - Set appropriate callback/logout URLs.
  - Allow the necessary scopes (openid, email, etc.).

---

## 5. .agentcore.env.example (Updated)

```
# AgentCore Gateway Automation Environment Example
# Fill in your actual values and rename to .agentcore.env

# AWS
AWS_REGION=us-east-1
AWS_PROFILE=StandardAccess-450410489798
AWS_ACCOUNT_ID=450410489798
PERMISSION_BOUNDARY=GroupIT_ProjectPermissionBoundary

# Cognito
COGNITO_USER_POOL_ID=us-east-1_R6pOfxcKV
COGNITO_APP_CLIENT_ID=2a8at414274aard1bvn12gt3h2
COGNITO_USER_POOL_NAME=agentic-ai-poc-3-1-user-pool
COGNITO_CLIENT_NAME=agentic-ai-poc-3-1-client

# MCP Tool ARNs/URLs
GET_SPARE_PARTS_LAMBDA_ARN=arn:aws:lambda:us-east-1:450410489798:function:get_spare_parts
SCHEDULE_MAINTENANCE_LAMBDA_ARN=arn:aws:lambda:us-east-1:450410489798:function:schedule_maintenance
CREATE_WORK_ORDER_URL=https://tisvuktmqa.us-east-1.awsapprunner.com/work_order

# (Add more tool ARNs/URLs as needed)
```
