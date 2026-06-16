# Phase 1 Week 1 Day 5-7: Implementation Reference

Complete implementation details for all agent code created in Day 5-7.

**See [PHASE1_WEEK1_DAY5_7_SETUP.md](PHASE1_WEEK1_DAY5_7_SETUP.md) for architecture and concepts.**

---

## File Structure

```
src/
├── agents/
│   ├── __init__.py              (22 lines) - Package initialization
│   ├── base_agent.py            (51 lines) - Abstract BaseAgent class
│   ├── health_agent.py          (188 lines) - Health state classification
│   └── diagnosis_agent.py       (395 lines) - Equipment-specific diagnosis
└── graph/
    ├── __init__.py              (6 lines) - Package initialization
    └── workflow.py              (346 lines) - LangGraph orchestration

test_health_agent.py             (135 lines) - Unit tests
test_workflow.py                 (169 lines) - Integration tests  
test_all_devices.py              (201 lines) - Batch processing

output/reports/                  - Generated reports (17 devices + 1 summary)
```

**Total Production Code:** 1,490 lines  
**Total Test Code:** 505 lines

---

## File Details

### 1. `src/agents/__init__.py`

**Purpose:** Package initialization and exports.

**Contains:**
- Imports for BaseAgent, HealthAgent, DiagnosisAgent
- `__all__` export list

**Key Line Range:** 1-22

---

### 2. `src/agents/base_agent.py`

**Purpose:** Abstract base class defining agent contract.

**Contains:**
- `BaseAgent` abstract class
- `name` and `agent_type` attributes
- `async execute()` abstract method
- `_log()` helper method

**Key Methods:**
- `async execute(input_data)` - Abstract method all agents implement

**Key Line Range:** 1-51

**Example Usage:**
```python
from src.agents.base_agent import BaseAgent

class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__("MyAgent", "my_type")
    
    async def execute(self, input_data):
        # Implementation here
        return result
```

---

### 3. `src/agents/health_agent.py`

**Purpose:** Reads degradation score and classifies health state.

**Contains:**
- `HealthAgent` class (inherits from BaseAgent)
- Health state classification (healthy/warning/alert/critical)
- Anomaly detection (sensor values outside normal ranges)
- Trend calculation (degrading/stable/improving)

**Key Methods:**
1. `async execute(input_data)` - Main method
   - Input: `device_id`, `current_reading`, optional `historical_readings`
   - Output: `health_state`, `degradation_score`, `trend`, `anomalies`

2. `_classify_health_state(degradation_score)` - Maps score to state
   - Healthy: < 0.10
   - Warning: 0.10-0.25
   - Alert: 0.25-0.42
   - Critical: ≥ 0.42

3. `_detect_anomalies(reading)` - Finds sensors outside normal range
   - Checks each sensor value against `normal_range`
   - Returns list of anomaly names

4. `_calculate_trend(historical_readings)` - Compares recent vs old degradation
   - Returns: degrading, stable, or improving

**Key Line Range:** 1-188

**Example Usage:**
```python
from src.agents.health_agent import HealthAgent
import asyncio

agent = HealthAgent()
result = asyncio.run(agent.execute({
    'device_id': 'pump-001',
    'current_reading': {
        'degradation_score': 0.87,
        'readings': {...}
    }
}))

# result['health_state'] = 'critical'
# result['trend'] = 'degrading'
```

---

### 4. `src/agents/diagnosis_agent.py`

**Purpose:** Equipment-specific root cause analysis.

**Contains:**
- `DiagnosisAgent` class
- 4 equipment-specific diagnosis methods
- Pattern matching logic per equipment type
- Confidence scoring (0.0-1.0)

**Key Methods:**
1. `async execute(input_data)` - Main method
   - Input: `device_id`, `equipment_type`, `health_result`, `current_reading`
   - Output: `primary_diagnosis`, `confidence`, `severity`, `recommended_actions`

2. `_diagnose_pump(reading)` - PUMP-specific patterns
   - Detects: cavitation, bearing wear, seal failure
   - Analyzes: flow, pressure, temperature, vibration

3. `_diagnose_motor(reading)` - MOTOR-specific patterns
   - Detects: bearing degradation, overload, insulation breakdown
   - Analyzes: RPM, current, temperature, vibration

4. `_diagnose_compressor(reading)` - COMPRESSOR-specific patterns
   - Detects: thermal stress, efficiency loss, valve issues
   - Analyzes: discharge pressure, discharge temp, motor current

5. `_diagnose_generator(reading)` - GENERATOR-specific patterns
   - Detects: voltage degradation, AVR issues, winding problems
   - Analyzes: voltage, current, frequency, temperature

**Diagnosis Pattern Example (PUMP):**
```
If temperature_high AND flow_low AND vibration_high:
  → Diagnosis: "Pump cavitation with bearing wear"
  → Confidence: 0.92 (very sure)
  → Severity: "high"
  → Actions: ["Check suction", "Inspect impeller", "Replace bearings"]
```

**Key Line Range:** 1-395

**Example Usage:**
```python
from src.agents.diagnosis_agent import DiagnosisAgent
import asyncio

agent = DiagnosisAgent()
result = asyncio.run(agent.execute({
    'device_id': 'pump-004',
    'equipment_type': 'PUMP',
    'health_result': {...},
    'current_reading': {...}
}))

# result['primary_diagnosis'] = 'Pump cavitation with bearing wear'
# result['confidence'] = 0.92
# result['recommended_actions'] = ['Check suction...', '...']
```

---

### 5. `src/graph/__init__.py`

**Purpose:** Package initialization for graph module.

**Contains:**
- Imports for AgentWorkflow
- `__all__` export list

**Key Line Range:** 1-6

---

### 6. `src/graph/workflow.py`

**Purpose:** LangGraph orchestration of all agents.

**Contains:**
- `MonitoringState` TypedDict (state schema)
- `AgentWorkflow` class with 4-node LangGraph workflow

**Key Components:**

1. **MonitoringState (TypedDict)** - Passed between nodes
   - `device_id`, `equipment_type`
   - `current_reading`, `health_result`, `diagnosis_result`
   - `final_report`, `status`

2. **AgentWorkflow Class**
   - `_build_graph()` - Constructs LangGraph workflow
   - `_health_agent_node()` - Executes HealthAgent
   - `_router_node()` - Decides routing (NOT an agent)
   - `_diagnosis_agent_node()` - Executes DiagnosisAgent
   - `_aggregator_node()` - Combines results
   - `_should_diagnose()` - Router conditional function
   - `run()` - Executes workflow for single device

**Workflow Edges:**
```
entry → health_agent_node
         ↓
      router_node
         ↓
   _should_diagnose (conditional)
      ↙        ↖
  "diagnose"    "end"
     ↓           ↓
diagnosis_agent  aggregator_node
     ↓            ↑
     └────────────┘
         ↓
       END
```

**Router Logic:**
- If health_state in [warning, alert, critical] → route to "diagnose"
- Else → route to "end" (skip diagnosis, go to aggregator)

**Key Line Range:** 1-346

**Example Usage:**
```python
from src.graph.workflow import AgentWorkflow

workflow = AgentWorkflow()

report = workflow.run(
    device_id='pump-004',
    equipment_type='PUMP',
    current_reading={...}  # From JSON file
)

# report = {
#   'device_id': 'pump-004',
#   'equipment_type': 'PUMP',
#   'health': {...health_agent result...},
#   'diagnosis': {...diagnosis_agent result...},  # or None
#   'status': 'completed'
# }
```

---

## Test Files

### 7. `test_health_agent.py`

**Purpose:** Unit tests for HealthAgent.

**Tests:**
1. Single reading analysis (4 devices with different health states)
2. Trend calculation with historical data
3. Anomaly detection

**Run:**
```bash
python test_health_agent.py
```

**Key Line Range:** 1-135

---

### 8. `test_workflow.py`

**Purpose:** Integration tests for full workflow.

**Tests:**
1. Single device workflow (verifies all nodes execute)
2. All 17 devices workflow (verifies routing logic)

**Run:**
```bash
python test_workflow.py
```

**Expected Output:**
- 3 healthy devices (skip diagnosis)
- 8 alert devices (run diagnosis)
- 6 critical devices (run diagnosis)

**Key Line Range:** 1-169

---

### 9. `test_all_devices.py`

**Purpose:** Batch processing and report generation.

**What it does:**
1. Loads all 17 device JSON files
2. Runs workflow for each device (latest reading)
3. Saves individual reports to `output/reports/`
4. Creates fleet summary with critical devices

**Run:**
```bash
python test_all_devices.py
```

**Output:**
- 17 individual device reports (JSON)
- 1 fleet summary (JSON)
- Total: 18 files in `output/reports/`

**Key Line Range:** 1-201

---

## Data Flow

### Single Device Processing

```
pump-004.json (720 readings)
        ↓
     [Latest reading extracted]
        ↓
   HealthAgent.execute()
   ├─ Read degradation_score: 0.87
   ├─ Classify: "critical"
   ├─ Detect anomalies: ["temperature_out_of_range"]
   └─ Output: {health_state: 'critical', ...}
        ↓
   Router: Should diagnose?
   ├─ Check health_state: 'critical'
   └─ Decision: YES, route to diagnosis
        ↓
   DiagnosisAgent.execute()
   ├─ Equipment type: PUMP
   ├─ Analyze sensor patterns
   ├─ Match pattern: temp↑ + flow↓ + vibration↑
   └─ Output: {diagnosis: 'cavitation', confidence: 0.92, ...}
        ↓
   Aggregator: Combine results
   ├─ Add health + diagnosis
   ├─ Set status: 'completed'
   └─ Output: {device_id, equipment_type, health, diagnosis}
        ↓
   Save to JSON
   └─ output/reports/pump-004_report.json
```

---

## Code Statistics

| Component | Lines | Purpose |
|-----------|-------|---------|
| base_agent.py | 51 | Abstract pattern |
| health_agent.py | 188 | State classification |
| diagnosis_agent.py | 395 | Root cause analysis |
| workflow.py | 346 | Orchestration |
| Package inits | 28 | Module setup |
| **Production Total** | **1,008** | Core agents + workflow |
| **Tests Total** | **505** | Unit + integration + batch |
| **Grand Total** | **1,513** | All code |

---

## Dependencies

**Required Packages:**
```
langgraph>=0.1.0
langchain>=0.1.0
asyncio (built-in)
json (built-in)
pathlib (built-in)
typing (built-in)
```

**Install:**
```bash
pip install langgraph langchain
```

---

## Configuration Files

No additional configuration needed. All settings hardcoded in agents:

- **Health state thresholds:** In `health_agent.py` `_classify_health_state()`
- **Anomaly ranges:** In JSON files themselves (`normal_range` per sensor)
- **Diagnosis patterns:** In `diagnosis_agent.py` per equipment type
- **Workflow routing:** In `workflow.py` `_should_diagnose()`

---

## Common Issues & Solutions

**Issue: Import errors**
```bash
# Make sure __init__.py files exist
touch src/agents/__init__.py
touch src/graph/__init__.py
```

**Issue: LangGraph not found**
```bash
pip install --upgrade langgraph langchain
```

**Issue: JSON files not found**
```bash
# Verify Day 3-4 equipment simulator ran
ls data/generated/ | wc -l  # Should be 17
```

**Issue: Output directory doesn't exist**
```bash
mkdir -p output/reports
```

---

## Report Format

**Individual Device Report (example):**
```json
{
  "device_id": "pump-004",
  "equipment_type": "PUMP",
  "health": {
    "device_id": "pump-004",
    "health_state": "critical",
    "degradation_score": 0.87,
    "trend": "degrading",
    "anomalies": ["temperature_out_of_range", "flow_out_of_range"],
    "status": "completed"
  },
  "diagnosis": {
    "device_id": "pump-004",
    "primary_diagnosis": "Pump cavitation with bearing wear",
    "confidence": 0.92,
    "severity": "high",
    "recommended_actions": [
      "Check suction pressure immediately",
      "Inspect pump impeller for damage",
      "Replace bearings within 1 week"
    ],
    "status": "completed"
  },
  "status": "completed"
}
```

**Fleet Summary (example):**
```json
{
  "summary": {
    "total_devices": 17,
    "healthy": 3,
    "warning": 0,
    "alert": 8,
    "critical": 6
  },
  "critical_devices": [
    {
      "device_id": "pump-004",
      "degradation": 0.87,
      "diagnosis": "Pump cavitation with bearing wear"
    },
    ...
  ]
}
```

---

## Next Steps

**After verifying all tests pass:**
1. Review generated reports in `output/reports/`
2. Check fleet summary for critical devices
3. Proceed to Week 2 (MCP tools + AgentCore)

**No modifications to Day 5-7 agents** are needed to connect to AWS. Week 2 will add:
- Agent credentials (Cognito Identity)
- MCP tool invocation
- AgentCore Gateway integration

All changes happen at boundaries, not inside agents.