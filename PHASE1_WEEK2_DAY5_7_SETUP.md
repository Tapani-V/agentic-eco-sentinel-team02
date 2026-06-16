# Phase 1 Week 2 Day 5-7: Agent Integration with MCP Tools

Connect Week 1 self-sufficient agents to AWS AgentCore MCP tools via AWS AgentCore Gateway.

---

## Scope: Upgrade Agents to Use MCP Tools

**Key Point:** Week 2 Day 5-7 transforms agents from self-contained to tool-enhanced.

- ✅ Agents authenticate with AgentCore Identity
- ✅ Agents invoke tools through AgentCore Gateway
- ✅ Tools enhance agent decision logic
- ✅ Agents handle tool failures gracefully
- ✅ Full end-to-end workflow tested
- ✅ Dashboard UI calls AgentCore tools
- ❌ NO new tools created (created in Day 1-4)
- ❌ NO infrastructure changes (done in Day 1-4)

**Focus:** Update existing agents to leverage tools. Tools are enhancements, not requirements.

---

## Architecture

### Data Flow (Day 5-7)

```
Local Agent (Week 1)
    ↓
Needs context? → Call AgentCore Gateway
    ↓
Uses AgentCore Identity credentials
    ↓
AWS AgentCore Gateway (routes tool calls)
    ├─ Validates MCP schema
    └─ Routes to Lambda/ECS
    ↓
Lambda Function or ECS Container
    ├─ Executes tool logic
    └─ Returns MCP response
    ↓
AgentCore Gateway (formats response)
    ↓
Agent receives tool data
    ↓
Incorporates into decision logic
    ↓
Takes action or escalates
```

---

## Available Tools (from Day 1-4)

These tools will be ready for agents to use:

### Lambda Functions (Fast, read operations)

1. **get_maintenance_history**
   - Input: `{device_id, start_date, end_date}`
   - Output: `{records: [{date, action, status}]}`
   - Used by: HealthAgent, DiagnosisAgent

2. **get_device_alerts**
   - Input: `{device_id}`
   - Output: `{alerts: [{timestamp, severity, type}]}`
   - Used by: HealthAgent, DiagnosisAgent

3. **get_spare_parts**
   - Input: `{issue_type}`
   - Output: `{available: boolean, parts: [...]}`
   - Used by: DiagnosisAgent

### Lambda Functions (Write operations)

4. **schedule_maintenance**
   - Input: `{device_id, maintenance_type, priority}`
   - Output: `{id, status, scheduled_date}`
   - Used by: DiagnosisAgent, EscalationAgent

### ECS Containers (Complex operations)

5. **create_work_order**
   - Input: `{device_id, issue_type, assigned_to, priority}`
   - Output: `{id, status, created_date}`
   - Used by: EscalationAgent

---

## Agents to Upgrade

### 1. HealthAgent
**Current Behavior:** Checks device metrics, determines health status  
**Week 1 Decision Logic:** If degradation > threshold → escalate

**Upgrade:**
- Get maintenance history when degradation is high
- Get recent alerts
- Decision changes based on historical context
- Example: High degradation + recently serviced → monitor only

**New Decision Logic:**
```
IF degradation > 0.7 AND recent_maintenance < 2:
    THEN schedule_replacement
ELSE IF degradation > 0.7 AND recent_alerts > 3:
    THEN escalate_to_specialist
ELSE:
    THEN monitor
```

**Tools to Use:**
- `get_maintenance_history` (required)
- `get_device_alerts` (optional)

---

### 2. DiagnosisAgent
**Current Behavior:** Diagnoses equipment issues, suggests fixes  
**Week 1 Decision Logic:** Based on symptoms only

**Upgrade:**
- Check spare parts availability before suggesting replacement
- Schedule maintenance tasks automatically if parts available
- Different actions based on inventory

**New Decision Logic:**
```
IF diagnosis.requires_replacement:
    check_spare_parts()
    IF parts_available:
        schedule_maintenance()
        RETURN "Maintenance scheduled"
    ELSE:
        RETURN "Parts not available - escalate"
```

**Tools to Use:**
- `get_spare_parts` (required for decisions)
- `schedule_maintenance` (action execution)

---

### 3. EscalationAgent
**Current Behavior:** Routes issues to specialists  
**Week 1 Decision Logic:** Determine specialist type based on issue

**Upgrade:**
- Create work order automatically when escalating
- Work order captures issue details
- Track escalations in work order system

**New Decision Logic:**
```
IF issue_needs_specialist:
    specialist = determine_specialist(issue_type)
    work_order = create_work_order(device_id, issue_type, specialist)
    RETURN "Escalated with work order ID: {work_order.id}"
```

**Tools to Use:**
- `create_work_order` (action execution)

---

## Integration Architecture

### Agent Changes Required

Each agent needs:

```
1. Add AgentCore Gateway client
   └─ For invoking tools through AWS

2. Add AgentCore Credential Manager
   └─ For authentication and credential lifecycle

3. Add tool invocation methods
   └─ One method per tool or group of tools
   └─ Error handling + fallback logic

4. Modify execute() method
   └─ Make it async
   └─ Call tools when needed
   └─ Incorporate tool data into decisions

5. Update decision logic
   └─ Now uses tool data + local data
   └─ Different branches based on tool responses
```

### Client Classes Needed

**AgentCoreGateway** (new)
```python
class AgentCoreGateway:
    def __init__(self, endpoint_url: str):
        self.endpoint = endpoint_url
    
    async def invoke_tool(self, tool_name: str, params: dict, credentials: dict):
        """Call MCP tool through AgentCore Gateway"""
        # HTTPS POST to AgentCore endpoint
        # Pass credentials in request
        # Return tool response
```

**AgentCoreCredentialManager** (new)
```python
class AgentCoreCredentialManager:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
    
    def get_current(self) -> dict:
        """Get current credentials (refresh if needed)"""
        # Get from AgentCore Identity
        # Auto-refresh if expired
        # Return: {access_key, secret_key, session_token, expiration}
```

---

## Testing Strategy

### Level 1: Unit Tests (Mock Tools)
- Test each agent's tool invocation logic
- Mock AgentCore Gateway responses
- Verify decision logic uses tool data correctly
- No AWS calls

**File:** `test_health_agent_with_tools.py` (mock-based)

### Level 2: Integration Tests (Fake Tools)
- Test agents calling AgentCore with fake tool responses
- Verify end-to-end flow (agent → gateway → tool → agent)
- No real AWS resources

**File:** `test_agent_agentcore_integration.py` (fake AgentCore)

### Level 3: End-to-End Tests (Real Tools)
- Test agents calling real Lambda/ECS tools on AWS
- Real AgentCore credentials
- Real tool responses
- Verify complete workflow

**File:** `test_agent_with_real_agentcore.py` (real AWS)

### Dashboard Integration Test
- Dashboard calls AgentCore endpoints
- Displays tool results alongside agent decisions
- Handles tool failures gracefully

**File:** `test_dashboard_agentcore_integration.py`

---

## Backward Compatibility

**Critical Requirement:** If tools fail, agents must fall back to Week 1 behavior.

```python
async def execute(self, input_data):
    try:
        # Try to get tool context
        tool_data = await self._get_tool_context(...)
        if tool_data:
            # Use enhanced logic with tools
            return self._enhanced_decision(input_data, tool_data)
    except ToolError:
        # Tool failed - fall back to Week 1 logic
        self.logger.warning(f"Tool failed, using local-only logic")
    
    # Week 1 logic (always works)
    return self._local_decision(input_data)
```

**Testing:** Each agent must be tested with:
1. ✅ Tools available (happy path)
2. ✅ Tools unavailable (fallback path)
3. ✅ Tool timeouts (fallback path)
4. ✅ Tool errors (fallback path)

---

## Implementation Order

### Phase 1: Infrastructure Setup (Day 5)
- [ ] Create AgentCoreGateway client class
- [ ] Create AgentCoreCredentialManager class
- [ ] Create AgentCore endpoint configuration
- [ ] Test agent can obtain credentials
- [ ] Test agent can reach AgentCore endpoint

### Phase 2: Agent Upgrades (Day 6)
- [ ] Upgrade HealthAgent
  - [ ] Add tool invocation methods
  - [ ] Modify execute() to be async
  - [ ] Add tool data integration
  - [ ] Add error handling + fallback
  - [ ] Unit tests with mocks
  
- [ ] Upgrade DiagnosisAgent
  - [ ] Add tool invocation methods
  - [ ] Modify execute() to be async
  - [ ] Add tool data integration
  - [ ] Add error handling + fallback
  - [ ] Unit tests with mocks

- [ ] Upgrade EscalationAgent
  - [ ] Add tool invocation methods
  - [ ] Modify execute() to be async
  - [ ] Add tool data integration
  - [ ] Add error handling + fallback
  - [ ] Unit tests with mocks

### Phase 3: Integration Testing (Day 6-7)
- [ ] Integration tests (fake AgentCore)
  - [ ] HealthAgent with fake tools
  - [ ] DiagnosisAgent with fake tools
  - [ ] EscalationAgent with fake tools

- [ ] End-to-end tests (real AgentCore)
  - [ ] HealthAgent calls real Lambda
  - [ ] DiagnosisAgent calls real Lambda/ECS
  - [ ] EscalationAgent calls real ECS

- [ ] LangGraph workflow with tools
  - [ ] Agents in workflow call tools
  - [ ] Workflow completes successfully
  - [ ] Results include tool data

### Phase 4: Dashboard Integration (Day 7)
- [ ] Update Flask dashboard
  - [ ] Add AgentCore Gateway client
  - [ ] Dashboard endpoints call tools
  - [ ] Display tool results in UI
  - [ ] Error handling for tool failures

- [ ] Dashboard testing
  - [ ] UI loads agent results
  - [ ] Tool data displayed correctly
  - [ ] Tool failures handled gracefully

---

## Expected Output

### Agent Test Results
```
✅ HealthAgent tests passing
  ├─ Unit tests (mock tools): 8/8 passed
  ├─ Integration tests (fake AgentCore): 5/5 passed
  └─ End-to-end tests (real AWS): 5/5 passed

✅ DiagnosisAgent tests passing
  ├─ Unit tests (mock tools): 10/10 passed
  ├─ Integration tests (fake AgentCore): 7/7 passed
  └─ End-to-end tests (real AWS): 7/7 passed

✅ EscalationAgent tests passing
  ├─ Unit tests (mock tools): 6/6 passed
  ├─ Integration tests (fake AgentCore): 4/4 passed
  └─ End-to-end tests (real AWS): 4/4 passed
```

### Workflow Test Results
```
✅ LangGraph workflow with tools
  ├─ Device health check: Pass
  ├─ Issue diagnosis: Pass
  ├─ Maintenance scheduling: Pass
  ├─ Escalation with work order: Pass
  └─ Tool failures handled gracefully: Pass
```

### Dashboard Test Results
```
✅ Dashboard integration tests
  ├─ Dashboard loads agent results: Pass
  ├─ Tool data displayed: Pass
  ├─ Tool failures handled: Pass
  └─ UI updates reflect agent decisions: Pass
```

---

## Success Criteria

✅ All three agents upgraded and tested  
✅ Agents can authenticate with AgentCore Identity  
✅ Agents can invoke all 5 tools through AgentCore Gateway  
✅ Tool responses integrated into agent decisions  
✅ All agents have fallback logic (Week 1 behavior)  
✅ Unit tests: All passing with mock tools  
✅ Integration tests: All passing with fake AgentCore  
✅ End-to-end tests: All passing with real AWS tools  
✅ LangGraph workflow uses agents with tools  
✅ Flask dashboard displays tool results  
✅ Tool failures don't break agent execution  
✅ All tests pass with Exit Code: 0  
✅ Agents ready for production deployment

---

## Key Design Principles

### 1. Tools Are Enhancements
- Agents work without tools (Week 1 logic)
- Tools improve decision quality
- If tools unavailable, agent falls back gracefully

### 2. Async/Await Pattern
- All tool calls are async
- Agents can call multiple tools in parallel
- Timeouts prevent hanging

### 3. Error Handling
- Tool failures don't crash agents
- Detailed error logging for debugging
- Fallback to local logic always works

### 4. Credential Security
- No hardcoded AWS keys
- Temporary credentials from AgentCore Identity
- Auto-refresh on expiration
- Scoped permissions

### 5. Testing in Layers
- Unit (mock) → Integration (fake) → E2E (real)
- Each layer validates one concern
- Easy to debug issues at each layer

---

## Dependency on Day 1-4

**Day 1-4 must deliver:**
1. ✅ All 5 tool schemas defined
2. ✅ Lambda functions deployed and working
3. ✅ ECS containers deployed and working
4. ✅ Tools registered with AgentCore Gateway
5. ✅ AgentCore Identity configured
6. ✅ AgentCore Memory namespace created
7. ✅ Test tool can call Lambda/ECS successfully

**Day 5-7 assumes:**
- Tools are available and working
- AgentCore Gateway routing is functional
- AgentCore Identity provides credentials
- No changes needed to tool implementations

---

## Files to Create (Day 5-7)

### Core Infrastructure
- `src/identity/agentcore_credentials.py` - Credential manager
- `src/api/agentcore_gateway.py` - Gateway client
- `src/config/agentcore_config.py` - Endpoint configuration

### Agent Updates
- `src/agents/health_agent.py` - Updated HealthAgent
- `src/agents/diagnosis_agent.py` - Updated DiagnosisAgent
- `src/agents/escalation_agent.py` - Updated EscalationAgent

### Tests
- `test_agentcore_credentials.py` - Credential tests
- `test_agentcore_gateway.py` - Gateway client tests
- `test_health_agent_with_tools.py` - HealthAgent with tools
- `test_diagnosis_agent_with_tools.py` - DiagnosisAgent with tools
- `test_escalation_agent_with_tools.py` - EscalationAgent with tools
- `test_agent_agentcore_integration.py` - Integration with fake AgentCore
- `test_agent_with_real_agentcore.py` - End-to-end with real AWS
- `test_workflow_with_tools.py` - LangGraph workflow tests
- `test_dashboard_agentcore.py` - Dashboard integration tests

### Configuration
- Update `.env` with AgentCore endpoints
- Update `.env.template` with new variables

**Total new code: ~2,000 lines**

---

## Next Steps After Day 5-7

### Week 3+: Production Readiness
- Monitor tool performance metrics
- Optimize tool latency
- Add observability (CloudWatch, X-Ray)
- Scale tool infrastructure as needed

### Future Enhancements
- Add more tools as business needs grow
- Implement tool caching for frequently accessed data
- Add tool versioning support
- Multi-agent tool coordination patterns

---

## References

- See [AGENT_UPGRADE_GUIDE.md](AGENT_UPGRADE_GUIDE.md) for detailed agent upgrade patterns
- See [PHASE1_WEEK2_DAY1_4_SETUP.md](PHASE1_WEEK2_DAY1_4_SETUP.md) for Day 1-4 tool creation
- See [PHASE1_WEEK2_DAY1_4_IMPLEMENTATION.md](PHASE1_WEEK2_DAY1_4_IMPLEMENTATION.md) for tool details
