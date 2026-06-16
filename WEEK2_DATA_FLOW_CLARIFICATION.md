# Week 2 Data Flow Clarification

Understanding how simulated data and MCP tools work together.

---

## The Complete Picture

### What Week 1 Had:
```
Equipment Simulator (generates synthetic data)
    ↓
Device Metrics: {temperature, degradation_score, vibration, ...}
    ↓
HealthAgent (local analysis)
    ├─ Check: degradation > 0.7?
    ├─ Check: temperature > 80?
    └─ Decision: HEALTHY | WARNING | CRITICAL
    ↓
Action: Monitor | Escalate | etc.
```

### What Week 2 Adds:
```
Equipment Simulator (generates synthetic data) ← UNCHANGED
    ↓
Device Metrics: {temperature, degradation_score, vibration, ...}
    ↓
HealthAgent (enhanced analysis)
    ├─ Check: degradation > 0.7? (local)
    │
    ├─ IF high degradation/temp:
    │   └─ Call MCP Tool: get_maintenance_history (via AgentCore)
    │       └─ Tool reads S3: "Last serviced 6 months ago"
    │
    ├─ COMBINE: Real-time data + Historical context
    │
    └─ Enhanced Decision: HEALTHY | WARNING | CRITICAL | SCHEDULE_REPLACEMENT
    ↓
Action: Monitor | Escalate | Schedule | etc.
```

---

## Data Sources (Clear Breakdown)

| Data Type | Source | When Used | Purpose |
|-----------|--------|-----------|---------|
| **Real-time metrics** | Equipment Simulator | Always | Agent's primary input |
| **Maintenance history** | MCP Tool → S3 | Optional, when ambiguous | Enrich decision context |
| **Device alerts** | MCP Tool → S3 | Optional, when ambiguous | Assess severity |
| **Spare parts status** | MCP Tool → S3 | Optional, for diagnosis | Check availability |

---

## Example: HealthAgent Decision Flow

### Scenario: Device with High Degradation

**Input (from Equipment Simulator):**
```json
{
  "device_id": "MOTOR-001",
  "temperature": 82,
  "degradation_score": 0.75,
  "vibration": 0.45
}
```

**Week 1 Logic:**
```python
if degradation > 0.7:
    return {'action': 'ESCALATE', 'reason': 'High degradation'}
```
Result: `ESCALATE` (no context)

**Week 2 Logic:**
```python
if degradation > 0.7:
    # NEW: Get context
    history = tool_call('get_maintenance_history', device_id)
    # Result: {"records": [{"date": "2025-11-01", ...}, ...]}
    
    # NEW: Check last maintenance
    if len(history['records']) < 2:
        return {'action': 'SCHEDULE_REPLACEMENT', 'reason': 'High degradation + rarely serviced'}
    else:
        return {'action': 'MONITOR', 'reason': 'Recently serviced, degradation normal'}
```
Result: `SCHEDULE_REPLACEMENT` (with context)

---

## Three Data Flows in Week 2

### Flow 1: Real-time Metrics (Unchanged)
```
Equipment Simulator → Agent
Time: Continuous (e.g., every 5 seconds)
Latency: < 100ms
Reliability: 100% (local)
Purpose: Real-time decision making
```

### Flow 2: Tool Queries (New)
```
Agent → AgentCore Gateway → Lambda/ECS → DynamoDB/S3
Time: On-demand (when agent needs context)
Latency: 200-500ms (network + AWS)
Reliability: 99% (depends on AWS)
Purpose: Historical context enrichment
```

### Flow 3: Fallback (New Safety)
```
If tool fails:
  → Agent continues with Week 1 logic
  → Decision made on real-time data only
  → No impact to agent operation
```

---

## Implementation Detail: Where Maintenance History Comes From

### S3 Storage (Week 2)
```
During Week 2 Day 1-4:
- Synthetic device data (JSON files) stored in S3
- Maintenance records in S3
- Alert history in S3
- Tools read from S3

Bucket structure:
s3://agentic-ai-poc-3-1-data/
  ├─ devices/
  │   ├─ MOTOR-001.json
  │   ├─ PUMP-002.json
  │   └─ ...
  ├─ maintenance/
  │   ├─ MOTOR-001_history.json
  │   ├─ PUMP-002_history.json
  │   └─ ...
  └─ alerts/
      ├─ MOTOR-001_alerts.json
      ├─ PUMP-002_alerts.json
      └─ ...
```

### Optional: DynamoDB (Week 3+)
```
If moving to DynamoDB later:
- Same tool interface (agent doesn't care)
- Tool implementation changes:
  FROM: Read S3 JSON files
  TO:   Query DynamoDB tables
- Agent code: ZERO changes
```

---

## Agent Input Sources (Crystal Clear)

### HealthAgent Inputs:
1. **Real-time device metrics** (Equipment Simulator)
   - Primary, always available
   - Format: dict with temperature, degradation, etc.
   - Used: Every execution
   
2. **Maintenance history** (MCP Tool - NEW)
   - Optional, on-demand
   - Source: DynamoDB/S3
   - Used: When degradation or temp is high

### DiagnosisAgent Inputs:
1. **Issue data** (from HealthAgent or user)
   - Primary input
   - Format: issue type, affected device
   - Used: Every execution

2. **Spare parts availability** (MCP Tool - NEW)
   - Optional, on-demand
   - Source: S3 or external inventory API
   - Used: When diagnosis requires replacement

### EscalationAgent Inputs:
1. **Escalation request** (from other agents)
   - Primary input
   - Format: issue type, severity, device
   - Used: Every execution

2. **Work order creation** (MCP Tool - NEW)
   - Action output (not input)
   - Format: work order ID and status
   - Used: When escalating

---

## The Key Insight

**Week 1:** Agents analyze real-time data in isolation  
**Week 2:** Agents analyze real-time data + optional historical context

The simulated data doesn't change. The tools don't replace it. They just provide optional enrichment.

```
Think of it like:

Week 1: Mechanic looks at car engine (real-time)
Week 2: Mechanic looks at car engine (real-time) 
        + checks service history (tool access)
        → Makes better decision
```

---

## Testing With This Understanding

### Unit Tests (Mock Tools)
```python
# Test with fake tool data
def test_health_agent_with_recent_maintenance():
    agent = HealthAgent()
    
    # Real device data (from simulator mock)
    device_data = {'degradation': 0.75, 'temperature': 82, ...}
    
    # Fake tool response
    agent.agentcore_gateway.invoke_tool = Mock(
        return_value={'records': [...]}  # Fake maintenance history
    )
    
    # Should use BOTH: real data + fake tool response
    result = agent.execute(device_data)
    assert result['action'] == 'SCHEDULE_REPLACEMENT'
```

### Integration Tests (Real Simulator + Real Tools)
```python
# Test with real simulator data + real tools
def test_health_agent_end_to_end():
    agent = HealthAgent()
    simulator = EquipmentSimulator()
    
    # Real device data from simulator
    device_data = simulator.get_next_reading()
    
    # Real tool call (to DynamoDB)
    result = agent.execute(device_data)
    
    # Should use BOTH: real simulator data + real tool data
    assert 'reason' in result  # Should explain decision with context
```

---

## No Changes to Simulator or Data Generation

✅ Equipment simulator still runs as-is  
✅ Generates synthetic device metrics  
✅ Agent receives this data (Week 1 → Week 2)  
✅ Agent ADDITIONALLY can query tools (Week 2 only)  
✅ Data generation path: **UNCHANGED**

---

## Summary

| Aspect | Week 1 | Week 2 |
|--------|--------|--------|
| **Simulator** | Generates metrics | Still generates metrics |
| **Agent input** | Real-time metrics | Real-time metrics + optional tool context |
| **Tool access** | None | Optional MCP tools |
| **Decision logic** | Local only | Local + enriched with history |
| **Fallback** | N/A | Falls back to local if tools unavailable |

**Simulated data continues flowing.** Tools are an optional enhancement.
