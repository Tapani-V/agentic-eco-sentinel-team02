# Next Steps (May 28, 2026)

## 1. Implement AgentCoreGateway
- Utility to invoke MCP tools (HTTP for App Runner, boto3 for Lambda)
- Should support authenticated requests and error handling

## 2. Implement AgentCoreCredentialManager
- Handles credentials for tool calls (e.g., AWS credentials, tokens)
- Should provide current credentials to agents/gateway

## 3. Refactor Agents
- Inject and use AgentCoreGateway and AgentCoreCredentialManager in HealthAgent, DiagnosisAgent, etc.
- On action trigger (e.g., high degradation), call the appropriate MCP tool via the gateway
- Handle tool failures gracefully (fallback to logging/escalation)

## 4. Update Orchestration
- Ensure LangGraph workflow supports tool invocation and error handling
- After agent analysis, invoke tool actions as needed (e.g., schedule_maintenance, create_work_order)

---

These steps will enable agents to orchestrate and invoke AWS MCP tools as described in the AGENT_UPGRADE_GUIDE.md.
