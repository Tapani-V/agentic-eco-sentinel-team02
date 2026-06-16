# Sync Analysis: Three Core Documents

**Purpose:** Identify inconsistencies between WEEK2_DAY5_7_AGENT_INTEGRATION.md, AGENT_UPGRADE_GUIDE.md, and WEEK2_DAY1_4_STEP_BY_STEP.md before implementation.

**Status:** ⚠️ **NEEDS SYNC** - Multiple gaps and inconsistencies found

---

## Document Comparison

### 1. Agent Workflow Design

| Aspect | WEEK2_DAY5_7 | AGENT_UPGRADE_GUIDE | WEEK2_DAY1_4 |
|--------|--------------|-------------------|--------------|
| **HealthAgent responsibility** | Threshold-based state classification only (no tools) | Calls schedule-maintenance tool ❌ | Not detailed |
| **DiagnosisAgent responsibility** | Root cause analysis + pattern matching + optional LLM + tool orchestration | Checks parts, then schedules or escalates ✓ | Not detailed |
| **Confidence threshold** | ≥0.85 = trust rule, <0.85 = call LLM | Not mentioned ❌ | Not mentioned |
| **LLM integration** | When confidence < 0.85 | Not mentioned ❌ | Not mentioned |
| **Actions defined** | URGENT_REPAIR, SCHEDULE_MAINTENANCE, CHECK_PARTS_FIRST, MONITOR_ONLY | MAINTENANCE_SCHEDULED, WORK_ORDER_CREATED, ESCALATE | Not defined |
| **Router node** | Conditionally skips DiagnosisAgent if healthy | Not mentioned ❌ | Not mentioned |
| **Health status values** | healthy, warning, critical | Not clearly defined ❌ | Not mentioned |

---

## 🔴 CRITICAL GAPS FOUND

### Gap 1: HealthAgent Should NOT Call Tools

**WEEK2_DAY5_7 says:**
> "HealthAgent analyzes device health (deterministic rules only)"
> "HealthAgent: threshold checks only (no tools)"

**AGENT_UPGRADE_GUIDE says:**
```python
def _schedule_replacement(self, device_id, device_data):
    """Execute action via MCP tool using GatewayClient"""
    result = self.gateway.call_tool('schedule-maintenance___schedule_maintenance', {...})
```
❌ **CONFLICT:** HealthAgent calling schedule-maintenance tool directly

**WEEK2_DAY1_4:**
- Not mentioned (generic Phase 1 setup guide)

**RESOLUTION NEEDED:** 
- HealthAgent should return ONLY: `health_status`, `degradation_score`, `anomalies`
- DiagnosisAgent should decide which tools to call (not HealthAgent)

---

### Gap 2: Confidence Threshold & LLM Integration

**WEEK2_DAY5_7 (Complete):**
- ✅ Defined: Confidence ≥0.85 → trust rule, execute action directly
- ✅ Defined: Confidence <0.85 → call LLM for clarification
- ✅ Defined: LLM returns recommended_action (CHECK_PARTS_FIRST, MONITOR_ONLY, SCHEDULE_MAINTENANCE, URGENT_REPAIR)
- ✅ Defined: Real scenarios showing all 4 action paths

**AGENT_UPGRADE_GUIDE (Missing):**
- ❌ No confidence threshold mentioned
- ❌ No LLM integration mentioned
- ❌ Only talks about "requires_replacement" boolean logic
- ❌ DiagnosisAgent example is too simple (rules-only, no LLM)

**WEEK2_DAY1_4 (Missing):**
- ❌ No confidence or LLM mentioned
- ❌ Only Phase 1 setup, not agent workflows

**RESOLUTION NEEDED:** 
- Update AGENT_UPGRADE_GUIDE.md to show:
  - Confidence calculation
  - LLM integration triggers
  - All 4 action types
  - DiagnosisAgent 4-step process (rules → confidence check → optional LLM → execute)

---

### Gap 3: Action Types Undefined

**WEEK2_DAY5_7 (Complete with 4 Stories):**
- ✅ URGENT_REPAIR: High-confidence rule → create-work-order (critical)
- ✅ SCHEDULE_MAINTENANCE: High-confidence rule → schedule-maintenance (planned)
- ✅ CHECK_PARTS_FIRST: LLM → get-spare-parts → then schedule or escalate
- ✅ MONITOR_ONLY: LLM low-confidence → no tools, just recommendation
- ✅ Each action demonstrated with real sensor data in 4 stories

**AGENT_UPGRADE_GUIDE (Incomplete):**
- ❌ Only mentions: MAINTENANCE_SCHEDULED, WORK_ORDER_CREATED, ESCALATE (3 types)
- ❌ CHECK_PARTS_FIRST not mentioned
- ❌ MONITOR_ONLY not mentioned
- ❌ URGENT_REPAIR not mentioned as separate action

**WEEK2_DAY1_4:**
- Not mentioned

**RESOLUTION NEEDED:** 
- Align AGENT_UPGRADE_GUIDE action types to match WEEK2_DAY5_7 (4 actions, not 3)
- Update DiagnosisAgent code example to show all 4 branches

---

### Gap 4: Router Node (Cost Optimization)

**WEEK2_DAY5_7 (Defined):**
- ✅ Router checks: health_status == "healthy"?
- ✅ If YES → return "no action needed" + SKIP DiagnosisAgent
- ✅ If NO → call DiagnosisAgent (warning or critical)
- ✅ Cost optimization: Saves LLM + tool calls for obvious healthy cases

**AGENT_UPGRADE_GUIDE:**
- ❌ Not mentioned at all
- ❌ No mention of conditional routing

**WEEK2_DAY1_4:**
- ❌ Not mentioned

**RESOLUTION NEEDED:** 
- Add Router node explanation to AGENT_UPGRADE_GUIDE
- Show LangGraph workflow with 4 nodes: health_agent_node → router_node → diagnosis_agent_node → aggregator_node

---

### Gap 5: Story 2 Vibration Value

**WEEK2_DAY5_7 (FIXED - now consistent):**
- ✅ Story 2 vibration: 4.2 mm/s (high)
- ✅ Rule 1 pattern: "pressure_fluctuation + vibration_high"
- ✅ Confidence 0.88 ✓ (now makes sense!)

**AGENT_UPGRADE_GUIDE:**
- ⚠️ No Story 2 example (no concrete scenarios)
- ⚠️ Cannot verify consistency without examples

**WEEK2_DAY1_4:**
- ⚠️ No Story 2 example

**RESOLUTION NEEDED:** 
- Add the 4 stories from WEEK2_DAY5_7 to AGENT_UPGRADE_GUIDE as concrete examples
- This will help implementation team understand decision paths

---

## Summary Table: What Each Document Should Cover

| Topic | WEEK2_DAY5_7 | AGENT_UPGRADE_GUIDE | WEEK2_DAY1_4 |
|-------|--------------|-------------------|--------------|
| Architecture overview | ✅ | ✅ | ✅ (Phase 1) |
| HealthAgent role | ✅ Correct | ❌ Wrong (calls tools) | ⚠️ Minimal |
| DiagnosisAgent role | ✅ Correct | ⚠️ Incomplete (no confidence/LLM) | ⚠️ Minimal |
| Router node | ✅ | ❌ | ❌ |
| Confidence threshold | ✅ 0.85 | ❌ | ❌ |
| LLM integration | ✅ Detailed | ❌ | ❌ |
| Action types (4) | ✅ URGENT, SCHEDULE, CHECK_PARTS, MONITOR | ⚠️ 3 types only | ❌ |
| Real scenarios/Stories | ✅ 4 detailed stories | ❌ Generic code | ❌ |
| GatewayClient usage | ✅ Specified | ✅ Code shown | ⚠️ Mentioned |
| Tool calling patterns | ✅ Detailed | ✅ Code shown | ✅ Mentioned |

---

## Recommendation: Sync Order

### Phase 1: Fix AGENT_UPGRADE_GUIDE.md (HIGHEST PRIORITY)

This is the implementation guide developers will use. It has the most critical gaps:

**Changes needed:**
1. **Update HealthAgent section** (Lines ~277-340):
   - Remove `gateway.call_tool()` calls
   - HealthAgent should ONLY return: `health_status` (healthy/warning/critical), `degradation_score`, `anomalies`
   - Add note: "HealthAgent does NOT execute actions. Actions are orchestrated by Router and DiagnosisAgent"

2. **Update DiagnosisAgent section** (Lines ~342-450):
   - Add confidence threshold (≥0.85 = trust rule, <0.85 = call LLM)
   - Add 4-step process:
     - Step 1: Match equipment patterns
     - Step 2: Check confidence
     - Step 3: Optional LLM if uncertain
     - Step 4: Execute action (4 branches)
   - Update action types: URGENT_REPAIR, SCHEDULE_MAINTENANCE, CHECK_PARTS_FIRST, MONITOR_ONLY

3. **Add Router node section** (New):
   - Show how Orchestrator routes: health_agent → router → (optional) diagnosis_agent → aggregator

4. **Add 4 Stories as examples** (Reference from WEEK2_DAY5_7):
   - Story 1: Happy Path (healthy)
   - Story 2: Simple Issue (valve wear, 4.2 mm/s vibration, 0.88 confidence)
   - Story 3: Ambiguous (LLM, parts check)
   - Story 4: Emergency (critical, 0.96 confidence)

---

### Phase 2: Update WEEK2_DAY1_4_STEP_BY_STEP.md (if needed)

Check if this document references agent workflows. If it does, align with WEEK2_DAY5_7 and corrected AGENT_UPGRADE_GUIDE.

---

### Phase 3: Verify WEEK2_DAY5_7_AGENT_INTEGRATION.md (already good)

This is already comprehensive and correct after the Story 2 vibration fix. Just verify it's used as the reference for other updates.

---

## Pre-Implementation Checklist

Before starting Days 5-7 implementation, ensure:

- [ ] AGENT_UPGRADE_GUIDE.md is updated (4 actions, confidence threshold, LLM, Router node)
- [ ] All 3 documents show consistent HealthAgent responsibilities (analysis only, no tools)
- [ ] All 3 documents show consistent DiagnosisAgent responsibilities (pattern matching + LLM + tools)
- [ ] All 4 action types (URGENT_REPAIR, SCHEDULE_MAINTENANCE, CHECK_PARTS_FIRST, MONITOR_ONLY) are defined everywhere
- [ ] Story 2 with 4.2 mm/s vibration is used as golden example across all documents
- [ ] Router node concept is documented in both AGENT_UPGRADE_GUIDE and WEEK2_DAY5_7
- [ ] GatewayClient usage patterns are identical in all code examples

---

## Files Ready for Implementation?

| Document | Status | Reason |
|----------|--------|--------|
| WEEK2_DAY5_7_AGENT_INTEGRATION.md | ✅ READY | Complete, correct after vibration fix |
| AGENT_UPGRADE_GUIDE.md | ❌ NEEDS FIXES | Missing confidence, LLM, Router, 4th action type |
| WEEK2_DAY1_4_STEP_BY_STEP.md | ⚠️ NEEDS REVIEW | Check if agent workflows are mentioned; if yes, align with other docs |

