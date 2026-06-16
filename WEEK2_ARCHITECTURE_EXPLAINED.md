# Week 2 Architecture: Corrected Understanding

Clear explanation of agents + tools + data in Week 2.

---

## The Correct Model

### Week 2 (Phase 1): Local Setup

**Stack:**
```
Local Machine:
  ├─ Equipment Simulator
  │   └─ Generates JSON files (device_metrics)
  │
  ├─ Agents
  │   ├─ HealthAgent
  │   ├─ DiagnosisAgent
  │   └─ EscalationAgent
  │       └─ All read from LOCAL JSON files
  │
  ├─ MCP Tools (via AgentCore)
  │   ├─ schedule_maintenance (Lambda in AWS)
  │   └─ create_work_order (ECS in AWS)
  │
  └─ AgentCore Gateway
      └─ Routes tool calls to AWS
```

**Data Flow:**
1. Equipment Simulator generates JSON → stored locally
2. Agents read JSON from local disk
3. Agents analyze data locally
4. When action needed: agents call MCP tools via AgentCore
5. Tools execute in AWS and return result

**Key:** Agents DO NOT use tools to fetch data. Tools execute ACTIONS.

---

## Phase 1 vs Phase 2 vs Phase 3

### Phase 1: Week 2 (Current)
```
Agents:        LOCAL
Data:          LOCAL JSON files
Tools:         Executable actions only
               ├─ schedule_maintenance
               └─ create_work_order

Example:
  Agent reads local JSON
  → Detects high degradation
  → Calls schedule_maintenance tool
  → Tool executes in AWS
  → Returns scheduled date
```

### Phase 2: Week 3+ (Future)
```
Agents:        AWS AgentCore Runtime
Data:          S3 JSON files
Tools:         Same (schedule_maintenance, create_work_order)

Agent code:    IDENTICAL to Phase 1!
Only change:   Data source (local → S3)

Example:
  Agent reads S3 JSON (same code as Phase 1)
  → Detects high degradation
  → Calls schedule_maintenance tool (same code)
  → Tool executes (same tool)
  → Returns scheduled date (same result)
```

### Phase 3: Future Enhancement
```
Agents:        AWS AgentCore Runtime
Data:          S3 JSON files
Tools:         Extended with data-fetching tools
               ├─ schedule_maintenance (action)
               ├─ create_work_order (action)
               ├─ get_maintenance_history (data query)
               └─ get_device_alerts (data query)

This allows richer decision-making with historical context.
```

---

## What Are Tools For?

### NOT for data fetching (Week 2)
❌ Tools should NOT be used to query:
- Device metrics
- Maintenance history
- Past alerts
- Parts inventory

These come from local/S3 data files.

### YES for executing actions (Week 2)
✅ Tools ARE used for:
- `schedule_maintenance` - Schedule a maintenance task
- `create_work_order` - Create work order in system

Actions that update systems or require external integration.

---

## Agent Responsibilities (Week 2)

### Each Agent Must:

1. **READ Data** (from LOCAL JSON)
   ```python
   device_data = load_json(f'data/{device_id}.json')
   ```

2. **ANALYZE Data** (using Week 1 logic)
   ```python
   if device_data['degradation'] > 0.7:
       # decision needed
   ```

3. **EXECUTE Actions** (via MCP tools)
   ```python
   tool_result = invoke_tool(
       'schedule_maintenance',
       {'device_id': device_id, ...}
   )
   ```

4. **HANDLE Failures** (fallback gracefully)
   ```python
   try:
       result = invoke_tool(...)
   except:
       # Escalate locally
       return {'status': 'escalate', ...}
   ```

---

## Tools in Week 2

### Available Tools (Action Only)

#### 1. schedule_maintenance
```python
# Invoke via AgentCore Gateway
result = agent_core.invoke_tool(
    'schedule_maintenance',
    {
        'device_id': 'MOTOR-001',
        'maintenance_type': 'component_replacement',
        'priority': 'high',
        'reason': 'High degradation'
    },
    credentials
)

# Returns: {'id': 'MAINT-12345', 'scheduled_date': '2026-05-28'}
```

#### 2. create_work_order
```python
result = agent_core.invoke_tool(
    'create_work_order',
    {
        'device_id': 'MOTOR-001',
        'issue_type': 'bearing_failure',
        'assigned_to': 'specialist_name',
        'priority': 'high',
        'description': 'Bearing failure detected'
    },
    credentials
)

# Returns: {'id': 'WO-67890', 'status': 'created'}
```

### NOT Available (for Phase 3+)
These tools do NOT exist in Week 2:
- ❌ get_maintenance_history
- ❌ get_device_alerts
- ❌ get_spare_parts

They read data, not execute actions. Will be added in Phase 3.

---

## Data Organization: Week 2

### Local File Structure
```
Local Machine:
  /home/skroy/AGENTIC_AI_POC_Phase3_1/
  ├─ data/generated/
  │   ├─ MOTOR-001.json      ← device metrics
  │   ├─ PUMP-002.json       ← device metrics
  │   ├─ SENSOR-003.json     ← device metrics
  │   └─ ...
  │
  ├─ src/agents/
  │   ├─ health_agent.py     ← reads data/generated/*.json
  │   ├─ diagnosis_agent.py  ← reads data/generated/*.json
  │   └─ escalation_agent.py ← reads data/generated/*.json
  │
  └─ src/api/
      └─ agentcore_gateway.py ← calls tools in AWS
```

Agents read directly from `data/generated/` folder.
No tool needed for this.

### Future S3 Structure (Phase 2+)
```
S3 Bucket: agentic-ai-poc-3-1-data
  ├─ devices/
  │   ├─ MOTOR-001.json
  │   ├─ PUMP-002.json
  │   └─ ...
  │
  └─ ... other data files
```

Agent code changes:
```python
# Phase 1:
data = load_json_from_local(device_id)

# Phase 2: (same code, different function)
data = load_json_from_s3(device_id)

# Application code: IDENTICAL
```

---

## HealthAgent Example (Week 2)

```python
class HealthAgent(BaseAgent):
    def __init__(self):
        self.agentcore = AgentCoreGateway()
        self.creds = AgentCoreCredentialManager()
    
    def execute(self, input_data):
        # STEP 1: READ data from local JSON
        device_data = input_data['device_metrics']  # Already loaded
        degradation = device_data['degradation_score']
        
        # STEP 2: ANALYZE using Week 1 logic
        if degradation > 0.8:
            # Need to execute action
            return self._handle_critical_degradation(device_data)
        elif degradation > 0.6:
            return {'status': 'escalate', 'reason': 'High degradation'}
        else:
            return {'status': 'healthy', 'action': None}
    
    def _handle_critical_degradation(self, device_data):
        # STEP 3: EXECUTE action via tool
        try:
            result = self.agentcore.invoke_tool(
                'schedule_maintenance',
                {
                    'device_id': device_data['device_id'],
                    'maintenance_type': 'component_replacement',
                    'priority': 'high',
                    'degradation': degradation
                },
                self.creds.get_current()
            )
            
            # STEP 4: Return result
            return {
                'status': 'maintenance_scheduled',
                'maintenance_id': result['id'],
                'scheduled_date': result['scheduled_date']
            }
        except Exception as e:
            # STEP 4: FALLBACK on failure
            self.logger.error(f"Scheduling failed: {e}")
            return {
                'status': 'escalate',
                'reason': f'Critical degradation: {degradation}',
                'note': 'Scheduling failed, manual escalation needed'
            }
```

**Key Points:**
- Data comes from input (already loaded from local JSON)
- Analysis uses Week 1 logic
- Action execution uses MCP tool
- Failure falls back to local escalation

---

## Testing Strategy

### Unit Tests (Mock Tool Responses)
```python
def test_health_agent_schedules_on_high_degradation():
    agent = HealthAgent()
    
    # Mock the tool
    agent.agentcore.invoke_tool = Mock(
        return_value={'id': 'MAINT-001', 'scheduled_date': '2026-05-28'}
    )
    
    device_data = {
        'device_id': 'MOTOR-001',
        'degradation_score': 0.85
    }
    
    result = agent.execute({'device_metrics': device_data})
    
    # Verify
    assert result['status'] == 'maintenance_scheduled'
    assert result['maintenance_id'] == 'MAINT-001'
    
    # Verify tool was called correctly
    agent.agentcore.invoke_tool.assert_called_once()
    call_args = agent.agentcore.invoke_tool.call_args
    assert call_args[0][0] == 'schedule_maintenance'
```

### Integration Tests (Real AgentCore)
```python
def test_health_agent_with_real_agentcore():
    agent = HealthAgent()
    
    # Real local JSON
    device_data = load_local_json('MOTOR-001')
    
    # Real AgentCore call
    result = agent.execute({'device_metrics': device_data})
    
    # Verify
    assert result['status'] in ['healthy', 'escalate', 'maintenance_scheduled']
    
    if result['status'] == 'maintenance_scheduled':
        assert 'maintenance_id' in result
        # Can verify with AgentCore API if needed
```

---

## Migration Plan: Phase 1 → Phase 2

### Week 2 (Phase 1): Local Implementation ✅
```
1. Agents read from local JSON (agent code ready)
2. Agents call tools via AgentCore (agent code ready)
3. Tools execute in AWS (Lambda/ECS ready)
4. Everything works locally
```

### Week 3 (Phase 2): Move to Cloud
```
1. Upload JSON files to S3
   - Same files, just in cloud storage

2. Update data loader function
   - ONLY change: where files come from
   - Agent logic: UNCHANGED

3. Move agents to AWS AgentCore Runtime
   - SAME agent code
   - SAME tools
   - SAME logic

4. Result: Identical behavior, running in cloud
```

**Key:** Zero logic changes between phases!

---

## Summary

**Week 2 Model:**
- Agents read LOCAL JSON files
- Agents analyze with Week 1 logic
- Agents call MCP tools for ACTIONS
- Tools are: schedule_maintenance, create_work_order
- Tools execute in AWS, agents run locally

**Tools are for ACTIONS, not data fetching.**

**Phase 1 → Phase 2 Migration:**
- Change data source (local → S3)
- Keep all agent logic
- Keep all tool usage
- Seamless transition

---

## Files to Reference

- [AGENT_UPGRADE_GUIDE.md](AGENT_UPGRADE_GUIDE.md) - Detailed agent changes
- [PHASE1_WEEK2_DAY1_4_SETUP.md](PHASE1_WEEK2_DAY1_4_SETUP.md) - Tool creation (Day 1-4)
- [PHASE1_WEEK2_DAY5_7_SETUP.md](PHASE1_WEEK2_DAY5_7_SETUP.md) - Agent integration (Day 5-7)
