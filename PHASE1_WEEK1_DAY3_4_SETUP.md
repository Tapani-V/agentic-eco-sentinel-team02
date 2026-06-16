# Phase 1 Week 1 Day 3-4: Equipment Simulator & Synthetic Data

Generate 30 days of realistic equipment sensor data with **degradation modeling** (Phase 2.8 approach).

---

## Overview

**Goal:** Create synthetic equipment data with authentic degradation patterns and sensor correlations.

**What you'll build:**
- Equipment simulator with degradation score system (0.0-1.0)
- 30 days × 24 hourly readings = 720 per device
- 16 devices across 4 health states (healthy, degrading, warning, critical)
- Physics-based sensor correlations per equipment type
- JSON output files for agent training

**Equipment Types & Sensors:**
- **MOTOR**: RPM, Current, Temperature, Voltage, Power Factor, Vibration
- **PUMP**: Flow, Pressure, Temperature, Vibration, Suction Pressure
- **COMPRESSOR**: Discharge Pressure, Discharge Temp, Inlet Temp, Motor Current, Cooling Water Temp
- **GENERATOR**: Voltage, Current, Frequency, Temperature, Power Factor

**Degradation Scenarios:**
- **Healthy** (3 devices): Degradation 0.03 (stable)
- **Gradual** (5 devices): Degradation 0.08-0.30 (smooth increase)
- **Intermittent** (3 devices): Degradation 0.30-0.35 (baseline + spikes)
- **Catastrophic** (5 devices): Degradation 0.80-0.99 (critical state)

**Output:** 16 JSON files in `data/generated/` with realistic degradation data.

---

## Prerequisites

✅ From Day 1-2:
- Virtual environment activated
- AWS credentials configured (not needed for data generation)

---

## Implementation

### Step 1: Equipment Simulator (✅ COMPLETE)

**Location:** `src/data/equipment_simulator.py` (450+ lines)

**Contains:**
- `EquipmentSimulator` class with 4 equipment types
- Degradation score system (0.0-1.0) with 4 scenarios
- Physics-based sensor generation:
  - MOTOR: RPM drops, current/temp/vibration increase with degradation
  - PUMP: Flow decreases, pressure/temp/vibration increase
  - COMPRESSOR: Pressure drops, discharge temp/motor current increase
  - GENERATOR: Voltage drops, current/temp increase
- `DataGenerator` class with 16 predefined devices

### Step 2: Run Data Generation (✅ COMPLETE)

```bash
# Generate 30 days of sensor data (16 devices, 720 readings each)
python src/data/equipment_simulator.py --output-dir data/generated
```

**Output structure:**
```
data/generated/
├── pump-001.json          (healthy - 720 readings)
├── pump-002.json          (gradual_degradation)
├── pump-003.json          (gradual_degradation)
├── pump-004.json          (catastrophic)
├── pump-005.json          (catastrophic)
├── motor-001.json         (healthy)
├── motor-002.json         (gradual_degradation)
├── motor-003.json         (gradual_degradation)
├── motor-004.json         (intermittent)
├── motor-005.json         (catastrophic)
├── compressor-001.json    (healthy)
├── compressor-002.json    (gradual_degradation)
├── compressor-003.json    (intermittent)
├── compressor-004.json    (catastrophic)
├── generator-001.json     (intermittent)
├── generator-002.json     (catastrophic)
└── generator-003.json     (catastrophic)
```

### Step 3: Verify Generated Data

```bash
# Check generated files
ls -lh data/generated/

# View sample (first device)
head -100 data/generated/pump-001.json

# Count readings per device
jq 'length' data/generated/pump-001.json
# Expected output: 720

# Check degradation progression
jq '.[] | {timestamp, degradation_score, health_state}' data/generated/pump-004.json | head -20
```

**Expected totals:**
- 16 device files
- 720 readings per device
- 11,520 total readings (~1.5 MB total)

---

## Data Structure

**Each sensor reading with degradation:**
```json
{
  "device_id": "pump-001",
  "equipment_type": "PUMP",
  "timestamp": "2026-05-01T00:00:00",
  "degradation_score": 0.031,
  "health_state": "healthy",
  "readings": {
    "flow": {
      "value": 598.45,
      "unit": "GPM",
      "min": 0,
      "max": 1000,
      "normal_range": [500, 700]
    },
    "pressure": {
      "value": 149.2,
      "unit": "PSI",
      "min": 0,
      "max": 300,
      "normal_range": [140, 160]
    },
    "temperature": {
      "value": 84.8,
      "unit": "F",
      "min": 32,
      "max": 250,
      "normal_range": [70, 110]
    },
    "vibration": {...},
    "suction_pressure": {...}
  }
}
```

**Degradation Score Interpretation:**
- `0.03-0.10` → `healthy` (normal operation)
- `0.10-0.25` → `warning` (degrading, needs monitoring)
- `0.25-0.42` → `alert` (significant issues detected)
- `0.42+` → `critical` (imminent failure risk)

---

## Generated Files

**Data Summary:**
- **Devices:** 16 (4 equipment types)
- **Duration:** 30 days (May 1-30, 2026)
- **Frequency:** Hourly readings
- **Readings/device:** 720 (30 days × 24 hours)
- **Total readings:** 11,520
- **File size:** ~1.5 MB total

**Device Distribution:**
- 3 Healthy (stable, normal operation)
- 5 Gradual Degradation (declining performance)
- 3 Intermittent Issues (warning state with anomalies)
- 5 Catastrophic (critical, heading to failure)

---

## Next Steps

### Day 5-7: Build Agents (🔄 UPCOMING)

**Objective:** Create LangGraph-based agents to analyze equipment data

**Agents to implement:**
1. **BaseAgent** (`src/agents/base_agent.py`)
   - Abstract base class for all agents
   - Async execute() method pattern
   - Input/output contract

2. **HealthAgent** (`src/agents/health_agent.py`)
   - Analyzes current equipment health state
   - Calculates health metrics (avg degradation, trend)
   - Flags anomalies

3. **DiagnosisAgent** (`src/agents/diagnosis_agent.py`)
   - Performs root cause analysis
   - Identifies sensor correlations
   - Suggests maintenance actions

4. **SupervisorAgent** (`src/agents/supervisor_agent.py`)
   - Orchestrates other agents
   - Makes final recommendations
   - Generates health reports

**Expected structure:**
```
src/agents/
├── __init__.py
├── base_agent.py           (abstract base, async pattern)
├── health_agent.py         (health analysis)
├── diagnosis_agent.py      (root cause analysis)
└── supervisor_agent.py     (orchestration & reporting)
```

**Agent workflow:**
```
Equipment Data (JSON)
    ↓
HealthAgent → Calculates health metrics
    ↓
DiagnosisAgent → Root cause analysis
    ↓
SupervisorAgent → Final recommendation
    ↓
Report (JSON)
```

### Day 8-9: Integration & Testing (🔄 UPCOMING)

**Objective:** Connect agents to equipment data and test end-to-end

**Tasks:**
1. Create data loader for JSON files
2. Run agents against each device
3. Generate health reports for 16 devices
4. Validate agent recommendations
5. Test error handling

### Week 2: DynamoDB Integration (🔄 UPCOMING)

**Objective:** Load synthetic data into DynamoDB for query practice

**Tasks:**
1. Create data ingestion script
2. Batch write 11,520 readings to DynamoDB
3. Implement query patterns
4. Test agent performance with database

---

## Quick Start Checklist

✅ **Day 3-4 Completion:**
- [x] Equipment simulator implemented with Phase 2.8 approach
- [x] Degradation modeling (0.0-1.0 score system)
- [x] 4 scenario types (healthy, gradual, intermittent, catastrophic)
- [x] Physics-based sensor correlations
- [x] 16 devices generated with realistic data
- [x] 11,520 readings (720 per device) in `data/generated/`

📋 **Next: Day 5-7 Agent Development**
- [ ] Create BaseAgent abstract class
- [ ] Implement HealthAgent
- [ ] Implement DiagnosisAgent
- [ ] Implement SupervisorAgent
- [ ] Test agents with equipment data
```
Generate code for Phase 1 Week 1 Day 3-4: Equipment simulator and synthetic data generation
```

This will create:
- `src/data/equipment_simulator.py` - Main simulator
- `src/data/__init__.py` - Package init
- Unit tests

---

**Ready to proceed? Ask for code generation!**
