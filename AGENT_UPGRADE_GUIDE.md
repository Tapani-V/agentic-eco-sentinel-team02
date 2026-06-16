# Agent Upgrade Guide: Week 1 → Week 2 MCP Integration

Transform Week 1 self-sufficient agents to use AWS MCP tools for ACTIONS (not data).

---

## Architecture: Phased Approach

### Phase 1: Local Agents + 3-Container Architecture (Week 2 Day 1-7)

```
Local Machine (Docker Compose):
  ├─ Equipment Simulator → JSON files (device_metrics)
  │
  ├─ ORCHESTRATOR (port 8000)
  │   └─ LangGraph workflow routes to agent services
  │
  ├─ HEALTH AGENT SERVICE (port 8001)
  │   ├─ Read device data from LOCAL JSON files
  │   ├─ Analyze locally (Week 1 logic continues)
  │   └─ When action needed:
  │       └─ Call MCP tools via GatewayClient
  │           └─ schedule_maintenance (Lambda)
  │
  ├─ DIAGNOSIS AGENT SERVICE (port 8002)
  │   ├─ Read device data from LOCAL JSON files
  │   ├─ Analyze locally (Week 1 logic continues)
  │   └─ When action needed:
  │       └─ Call MCP tools via GatewayClient
  │           ├─ get_spare_parts (Lambda → S3)
  │           ├─ schedule_maintenance (Lambda → DynamoDB)
  │           └─ create_work_order (App Runner)
  │
  └─ GatewayClient (shared module)
      └─ Calls AgentCore Gateway (AWS) to invoke MCP tools
```

### Phase 2: AgentCore Runtime Deployment (Week 3+)

```
AWS (AgentCore Runtime):
  ├─ S3 Bucket: Generated JSON files (simulated data - same as Phase 1)
  │   └─ NOTE: Still simulated/generated data, NOT industry data yet
  │
  ├─ AgentCore Runtime: Containerized agents
  │   ├─ ORCHESTRATOR → LangGraph workflow
  │   ├─ HEALTH AGENT SERVICE → Read S3, GatewayClient calls
  │   ├─ DIAGNOSIS AGENT SERVICE → Read S3, GatewayClient calls
  │   └─ GatewayClient (same code, different env)
  │       └─ Calls AgentCore Gateway (AWS) to invoke MCP tools
  │
  └─ AgentCore Identity → Cognito credentials for tool calls
```

**Key Insight:** 
- Agent code stays the SAME between local Docker and AgentCore Runtime
- Container image is identical in both environments
- Only environment variables change (.agentcore.env configuration)

### Phase 3+: Real Industry Data Integration (Future)

When ready (future product stage):
- Replace simulated data with real industry data via **Kinesis** or similar streaming service
- Agent code remains **unchanged** (still data-source agnostic)
- Tools enhanced with data-fetching capabilities

---

## Critical Clarification: Data vs Actions

### Tools Are ONLY for ACTIONS

Agents do NOT use tools to fetch data. Tools execute actions:

| Agent Need | Where Data Comes From | Tool Required? |
|------------|----------------------|----------------|
| **Fetch device metrics** | LOCAL JSON files (Phase 1) or S3 (Phase 2) | ❌ NO |
| **Check spare parts availability** | Lambda reads S3 spare parts inventory JSON | ✅ YES (get-spare-parts) |
| **Schedule maintenance** | Lambda writes to DynamoDB | ✅ YES (schedule-maintenance) |
| **Create work order** | App Runner creates work order | ✅ YES (create-work-order) |

**Week 2 Tools (implemented now):**
- `get-spare-parts` - Check spare parts availability (**Lambda → S3**)
- `schedule-maintenance` - Schedule maintenance task (**Lambda → DynamoDB**)
- `create-work-order` - Create escalation work order (**App Runner FastAPI**)

**Tool Deployment:**
| Tool                | Deployment Type         | Backend |
|---------------------|------------------------|---------|
| get-spare-parts | Lambda | S3 (spare parts inventory) |
| schedule-maintenance | Lambda | DynamoDB (maintenance records) |
| create-work-order | App Runner | FastAPI service |

**Phase 3+ tools (future enhancements):**
- `get_maintenance_history` - Query maintenance history
- `get_device_alerts` - Query historical alerts

---

## Overview

**Week 1 Agents:** Self-contained, analyze local JSON data only  
**Week 2 Agents:** Enhanced with ability to execute actions via MCP tools

**Architecture Layer:**
- **GatewayClient** (Custom, `src/gateway/client.py`) = Runtime client for agents to call MCP tools
  - Handles Cognito token acquisition + HTTP communication
  - Wraps the patterns used in `scripts/test_agentcore_gateway_starter.py` 
  - Note: Different from AWS toolkit's `GatewayClient` which is for setup only
- **AgentCore Gateway** (AWS Service) = Hosted endpoint that routes to MCP tools (Lambda, App Runner, etc.)

**Important Distinction:**
- ❌ AWS toolkit's `GatewayClient` = Setup/admin only (create gateways, register targets) - see `create_agentcore_gateway_starter.py`
- ✅ Your custom `GatewayClient` = Runtime tool invocation (what agents use) - see `src/gateway/client.py`

Each agent needs to:
1. Continue reading device data from LOCAL files (unchanged location)
2. Analyze data locally (Week 1 logic continues)
3. When action needed: Use custom GatewayClient to call AgentCore Gateway MCP tools
4. Handle tool failures gracefully (fallback: log and escalate)

---

## Technical Note: GatewayClient Versions

**AWS Toolkit's GatewayClient** (for infrastructure setup):
```python
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient
client = GatewayClient(region_name=REGION)
```
- Used in: `scripts/create_agentcore_gateway_starter.py` (setup only)
- Purpose: Create/manage gateways and targets (one-time infrastructure setup)
- **Not used for tool calls** - See `scripts/test_agentcore_gateway_starter_1.py` for cleaner approach

**What the AWS Starter Kit does in THIS Project:**
- ✓ **Setup Phase:** Creates AgentCore Gateway infrastructure (one-time)
- ✓ **Setup Phase:** Registers MCP tools as gateway targets
- ✓ **Setup Phase:** Configures Cognito authorizer
- ❌ **NOT Runtime:** Does NOT call tools from agents
- **Why separate?** Setup is one-time admin work; runtime needs a simpler, focused client

**Your Custom GatewayClient** (for runtime tool invocation):
```python
from src.gateway.client import GatewayClient
gateway = GatewayClient()  # Calls MCP tools at runtime
result = gateway.call_tool("get-spare-parts___get_spare_parts", {...})
```
- Used in: Agent services (HealthAgent, DiagnosisAgent)
- Purpose: Runtime tool invocation with automatic token handling
- Handles: Cognito token acquisition, HTTP requests, tool name resolution
- Recommended approach: Single responsibility - focused on tool calling only

### Agent → Tool Call Architecture Flow

```
┌─────────────────────────────────────────────────────────┐
│  Agent Service (HealthAgent / DiagnosisAgent)           │
│                                                          │
│  When action needed:                                    │
│    result = gateway.call_tool("tool_name", {...})      │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Your Custom GatewayClient (src/gateway/client.py)     │
│                                                          │
│  ┌─ Step 1: Acquire Access Token from Cognito         │
│  │  └─ Uses client_credentials grant                   │
│  │     (similar logic to AWS toolkit)                  │
│  │                                                      │
│  └─ Step 2: Call AgentCore Gateway Endpoint            │
│     └─ HTTP POST with Authorization header              │
│        JSON-RPC format: {jsonrpc, method, params}      │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  AWS AgentCore Gateway (Service)                        │
│                                                          │
│  ┌─ Validates JWT token                                │
│  ├─ Routes to registered MCP tools                     │
│  └─ Returns JSON-RPC response                          │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  MCP Tools (Lambda / App Runner)                        │
│                                                          │
│  ├─ get-spare-parts (Lambda → S3)                      │
│  ├─ schedule-maintenance (Lambda → DynamoDB)           │
│  └─ create-work-order (App Runner)                     │
└─────────────────────────────────────────────────────────┘
```

**Key Points:**
- Your custom GatewayClient handles Steps 1-2 (token + HTTP)
- AWS toolkit's GatewayClient only does token extraction (not used here)
- AgentCore Gateway validates and routes (AWS service)
- MCP Tools execute actions (infrastructure layer)

---

## Agent Upgrade Pattern

### Before (Week 1)
```python
class HealthAgent(BaseAgent):
    def execute(self, device_data):
        # Data comes from local JSON
        if device_data['degradation'] > 0.7:
            return {'action': 'ESCALATE', 'reason': 'High degradation'}
        return {'action': None}
```

### After (Week 2)
```python
from src.gateway.client import GatewayClient

class HealthAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.gateway = GatewayClient()  # Handles Cognito tokens + MCP calls
    
    def execute(self, device_data):
        # Data still comes from local JSON (same as Week 1)
        degradation = device_data['degradation']
        
        # Week 1 analysis logic (unchanged)
        if degradation > 0.7:
            # NEW: Execute action via GatewayClient tool
            return self._schedule_maintenance(device_data)
        
        return {'action': None}
    
    def _schedule_maintenance(self, device_data):
        """Execute action via MCP tool on AgentCore Gateway"""
        try:
            # GatewayClient calls the AWS AgentCore Gateway service
            # AgentCore Gateway routes to registered MCP tools (Lambda, App Runner, etc.)
            result = self.gateway.call_tool(
                'schedule-maintenance___schedule_maintenance',
                {
                    'device_id': device_data['device_id'],
                    'maintenance_type': 'replacement',
                    'scheduled_date': '2026-06-15'
                }
            )
            
            return {
                'status': 'maintenance_scheduled',
                'maintenance_id': result['maintenance_id'],
                'reason': 'High degradation'
            }
        except Exception as e:
            # Fallback: escalate locally
            self.logger.error(f"Tool failed: {e}")
            return {
                'status': 'escalate',
                'reason': 'High degradation (scheduling failed)',
                'error': str(e)
            }
```

---

## Week 2 Orchestration: 3-Service Workflow

### The Router Node - Conditional Routing for Cost Optimization

**New Week 2 Architecture:**
1. **HealthAgent** (Port 8001): Classifies device state → returns `health_status`
2. **Router** (in Orchestrator): Routes based on state → skip or investigate
3. **DiagnosisAgent** (Port 8002): Root cause analysis + tool orchestration (if needed)

**Key Insight - Cost Optimization:**
- If device is `healthy` → Router skips DiagnosisAgent → **NO LLM calls, NO tool calls** → Fast & cheap
- If device is `warning` or `critical` → Router calls DiagnosisAgent → Pattern matching + optional LLM + tools

**Example Workflow:**

```
Input: sensor_data from device

│
├─ HealthAgent analyzes
│  └─ health_status = "healthy"?
│
├─ Router decides
│  ├─ YES (healthy):  RETURN "device normal" + Skip DiagnosisAgent ✓ (cost saved)
│  └─ NO (warning/critical): CALL DiagnosisAgent ✓ (investigate)
│
└─ DiagnosisAgent (if called)
   ├─ Match patterns with confidence
   ├─ If confidence >= 0.85: Trust rule, execute action
   ├─ If confidence < 0.85: Call LLM for clarification
   └─ Execute recommended action (tool call)

Output: Final response to client
```

**Real Numbers:**
| Scenario | Path | LLM | Tools | Time |
|----------|------|-----|-------|------|
| Device healthy | Health → Router (skip) | No | No | 80ms |
| Simple issue | Health → Router → Diagnosis (rules) | No | Yes | 200ms |
| Ambiguous | Health → Router → Diagnosis (LLM + parts) | Yes | Yes | 450ms |
| Critical | Health → Router → Diagnosis (urgent) | No | Yes | 120ms |

---

## Required Changes by Agent

### 1. HealthAgent

**Role:** Threshold-based health state classification only (NO tool calls)

**Current:** Reads local JSON, analyzes device health  
**New Capability:** Returns structured health status for Router to make orchestration decisions

**Key Design Principle:**
- ✅ HealthAgent does analysis only (determines device state)
- ❌ HealthAgent does NOT execute tools (no schedule-maintenance, no work orders)
- ✅ HealthAgent returns: `health_status` (healthy/warning/critical), `degradation_score`, `anomalies`
- ✅ Router and DiagnosisAgent decide when tools are called (separation of concerns)

**Changes Required:**
```python
class HealthAgent(BaseAgent):
    """
    Analyzes device health by applying threshold rules.
    Returns health classification only - does NOT execute actions/tools.
    """
    
    def __init__(self):
        super().__init__("HealthAgent", "health_monitoring")
        # NOTE: No GatewayClient needed - HealthAgent does not call tools
    
    def execute(self, input_data):
        """
        Classify device health state based on sensor thresholds.
        
        Returns:
            {
                'health_status': 'healthy' | 'warning' | 'critical',
                'degradation_score': float (0.0-1.0),
                'anomalies': [list of detected anomalies],
                'timestamp': ISO timestamp
            }
        """
        # Input: Device data from LOCAL JSON files (unchanged)
        device_data = input_data['device_metrics']
        device_id = device_data['device_id']
        equipment_type = device_data.get('equipment_type', 'generic')
        
        # Week 1 analysis logic (continues unchanged)
        degradation = device_data.get('degradation_score', 0)
        temperature = device_data.get('temperature', 0)
        vibration = device_data.get('vibration_level', 0)
        pressure = device_data.get('pressure', 0)
        
        # Detect anomalies
        anomalies = self._detect_anomalies(device_data)
        
        # Apply threshold rules to determine health_status
        health_status = self._classify_health(device_data, anomalies)
        
        # Return classification (no actions, no tools called)
        return {
            'device_id': device_id,
            'equipment_type': equipment_type,
            'health_status': health_status,  # healthy | warning | critical
            'degradation_score': round(degradation, 2),
            'anomalies': anomalies,
            'temperature': temperature,
            'vibration_level': vibration,
            'pressure': pressure,
            'timestamp': datetime.now().isoformat()
        }
    
    def _classify_health(self, device_data, anomalies):
        """
        Classify health as healthy | warning | critical based on thresholds.
        """
        temperature = device_data.get('temperature', 0)
        vibration = device_data.get('vibration_level', 'normal')
        degradation = device_data.get('degradation_score', 0)
        
        # CRITICAL: Temperature > 95°C or vibration = critical
        if temperature > 95 or vibration == 'critical':
            return 'critical'
        
        # WARNING: Temperature > 80°C or degradation > 0.6 or vibration = high
        if temperature > 80 or degradation > 0.6 or vibration == 'high':
            return 'warning'
        
        # HEALTHY: All metrics normal
        return 'healthy'
    
    def _detect_anomalies(self, device_data):
        """Detect anomalies from sensor data."""
        anomalies = []
        
        if device_data.get('temperature', 0) > 80:
            anomalies.append({
                'type': 'temperature_elevated',
                'value': device_data.get('temperature'),
                'threshold': 80
            })
        
        if device_data.get('vibration_level') in ['high', 'critical']:
            anomalies.append({
                'type': 'vibration_high',
                'value': device_data.get('vibration_level')
            })
        
        if 'pressure_fluctuation' in device_data.get('anomalies', []):
            anomalies.append({
                'type': 'pressure_fluctuation',
                'value': device_data.get('pressure')
            })
        
        return anomalies
```

**NO Tools Used:**
- HealthAgent does NOT call any MCP tools
- Tools are called by DiagnosisAgent (ONLY)

**Data Source:**
- LOCAL JSON files (Phase 1) → S3 (Phase 2, no code change needed)

**Output Example:**
```json
{
    "device_id": "pump-001",
    "equipment_type": "pump",
    "health_status": "warning",
    "degradation_score": 0.35,
    "anomalies": [
        {"type": "pressure_fluctuation", "value": 5.8},
        {"type": "temperature_elevated", "value": 87}
    ],
    "timestamp": "2026-06-12T10:30:00"
}
```

---

### 2. DiagnosisAgent

**Role:** Root cause analysis + Pattern matching + Optional LLM + Tool orchestration

**Current:** Reads local JSON, diagnoses issues  
**New Capability:** Pattern matching with confidence check, optional LLM enhancement, then orchestrates tool calls

**Key Design Principle - 4-Step Process:**
1. **Match equipment patterns** against known failure modes (rules with confidence scores)
2. **Check confidence threshold** (≥0.85 = trust rule, <0.85 = need LLM)
3. **Optional LLM enhancement** when uncertain (call Azure OpenAI for clarification)
4. **Execute action** based on decision (4 paths: URGENT_REPAIR, SCHEDULE_MAINTENANCE, CHECK_PARTS_FIRST, MONITOR_ONLY)

**4 Action Types:**
| Action | When | Tool Called | Example |
|--------|------|------------|---------|
| **URGENT_REPAIR** | High-confidence rule match (≥0.85), obvious failure | `create-work-order` (priority=critical) | Pump cavitation with bearing failure (0.96 confidence) |
| **SCHEDULE_MAINTENANCE** | High-confidence rule match (≥0.85), non-critical issue | `schedule-maintenance` | Valve wear detected (0.88 confidence) |
| **CHECK_PARTS_FIRST** | LLM recommendation after uncertainty | `get-spare-parts` + conditional `schedule-maintenance` or `create-work-order` | Possible bearing degradation (0.72 rule → 0.78 LLM) |
| **MONITOR_ONLY** | LLM recommendation, insufficient data to act | No tools, just monitoring guidance | Borderline metrics (0.68 rule → LLM says insufficient data) |

**Changes Required:**
```python
from src.gateway.client import GatewayClient
from datetime import datetime, timedelta
import logging

class DiagnosisAgent(BaseAgent):
    """
    Root cause analysis + action orchestration for warning/critical devices.
    
    Process:
    1. Match patterns (equipment-specific rules)
    2. Check confidence (≥0.85 = trust, <0.85 = call LLM)
    3. Optional LLM (if uncertain)
    4. Execute action (via MCP tools)
    """
    
    def __init__(self):
        super().__init__("DiagnosisAgent", "diagnosis")
        self.gateway = GatewayClient()  # For tool calls
        self.llm = AzureOpenAIClient()  # For uncertain cases
        self.knowledge_base = self._load_equipment_rules()
        self.logger = logging.getLogger("DiagnosisAgent")
    
    def execute(self, input_data):
        """
        Main entry point.
        
        Input:
            {
                'device_id': str,
                'equipment_type': str,
                'sensor_data': {...},
                'health_status': 'warning' | 'critical',  # From HealthAgent
                'anomalies': [...]  # From HealthAgent
            }
        
        Output:
            {
                'device_id': str,
                'equipment_type': str,
                'diagnosis': str,
                'confidence': float (0.0-1.0),
                'recommended_action': str (URGENT_REPAIR | SCHEDULE_MAINTENANCE | CHECK_PARTS_FIRST | MONITOR_ONLY),
                'action_taken': str,
                'tool_results': {...}
            }
        """
        device_id = input_data['device_id']
        equipment_type = input_data['equipment_type']
        sensor_data = input_data['sensor_data']
        anomalies = input_data['anomalies']
        health_status = input_data['health_status']
        
        # STEP 1: MATCH EQUIPMENT PATTERNS (Equipment-Specific Rules)
        rule_result = self._match_equipment_patterns(equipment_type, sensor_data, anomalies)
        
        # rule_result = {
        #     'diagnosis': 'Issue description',
        #     'confidence': 0.92,
        #     'severity': 'high',
        #     'recommended_action': 'URGENT_REPAIR' | 'SCHEDULE_MAINTENANCE' | 'CHECK_PARTS_FIRST' | 'MONITOR_ONLY',
        #     'action_details': {...}
        # }
        
        # STEP 2: CONFIDENCE CHECK
        if rule_result['confidence'] >= 0.85:
            # Trust the rule - no LLM needed
            self.logger.info(f"Rule confidence {rule_result['confidence']:.2f} >= 0.85, trusting rule")
            action = rule_result['recommended_action']
            diagnosis = rule_result['diagnosis']
            confidence = rule_result['confidence']
            llm_used = False
        else:
            # STEP 3: LLM ENHANCEMENT (uncertain case)
            self.logger.info(f"Rule confidence {rule_result['confidence']:.2f} < 0.85, calling LLM")
            llm_result = self.llm.analyze(
                device_id=device_id,
                equipment_type=equipment_type,
                sensor_data=sensor_data,
                rule_suggestion=rule_result,  # Give LLM context
                anomalies=anomalies
            )
            
            # LLM returns same structure
            # {
            #     'diagnosis': 'Better explanation',
            #     'confidence': 0.78,
            #     'recommended_action': 'CHECK_PARTS_FIRST' | 'MONITOR_ONLY' | ...,
            #     'reasoning': 'Why LLM chose this'
            # }
            
            action = llm_result['recommended_action']
            diagnosis = llm_result['diagnosis']
            confidence = llm_result['confidence']
            llm_used = True
        
        # STEP 4: EXECUTE ACTION (Call appropriate tools)
        tool_results = self._execute_action(device_id, action, rule_result, confidence)
        
        return {
            'device_id': device_id,
            'equipment_type': equipment_type,
            'diagnosis': diagnosis,
            'confidence': round(confidence, 2),
            'health_status_input': health_status,
            'recommended_action': action,
            'llm_used': llm_used,
            'action_taken': tool_results['action_taken'],
            'tool_results': tool_results.get('results', {}),
            'timestamp': datetime.now().isoformat()
        }
    
    def _execute_action(self, device_id, action, rule_result, confidence):
        """
        Execute tool calls based on recommended action.
        
        4 branches:
        - URGENT_REPAIR: Create critical work order
        - SCHEDULE_MAINTENANCE: Schedule maintenance
        - CHECK_PARTS_FIRST: Check parts, then schedule or escalate
        - MONITOR_ONLY: No tools, just recommendation
        """
        
        if action == 'URGENT_REPAIR':
            self.logger.info(f"ACTION: URGENT_REPAIR for {device_id}")
            try:
                result = self.gateway.call_tool(
                    'create-work-order___create_work_order',
                    {
                        'work_order_type': 'emergency_repair',
                        'priority': 'critical',
                        'description': f"{rule_result['diagnosis']} (Confidence: {confidence:.2f})"
                    }
                )
                return {
                    'action_taken': 'work_order_created',
                    'results': {'work_order_id': result.get('work_order_id')}
                }
            except Exception as e:
                self.logger.error(f"Create work order failed: {e}")
                return {'action_taken': 'failed', 'error': str(e)}
        
        elif action == 'SCHEDULE_MAINTENANCE':
            self.logger.info(f"ACTION: SCHEDULE_MAINTENANCE for {device_id}")
            try:
                scheduled_date = (datetime.now() + timedelta(days=7)).isoformat()[:10]
                result = self.gateway.call_tool(
                    'schedule-maintenance___schedule_maintenance',
                    {
                        'device_id': device_id,
                        'maintenance_type': rule_result.get('action_details', {}).get('maintenance_type', 'inspection'),
                        'scheduled_date': scheduled_date,
                        'reason': rule_result['diagnosis']
                    }
                )
                return {
                    'action_taken': 'maintenance_scheduled',
                    'results': {
                        'maintenance_id': result.get('maintenance_id'),
                        'scheduled_date': scheduled_date
                    }
                }
            except Exception as e:
                self.logger.error(f"Schedule maintenance failed: {e}")
                return {'action_taken': 'failed', 'error': str(e)}
        
        elif action == 'CHECK_PARTS_FIRST':
            self.logger.info(f"ACTION: CHECK_PARTS_FIRST for {device_id}")
            try:
                parts_needed = rule_result.get('action_details', {}).get('parts_needed', [])
                if not parts_needed:
                    parts_needed = ['diagnostic_required']
                
                # Check each part
                parts_results = {}
                all_available = True
                
                for part_type in parts_needed:
                    part_check = self.gateway.call_tool(
                        'get-spare-parts___get_spare_parts',
                        {'part_type': part_type}
                    )
                    parts_results[part_type] = part_check
                    if not part_check.get('available', False):
                        all_available = False
                
                # Decide next step based on parts availability
                if all_available:
                    # Parts available → schedule maintenance
                    scheduled_date = (datetime.now() + timedelta(days=3)).isoformat()[:10]
                    maint_result = self.gateway.call_tool(
                        'schedule-maintenance___schedule_maintenance',
                        {
                            'device_id': device_id,
                            'maintenance_type': 'repair_with_parts',
                            'scheduled_date': scheduled_date,
                            'reason': rule_result['diagnosis']
                        }
                    )
                    return {
                        'action_taken': 'maintenance_scheduled_with_parts',
                        'results': {
                            'maintenance_id': maint_result.get('maintenance_id'),
                            'scheduled_date': scheduled_date,
                            'parts_verified': parts_results
                        }
                    }
                else:
                    # Parts unavailable → escalate with work order
                    wo_result = self.gateway.call_tool(
                        'create-work-order___create_work_order',
                        {
                            'work_order_type': 'escalation_with_parts_order',
                            'priority': 'high',
                            'description': f"{rule_result['diagnosis']} | Parts on backorder, escalating for diagnosis"
                        }
                    )
                    return {
                        'action_taken': 'escalated_parts_unavailable',
                        'results': {
                            'work_order_id': wo_result.get('work_order_id'),
                            'parts_status': parts_results
                        }
                    }
            except Exception as e:
                self.logger.error(f"CHECK_PARTS_FIRST failed: {e}")
                return {'action_taken': 'failed', 'error': str(e)}
        
        elif action == 'MONITOR_ONLY':
            self.logger.info(f"ACTION: MONITOR_ONLY for {device_id} - deferring action")
            # NO tool calls for MONITOR_ONLY
            return {
                'action_taken': 'monitoring_recommended',
                'results': {
                    'next_check_in_hours': 8,
                    'escalation_threshold': 'if degradation > 0.7 or temp > 90°C',
                    'reason': 'Low confidence, continue monitoring'
                }
            }
        
        else:
            self.logger.warning(f"Unknown action: {action}, defaulting to MONITOR_ONLY")
            return {
                'action_taken': 'unknown_action',
                'results': {'note': 'Unknown action type, recommend manual review'}
            }
    
    def _match_equipment_patterns(self, equipment_type, sensor_data, anomalies):
        """
        Match sensor patterns to equipment-specific rules.
        Returns best-matching rule with confidence score.
        """
        rules = self.knowledge_base.get(equipment_type, [])
        matches = []
        
        for rule in rules:
            confidence = self._calculate_rule_confidence(rule, sensor_data, anomalies)
            if confidence > 0:
                matches.append((rule, confidence))
        
        if matches:
            # Sort by confidence, return best match
            best_rule, best_confidence = max(matches, key=lambda x: x[1])
            return {
                'diagnosis': best_rule['diagnosis'],
                'confidence': best_confidence,
                'severity': best_rule.get('severity', 'medium'),
                'recommended_action': best_rule['recommended_action'],
                'action_details': best_rule.get('action_details', {})
            }
        else:
            # No rules matched, return generic
            return {
                'diagnosis': 'Unable to match patterns',
                'confidence': 0.5,
                'severity': 'unknown',
                'recommended_action': 'MONITOR_ONLY',
                'action_details': {}
            }
    
    def _calculate_rule_confidence(self, rule, sensor_data, anomalies):
        """
        Calculate how well sensor data matches rule pattern.
        Returns 0.0 to 1.0.
        """
        # Simplified example - in production, this would be more sophisticated
        matched_patterns = 0
        total_patterns = len(rule.get('patterns', []))
        
        if total_patterns == 0:
            return 0.5
        
        for expected_pattern in rule.get('patterns', []):
            for anomaly in anomalies:
                if anomaly['type'] == expected_pattern:
                    matched_patterns += 1
                    break
        
        # Base confidence from pattern match
        base_confidence = matched_patterns / total_patterns
        
        # Adjust based on severity alignment
        if 'severity_sensor' in rule:
            sensor_val = sensor_data.get(rule['severity_sensor'], 0)
            if sensor_val > rule.get('severity_threshold', 100):
                base_confidence *= 1.2  # Boost confidence
        
        return min(base_confidence, 1.0)
    
    def _load_equipment_rules(self):
        """Load equipment-specific failure patterns."""
        # In production, load from external knowledge base
        return {
            'pump': [
                {
                    'pattern': 'temp_very_high AND flow_low AND vibration_critical',
                    'diagnosis': 'Pump cavitation with bearing failure',
                    'confidence': 0.96,
                    'severity': 'high',
                    'recommended_action': 'URGENT_REPAIR',
                    'action_details': {'maintenance_type': 'emergency_repair'},
                    'patterns': ['temperature_elevated', 'vibration_high']
                }
            ],
            'compressor': [
                {
                    'pattern': 'pressure_fluctuation AND vibration_high',
                    'diagnosis': 'Compressor valve wear',
                    'confidence': 0.88,
                    'severity': 'medium',
                    'recommended_action': 'SCHEDULE_MAINTENANCE',
                    'action_details': {'maintenance_type': 'valve_inspection', 'parts_needed': ['valve']},
                    'patterns': ['pressure_fluctuation', 'vibration_high']
                }
            ],
            'motor': [
                {
                    'pattern': 'temp_high AND vibration_borderline',
                    'diagnosis': 'Possible bearing degradation',
                    'confidence': 0.72,
                    'severity': 'medium',
                    'recommended_action': 'CHECK_PARTS_FIRST',
                    'action_details': {'maintenance_type': 'bearing_inspection', 'parts_needed': ['bearing']},
                    'patterns': ['temperature_elevated', 'vibration_high']
                }
            ]
        }
```

**Tools Used:**
- `get-spare-parts` (Lambda) - Check spare parts inventory
- `schedule-maintenance` (Lambda) - Schedule maintenance
- `create-work-order` (App Runner) - Create escalation work order

**Data Source:**
- Device data: LOCAL JSON files (Phase 1) → S3 (Phase 2, no code change needed)

---

## Real-World Examples: 4 Scenarios with DiagnosisAgent

For detailed walkthroughs showing all 4 action types in real scenarios, see **[WEEK2_DAY5_7_AGENT_INTEGRATION.md - Section 1.5: Stories](./WEEK2_DAY5_7_AGENT_INTEGRATION.md#15-story-how-it-works-real-world-examples)**.

**Quick Reference:**

| Story | Scenario | Confidence | LLM? | Tool(s) Called | Result |
|-------|----------|------------|------|---|--------|
| 1: Happy Path | Device healthy | N/A | No | None | No action (Router skips) |
| 2: Simple Issue | Compressor vibration 4.2 + pressure fluctuation | 0.88 ✓ | No | schedule-maintenance | Maintenance scheduled |
| 3: Ambiguous | Motor temp 84°C + vibration medium | 0.72 → 0.78 (LLM) | Yes | get-spare-parts + schedule-maintenance | Parts verified, maintenance scheduled |
| 4: Emergency | Pump cavitation critical | 0.96 ✓ | No | create-work-order | Urgent work order created |

**Key Takeaways:**
- ✅ Confidence ≥0.85 = Fast path (no LLM, no overhead)
- ✅ Confidence <0.85 = Slow path (LLM enhances, more accurate)
- ✅ Story 2 is a great template for high-confidence rules
- ✅ Story 3 shows the value of LLM for ambiguous cases
- ✅ Story 4 demonstrates critical priority escalation

---

## Implementation Checklist

For each agent (HealthAgent, DiagnosisAgent), add:

- [ ] GatewayClient initialization in __init__
- [ ] Tool invocation methods using `self.gateway.call_tool()`
- [ ] Error handling + fallback logic
- [ ] Update decision logic to call tools appropriately
- [ ] Logging for tool calls
- [ ] Wrap agents in FastAPI services for 3-container architecture
- [ ] Unit tests with mock tools
- [ ] Integration tests with real AgentCore Gateway

---

## Architecture Deployment

### Local Development (Docker Compose)

**Step 1:** Copy GatewayClient to each service container
```dockerfile
COPY src/gateway /app/src/gateway
```

**Step 2:** Create FastAPI wrappers for agents
```
services/
├── orchestrator/
│   ├── app.py           # LangGraph + HTTP calls to agents
│   ├── Dockerfile
│   └── requirements.txt
├── health_agent/
│   ├── app.py           # Wraps src/agents/health_agent.py
│   ├── Dockerfile
│   └── requirements.txt
└── diagnosis_agent/
    ├── app.py           # Wraps src/agents/diagnosis_agent.py
    ├── Dockerfile
    └── requirements.txt
```

**Step 3:** Run locally
```bash
docker-compose up
```

### AWS Deployment (AgentCore Runtime)

Same code, same containers, only environment configuration changes:
- `.agentcore.env` provides Cognito credentials
- S3 replaces LOCAL JSON file reads (no agent code changes needed)
- Container images identical to local Docker Compose

---

## Week 2 Data Generation Setup

Before implementing agents and tools, generate the required data files:

### Step 1: Generate Device Sensor Data

```bash
cd /home/skroy/AGENTIC_AI_POC_Phase3_1
python -m src.data.equipment_simulator --output-dir data/generated
```

**Output:**
- `data/generated/motor-001.json` through `pump-005.json` (16 devices)
- 720 readings per device (30 days × 24 hourly readings)
- Realistic degradation patterns across all device types

### Step 2: Generate Spare Parts Inventory

```bash
python -m src.data.inventory_data_generator --output-dir data/generated
```

**Output:**
- `data/generated/spare_parts_inventory.json`
- 8 part types with availability, lead times, costs
- Mapped to issue types that agents will diagnose

**Result:**
Both files now exist in `data/generated/` for Phase 1 (local) testing:
```
data/generated/
  ├─ motor-001.json through motor-005.json
  ├─ pump-001.json through pump-005.json
  ├─ compressor-001.json through compressor-004.json
  ├─ generator-001.json through generator-003.json
  └─ spare_parts_inventory.json
```

---

## Phase 1 → Phase 2 Migration

When migrating to Phase 2 (AWS):

1. **Copy files to S3:**
   ```bash
   aws s3 sync data/generated/ s3://agentic-ai-poc-3-1-data/ --include "*.json"
   ```

2. **Lambda functions read from S3:**
   - `schedule_maintenance` and `create_work_order` will read `spare_parts_inventory.json` from S3
   - Agent code stays identical (data-source agnostic)

---

## Week 2 Tools Implementation Summary

### Tool 1: `get_spare_parts` (Lambda Function)

**Purpose:** DiagnosisAgent queries this before scheduling maintenance to verify parts are available.

**Input Schema:**
```json
{
  "issue_type": "motor_bearing_failure"
}
```

**Output Schema:**
```json
{
  "available": true,
  "part_name": "Motor Bearing Assembly",
  "part_id": "MB-001",
  "quantity_in_stock": 5,
  "lead_time_days": 2,
  "cost": 450
}
```

**Data Source:**
- Phase 1 (Week 2): LOCAL `data/generated/spare_parts_inventory.json` (generated by inventory data generator)
- Phase 2+: S3 `s3://agentic-ai-poc-3-1-data/spare_parts_inventory.json`

**How it's generated:**
A separate inventory data generator creates this reference/knowledge base file. When you run:
```bash
python -m src.data.inventory_data_generator --output-dir data/generated
```

It creates:
- **`data/generated/spare_parts_inventory.json`** (spare parts knowledge base)

**Why separate from equipment simulator?**
- Equipment Simulator: Replicates real sensor data (physics-based)
- Inventory Generator: Creates reference/knowledge base data (configuration-based)
- Keeps concerns separated: sensor data vs. business/reference data

**Lambda Implementation:**
```python
import json

def lambda_handler(event, context):
    issue_type = event.get('issue_type')
    
    # Load spare parts inventory
    spare_parts = load_spare_parts_inventory()
    
    if issue_type in spare_parts:
        part_info = spare_parts[issue_type]
        return {
            'statusCode': 200,
            'body': json.dumps(part_info)
        }
    else:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': f'No part found for {issue_type}'})
        }

def load_spare_parts_inventory():
    # Phase 1: Local file in Lambda package
    with open('data/spare_parts_inventory.json', 'r') as f:
        return json.load(f)
    
    # Phase 2: Change to read from S3 (agent code unchanged)
    # import boto3
    # s3 = boto3.client('s3')
    # obj = s3.get_object(Bucket='agentic-ai-poc-3-1-data', Key='spare_parts_inventory.json')
    # return json.loads(obj['Body'].read())
```

**Sample Data File** (`data/generated/spare_parts_inventory.json`):
```json
{
  "motor_bearing_failure": {
    "available": true,
    "part_name": "Motor Bearing Assembly",
    "part_id": "MB-001",
    "quantity_in_stock": 5,
    "lead_time_days": 2,
    "cost": 450
  },
  "pump_seal_failure": {
    "available": true,
    "part_name": "Pump Seal Kit",
    "part_id": "PS-002",
    "quantity_in_stock": 12,
    "lead_time_days": 1,
    "cost": 120
  },
  "component_degradation": {
    "available": false,
    "part_name": "Custom Component Assembly",
    "part_id": "CC-003",
    "quantity_in_stock": 0,
    "lead_time_days": 14,
    "cost": 850,
    "backorder_note": "On order from supplier"
  }
}
```

### Tool 2: `schedule_maintenance` (Lambda Function)

**Input Schema:**
```json
{
  "device_id": "DEV001",
  "maintenance_type": "motor_bearing_failure",
  "priority": "high",
  "reason": "High degradation detected",
  "spare_part_id": "MB-001",
  "lead_time_days": 2
}
```

**Output Schema:**
```json
{
  "id": "MAINT-20260527-001",
  "device_id": "DEV001",
  "scheduled_date": "2026-05-29",
  "status": "scheduled"
}
```

### Tool 3: `create_work_order` (ECS Container)

**Input Schema:**
```json
{
  "device_id": "DEV001",
  "issue_type": "motor_bearing_failure",
  "priority": "high",
  "description": "High degradation + Parts on backorder"
}
```

**Output Schema:**
```json
{
  "id": "WO-20260527-001",
  "device_id": "DEV001",
  "status": "created",
  "assigned_date": "2026-05-27"
}
```

---

## Phase 2 → Phase 3 Migration (No Code Change!)

When moving to AWS with S3 data:

```python
# Phase 1 (Local):
device_data = load_from_local_json(device_id)

# Phase 2+ (S3):
device_data = load_from_s3(device_id)

# Agent code: EXACTLY THE SAME!
# Just change data source in data loader
```

Agent implementation is **data source agnostic**.

---

## Testing Strategy

### Unit Tests (Mock Tools)
```python
@pytest.mark.asyncio
def test_health_agent_schedules_maintenance():
    agent = HealthAgent()
    
    # Mock tool response
    agent.gateway.call_tool = Mock(
        return_value={'maintenance_id': 'MAINT-001', 'scheduled_date': '2026-05-28'}
    )
    
    device_data = {
        'device_id': 'DEV001',
        'degradation_score': 0.85
    }
    
    result = agent.execute({'device_metrics': device_data})
    
    assert result['status'] == 'maintenance_scheduled'
    agent.gateway.call_tool.assert_called_once()
```

### Integration Tests (Real AgentCore)
```python
def test_health_agent_with_real_agentcore():
    agent = HealthAgent()
    
    # Real AgentCore credentials
    device_data = load_local_json('DEV001')
    
    result = agent.execute({'device_metrics': device_data})
    
    assert result['status'] in ['healthy', 'escalate', 'maintenance_scheduled']
```

---

## Error Handling Pattern

```python
def _call_tool(self, tool_name, params):
    """Generic tool invocation with fallback"""
    try:
        return self.gateway.call_tool(tool_name, params)
    except Exception as e:
        self.logger.error(f"{tool_name} failed: {e}")
        return None  # Caller handles fallback
```

**Key Principle:** Tools are for ACTIONS. Data fetching is unchanged.
If tools fail, escalate locally (fallback to Week 1 behavior).

---

## Summary: Week 2 Agent Upgrade

Every agent needs:

```
1. Update source agents in `src/agents` (minimal, targeted changes)
2. Add custom GatewayClient init (`self.gateway = GatewayClient()`)
3. Keep AWS Starter Kit GatewayClient usage only in setup scripts (not runtime)
4. Implement decision flow in agents:
    - deterministic rules first
    - LLM only for ambiguous cases
    - outcomes: `schedule` | `check_parts` | `monitor_only`
5. Add tool invocation methods (`self.gateway.call_tool(...)`)
6. For `check_parts`: parts available → schedule, unavailable → create work order
7. Wrap updated agents with FastAPI services (do not rewrite business logic in wrappers)
8. Add error handling + fallback
9. Test with mock and real tools
```

**Data Source:** LOCAL in Phase 1 → S3 in Phase 2 (no code change!)  
