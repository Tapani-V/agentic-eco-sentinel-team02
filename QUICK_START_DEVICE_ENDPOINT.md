# Quick Start: Device Endpoint & LLM Testing

## TL;DR - Fastest Way to Get Started

```bash
# 1. Start services (if not already running)
docker compose up -d

# 2. Run comprehensive test
python scripts/test_device_endpoint.py

# 3. Open Swagger UI
http://localhost:8000/docs

# 4. Try a device
curl http://localhost:8000/devices/pump-001 | jq
```

---

## One-Liners for Quick Testing

### Healthy Device (Fast - 26ms, No LLM)
```bash
curl -s http://localhost:8000/devices/pump-001 | jq '.| {health_status, confidence, llm_used, processing_time_ms, action}'
```

**Output:**
```json
{
  "health_status": "healthy",
  "confidence": 1.0,
  "llm_used": false,
  "processing_time_ms": 26.35,
  "action": "MONITOR_ONLY"
}
```

### Critical Device with Rules (Medium - 300ms, No LLM)
```bash
curl -s http://localhost:8000/devices/pump-002 | jq '.| {health_status, confidence, llm_used, processing_time_ms, action, diagnosis}'
```

**Output:**
```json
{
  "health_status": "critical",
  "confidence": 0.88,
  "llm_used": false,
  "processing_time_ms": 950,
  "action": "SCHEDULE_MAINTENANCE",
  "diagnosis": "Pump valve wear - pressure unstable with high vibration"
}
```

### Emergency Device (Urgent Repair)
```bash
curl -s http://localhost:8000/devices/motor-005 | jq '.| {health_status, confidence, action, tool_results}'
```

**Output:**
```json
{
  "health_status": "critical",
  "confidence": 0.90,
  "action": "URGENT_REPAIR",
  "tool_results": {
    "create-work-order": {
      "work_order_id": "WO-f5cc0b04",
      "status": "created"
    }
  }
}
```

---

## Testing Different Scenarios

### 1. Test LLM Decision Logic
```bash
# Healthy (no LLM, confidence=1.0)
echo "1. Healthy device:"
curl -s http://localhost:8000/devices/pump-001 | jq '.| {health_status, confidence, llm_used}'

# Clear pattern (no LLM, confidence>=0.85)
echo -e "\n2. Clear pattern (high confidence):"
curl -s http://localhost:8000/devices/pump-002 | jq '.| {health_status, confidence, llm_used}'

# Would use LLM if confidence < 0.85 (see LLM_DECISION_LOGIC.md)
echo -e "\n3. Note: LLM called only if confidence < 0.85 (not in current test data)"
```

### 2. Compare All Devices
```bash
echo "Device | Health | Confidence | LLM Used | Time (ms)"
echo "-------|--------|------------|----------|----------"

for device in pump-001 pump-002 motor-005 compressor-001 generator-001; do
  curl -s http://localhost:8000/devices/$device | jq -r ".device_id + \" | \" + .health_status + \" | \" + (.confidence|tostring) + \" | \" + (.llm_used|tostring) + \" | \" + (.processing_time_ms|tostring)"
done
```

### 3. Check AWS Tool Results
```bash
# Device that created a work order
echo "Work Order Created:"
curl -s http://localhost:8000/devices/motor-005 | jq '.tool_results."create-work-order"'

# Device that scheduled maintenance
echo "Maintenance Scheduled:"
curl -s http://localhost:8000/devices/pump-002 | jq '.tool_results."schedule-maintenance".body' | jq .
```

### 4. Check Device History
```bash
# Get device summary with trends
echo "Device Summary (including 30-day trends):"
curl -s http://localhost:8000/devices/pump-001/summary | jq '.| {equipment_type, current_health, degradation_score, average_degradation_score, trend, history_count}'
```

---

## Using Swagger UI

### Step 1: Open Swagger
```
http://localhost:8000/docs
```

### Step 2: Click on GET /devices/{device_id}
- Click "Try it out"
- Enter device_id: `pump-001`
- Click "Execute"
- Examine response (see complete JSON with full analysis)

### Step 3: Check LLM Usage
In response, look for:
```json
{
  "confidence": 0.88,           // Between 0.0-1.0
  "llm_used": false,            // Would be true if < 0.85
  "processing_time_ms": 950     // Slower if LLM was used
}
```

### Step 4: Check AWS Tools
In response, look for:
```json
{
  "tool_results": {
    "schedule-maintenance": {...}  // AWS tool execution
  }
}
```

---

## Understanding the Output

### health_status
- `healthy`: All sensors normal (confidence=1.0)
- `warning`: Minor issues detected
- `alert`: Significant issues detected
- `critical`: Severe issues detected (needs action)

### confidence (0.0 to 1.0)
- `1.0`: Definitive (healthy or clear pattern)
- `0.85-0.99`: High confidence (use rules)
- `0.50-0.84`: Ambiguous (use LLM if called)
- `<0.50`: Very uncertain (recommend manual review)

### llm_used
- `false`: RULES-BASED decision (fast, cheap)
- `true`: LLM-BASED decision (slower, smart)
- Decision: Use LLM only if confidence < 0.85

### path
- `health_only`: Only HealthAgent called (~26ms)
- `full_diagnosis`: Both HealthAgent & DiagnosisAgent called (~300-900ms)

### processing_time_ms
- ~26ms: Health only (healthy device)
- ~150-300ms: Rules-based diagnosis
- ~800-1000ms: LLM-based diagnosis

### action
- `MONITOR_ONLY`: Continue monitoring (no tools)
- `SCHEDULE_MAINTENANCE`: AWS schedule-maintenance tool
- `URGENT_REPAIR`: AWS create-work-order tool
- `CHECK_PARTS_FIRST`: AWS get-spare-parts tool

---

## Batch Testing Script

Create `test_batch.sh`:
```bash
#!/bin/bash

echo "Testing all devices..."
echo ""

devices=(pump-001 pump-002 motor-005 compressor-001 generator-001)

for device in "${devices[@]}"; do
  echo "═══════════════════════════════════════"
  echo "Device: $device"
  echo "═══════════════════════════════════════"
  
  # Get response
  response=$(curl -s http://localhost:8000/devices/$device)
  
  # Extract key fields
  health=$(echo $response | jq -r '.health_status')
  confidence=$(echo $response | jq -r '.confidence')
  llm=$(echo $response | jq -r '.llm_used')
  time=$(echo $response | jq -r '.processing_time_ms' | cut -d. -f1)
  action=$(echo $response | jq -r '.action')
  
  echo "Health Status:      $health"
  echo "Confidence:         $confidence"
  echo "LLM Used:           $llm"
  echo "Processing Time:    ${time}ms"
  echo "Recommended Action: $action"
  
  # Show AWS tools if any
  tools=$(echo $response | jq -r '.tool_results | keys[]' 2>/dev/null)
  if [ ! -z "$tools" ]; then
    echo "AWS Tools:"
    for tool in $tools; do
      echo "  - $tool"
    done
  fi
  
  echo ""
done
```

Run it:
```bash
chmod +x test_batch.sh
./test_batch.sh
```

---

## Cost Analysis Quick Check

```bash
# Calculate cost for device processing

# Healthy device (frequent, no cost)
echo "Healthy device processing:"
echo "  Time: ~26ms (very fast)"
echo "  Cost: $0"
echo "  Frequency: ~80% of fleet"
echo "  Monthly cost (assuming 1000 devices daily):"
echo "  = 800 × 30 × $0 = $0"
echo ""

# Rules-based (common, no cost)
echo "Rules-based processing:"
echo "  Time: ~150-300ms"
echo "  Cost: $0"
echo "  Frequency: ~15% of fleet"
echo "  Monthly cost:"
echo "  = 150 × 30 × $0 = $0"
echo ""

# LLM-based (rare, has cost)
echo "LLM-based processing (IF confidence < 0.85):"
echo "  Time: ~800-1000ms"
echo "  Cost: $0.50-2 per call"
echo "  Frequency: ~5% of fleet"
echo "  Monthly cost (estimate):"
echo "  = 50 × 30 × $1 = $1,500"
echo ""

echo "TOTAL MONTHLY COST: ~$1,500 (worst case with max LLM calls)"
echo "BENEFIT: Prevents $10,000+ in failure costs per incident"
echo "ROI: Excellent - prevents catastrophic failures"
```

---

## Troubleshooting Commands

### Check if services are running
```bash
docker compose ps
# Should show all 3 containers as "Up"
```

### Check service logs
```bash
docker compose logs orchestrator      # Orchestrator logs
docker compose logs health-agent      # HealthAgent logs
docker compose logs diagnosis-agent   # DiagnosisAgent logs
```

### Test service connectivity
```bash
# Test each service
curl http://localhost:8000/health    # Orchestrator
curl http://localhost:8001/health    # HealthAgent
curl http://localhost:8002/health    # DiagnosisAgent

# Should all return 200 OK
```

### Check if device data is accessible
```bash
docker exec orchestrator ls data/generated/ | head -5
# Should list device JSON files
```

### Debug a specific device
```bash
curl -v http://localhost:8000/devices/pump-001 2>&1 | head -50
# Shows request/response details
```

---

## Common Questions

**Q: Why is device X taking 900ms instead of 300ms?**  
A: If confidence < 0.85, the system calls LLM (Azure OpenAI), which adds 600-800ms. This is intentional - smart analysis for ambiguous cases costs more but is more accurate.

**Q: Why is llm_used showing false when confidence < 0.85?**  
A: Current test data has all clear patterns (confidence ≥ 0.85). LLM would be called if we had truly ambiguous data (see LLM_DECISION_LOGIC.md for explanation).

**Q: How do I test with LLM enabled?**  
A: Create device data with ambiguous sensor patterns that don't match any known equipment profile. LLM will be automatically invoked.

**Q: Are the AWS work orders real?**  
A: YES! The system uses real AWS AgentCore Gateway with Cognito authentication. Work orders are actually created in AWS (see work_order_id in response).

**Q: How much does this cost per device per month?**  
A: Most devices: $0 (health_only path). With LLM for ambiguous cases: ~$1,500/month for 1000 devices, preventing $10,000+ in failures per incident.

---

## Next Steps

1. **Basic Testing**
   - Run: `python scripts/test_device_endpoint.py`
   - Open: `http://localhost:8000/docs`

2. **Advanced Testing**
   - Create custom device data (POST /process)
   - Monitor AWS tool results
   - Check processing times

3. **Production Readiness**
   - Deploy to AWS ECS
   - Set up monitoring
   - Configure alerts

4. **Optimization**
   - Tune LLM threshold (currently 0.85)
   - Add more equipment patterns
   - Monitor cost vs accuracy tradeoff

---

**Quick Reference:**
- Healthy device: ~26ms, $0, no LLM
- Clear pattern: ~300ms, $0, no LLM  
- Ambiguous: ~900ms, $0.50-2, uses LLM
- Documentation: See DEVICE_ENDPOINT_GUIDE.md, LLM_DECISION_LOGIC.md, ARCHITECTURE_DIAGRAMS.md
