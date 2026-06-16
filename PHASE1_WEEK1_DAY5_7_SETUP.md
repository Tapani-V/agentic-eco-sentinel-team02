# Phase 1 Week 1 Day 5-7: Multi-Agent System with LangGraph

Build a local multi-agent system that analyzes equipment data and generates health reports with recommendations.

---

## Scope: Local Agents (No AWS)

**Key Point:** Day 5-7 agents run **purely locally** - no AWS calls, authentication, or external services.

- ✅ Read synthetic equipment data (from Day 3-4)
- ✅ Analyze with pure Python agent logic
- ✅ Generate health reports (JSON files)
- ✅ Test locally with unit and integration tests
- ❌ NO AWS services, Cognito, or DynamoDB yet
- ❌ NO MCP tools or AgentCore (these come in Week 2)

**Focus:** Get agents working correctly in local environment first. AWS integration happens Week 2.

---

## Overview

**Goal:** Create autonomous agents that analyze equipment health and recommend actions.

**What you'll build:**
- **BaseAgent**: Abstract base class defining agent contract
- **HealthAgent**: Classifies device health state (healthy/warning/alert/critical)
- **DiagnosisAgent**: Equipment-specific root cause analysis
- **LangGraph Workflow**: Orchestration engine with 4 nodes

**Workflow Pattern:**
```
Equipment Data (JSON)
        ↓
  HealthAgent (classify state)
        ↓
  Router (conditional routing)
        ↓
  DiagnosisAgent (if needed) or Skip
        ↓
  Aggregator (combine results)
        ↓
  Health Report (JSON)
```

**Key Concepts:**
- **Health States**: healthy (skip diagnosis) vs warning/alert/critical (run diagnosis)
- **Degradation Score**: 0.0-1.0 (machine wear level)
- **Anomalies**: Sensor values outside expected ranges
- **Confidence Scores**: How sure diagnosis is (0.0-1.0)
- **Recommendations**: Specific maintenance actions based on equipment type

---

## Prerequisites

✅ From Day 3-4:
- Equipment simulator completed
- 17 devices with 720 readings each in `data/generated/`
- Virtual environment activated
- LangGraph installed (`pip install langgraph`)

---

## Architecture Decision: Why This Pattern?

**Why Async Agents?**
- Enables parallel processing of multiple devices
- Future-proof for concurrent AWS API calls (Week 2)
- Aligns with AgentCore async patterns

**Why LangGraph?**
- Industry standard for agent orchestration
- Built-in state management
- Conditional routing for workflow decisions
- Easy to extend with more agents later

**Why Router is NOT an Agent?**
- Simple if/else logic doesn't need agent autonomy
- Keeps architecture clean (agents do analysis, router decides)
- Reduces complexity

**Health State Mapping:**
- Healthy (degradation < 0.10) → Skip diagnosis (trust equipment)
- Warning (0.10-0.25) → Run diagnosis (early warning)
- Alert (0.25-0.42) → Run diagnosis (close monitoring)
- Critical (≥ 0.42) → Run diagnosis (immediate action)

---

## Implementation Overview

**Files to Create (See PHASE1_WEEK1_DAY5_7_IMPLEMENTATION.md for details):**

1. `src/agents/base_agent.py` - Abstract base class for agents
2. `src/agents/health_agent.py` - Health state classification + anomaly detection
3. `src/agents/diagnosis_agent.py` - Equipment-specific root cause analysis
4. `src/graph/__init__.py` - Package initialization
5. `src/graph/workflow.py` - LangGraph workflow orchestration
6. `test_health_agent.py` - Unit tests
7. `test_workflow.py` - Integration tests
8. `test_all_devices.py` - Batch processing tests

**Total Lines:** ~1,490 lines of production code + ~505 lines of tests

---

## Quick Start

### Step 1: Create Agent Files

See [PHASE1_WEEK1_DAY5_7_IMPLEMENTATION.md](PHASE1_WEEK1_DAY5_7_IMPLEMENTATION.md) for the actual code structure and implementation details.

### Step 2: Install Dependencies

```bash
pip install langgraph langchain
```

### Step 3: Run Tests

```bash
# Unit tests for HealthAgent
python test_health_agent.py

# Integration tests for workflow
python test_workflow.py

# Batch processing all devices
python test_all_devices.py
```

### Step 4: Check Reports

```bash
ls -la output/reports/
cat output/reports/fleet_summary.json
```

---

## What Gets Generated

**Individual Device Reports** (17 files):
```
output/reports/pump-001_report.json
output/reports/pump-002_report.json
... (one per device)
output/reports/generator-004_report.json
```

**Fleet Summary** (1 file):
```
output/reports/fleet_summary.json
```

**Report Format:**
```json
{
  "device_id": "pump-004",
  "equipment_type": "PUMP",
  "health": {
    "health_state": "critical",
    "degradation_score": 0.87,
    "trend": "degrading",
    "anomalies": [...]
  },
  "diagnosis": {
    "primary_diagnosis": "Pump cavitation",
    "confidence": 0.92,
    "recommended_actions": [...]
  }
}
```

---

## Expected Test Results

- ✅ Health Agent: Classifies all devices into correct health states
- ✅ Workflow: Routes healthy devices (skip diagnosis), unhealthy devices (run diagnosis)
- ✅ Batch Processing: Generates 17 individual reports + 1 fleet summary
- ✅ All tests pass with Exit Code: 0

---

## Troubleshooting

**Import errors?**
```bash
# Make sure src/agents/__init__.py exists
ls src/agents/__init__.py

# Make sure src/graph/__init__.py exists
ls src/graph/__init__.py
```

**LangGraph errors?**
```bash
pip install --upgrade langgraph langchain
```

**Data files missing?**
```bash
# Make sure Day 3-4 equipment simulator ran
ls data/generated/ | wc -l  # Should show 17 files
```

---

## Next Steps: Week 2

Once agents work locally:
1. **Week 2 Day 1-2:** Create MCP tool stubs (Lambda functions, ECS containers)
2. **Week 2 Day 3-4:** Set up AgentCore Identity (Cognito Identity Pool, IAM roles)
3. **Week 2 Day 5-7:** Connect agents to AgentCore Gateway (agent credentials, tool invocation)

**No changes needed to Day 5-7 agents** — they work locally first, then connect to AWS Week 2.



