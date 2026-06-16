# Quick Sync Reference: 3 Documents Aligned

## ✅ All Documents NOW Consistent

### Document 1: WEEK2_DAY5_7_AGENT_INTEGRATION.md
**Purpose:** Architecture & workflows (THE REFERENCE)  
**Coverage:**  
- 3-container architecture diagram ✅
- 4 agent-specific decision flow diagrams ✅  
- 4 real-world stories (Story 1-4) ✅
- Story 2: Compressor, vibration 4.2 mm/s, confidence 0.88 ✅
- Complete DiagnosisAgent 4-step implementation code ✅
- Action sourcing (Rules vs LLM) ✅
- All 4 action types with tool calls ✅

---

### Document 2: AGENT_UPGRADE_GUIDE.md  
**Purpose:** Implementation guide for developers (JUST SYNCHRONIZED)  
**Key Fixes:**
- ✅ HealthAgent now does analysis ONLY (no tools)
- ✅ DiagnosisAgent now shows 4-step process with confidence threshold
- ✅ Added Router node explanation (conditional routing)
- ✅ All 4 action types now listed (was 3)
- ✅ LLM integration documented (when confidence < 0.85)
- ✅ References 4 Stories from WEEK2_DAY5_7
- ✅ Complete code examples for both agents

**For Developers:**
```
HealthAgent Role: device_data → classify health → return health_status
                  (No tools, no actions)

Router Role:      health_status == "healthy"? 
                  → YES: return "healthy" (skip Diagnosis) 
                  → NO: call DiagnosisAgent

DiagnosisAgent:   sensor_data + health_status → 4-step process → tools
                  Step 1: Match rules (confidence score)
                  Step 2: Check if confidence ≥ 0.85
                  Step 3: If < 0.85, call LLM
                  Step 4: Execute action (4 branches)
```

---

### Document 3: WEEK2_DAY1_4_STEP_BY_STEP.md
**Purpose:** Phase 1 setup tasks (NO CHANGES NEEDED)  
**Scope:** Days 1-4 infrastructure only  
- S3 bucket setup ✅
- Lambda functions ✅
- MCP tools registration ✅
- Cognito setup ✅
- NOT about agent workflows (separate Phase 2 scope)

---

## Golden Rules (Now Consistent Everywhere)

1. **Who analyzes health?** → HealthAgent (only)
2. **Who decides routing?** → Router (in Orchestrator)
3. **Who calls tools?** → DiagnosisAgent (only)
4. **When is LLM called?** → When confidence < 0.85
5. **What are the actions?** → URGENT_REPAIR, SCHEDULE_MAINTENANCE, CHECK_PARTS_FIRST, MONITOR_ONLY
6. **When is Router skipped?** → Never skip Router; it's how we save costs
7. **What does HealthAgent return?** → health_status, degradation_score, anomalies (NEVER actions/tools)

---

## Story 2 Reference (Everywhere Consistent)

**Compressor Example:**
- Temperature: 87°C (slightly high)
- Pressure: 5.5-6.2 bar (fluctuating)
- **Vibration: 4.2 mm/s (HIGH)** ← KEY FIX
- Rule 1 pattern: "pressure_fluctuation + vibration_high"
- **Confidence: 0.88 ✓** (Now makes sense!)
- Action: SCHEDULE_MAINTENANCE ✓

---

## Ready for Implementation

### What Developers Should Use

1. **For Architecture Understanding:**
   - Read: WEEK2_DAY5_7_AGENT_INTEGRATION.md
   - Focus: Section 2 (Architecture), Section 1.5 (Stories)

2. **For Coding:**
   - Read: AGENT_UPGRADE_GUIDE.md
   - Focus: "Required Changes by Agent" section
   - Copy: Code examples for HealthAgent and DiagnosisAgent
   - Reference: Real-World Examples section (links to Stories)

3. **For Router Concept:**
   - Read: AGENT_UPGRADE_GUIDE.md
   - Section: "Week 2 Orchestration: 3-Service Workflow"
   - See: Cost optimization table

### Step-by-Step Implementation

Day 5:
- [ ] Create `src/gateway/client.py` (GatewayClient module)
- [ ] Wrap HealthAgent as FastAPI service (port 8001)
- [ ] Wrap DiagnosisAgent as FastAPI service (port 8002)

Day 6:
- [ ] Create Orchestrator with LangGraph (port 8000)
- [ ] Add 4 LangGraph nodes: health_agent_node, router_node, diagnosis_agent_node, aggregator_node
- [ ] Docker Compose file

Day 7:
- [ ] End-to-end tests (all 4 stories)
- [ ] Error handling
- [ ] Documentation

---

## Final Checklist Before Implementation

- [x] HealthAgent role clarified (analysis only)
- [x] DiagnosisAgent role clarified (pattern + LLM + tools)
- [x] Router node concept documented
- [x] Confidence threshold (0.85) defined everywhere
- [x] LLM integration documented
- [x] All 4 action types aligned
- [x] Story 2 vibration (4.2 mm/s) consistent everywhere
- [x] GatewayClient usage documented
- [x] Tool calling patterns clear
- [x] Cost optimization explained

✅ **ALL SYSTEMS GO FOR IMPLEMENTATION** 🚀
