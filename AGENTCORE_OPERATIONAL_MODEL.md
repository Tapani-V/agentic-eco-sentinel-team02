# AgentCore Runtime Operational Model - Clarification

**Date**: 2026-07-10  
**Status**: Design Document  

## Quick Answer

**Will agents run indefinitely?**

🎯 **Short answer**: No, not all. It depends on the agent's scaling configuration.

- **Orchestrator Agent**: ✅ YES - runs indefinitely (minInstances=1, always-on)
- **Health Agent**: ❌ NO - scales to zero when idle
- **Diagnosis Agent**: ❌ NO - scales to zero when idle

---

## Detailed Breakdown

### Orchestrator Agent (Entry Point)

**Configuration**:
```yaml
minInstances: 1
maxInstances: 5
timeout: 60 seconds
```

**Operational Model**:
- ✅ **Always running** (1 instance minimum)
- Spins up to 5 instances under load
- Why: Needs immediate response for new requests (orchestration is synchronous)
- Cost: ~$40-50/month for 1 constantly-running instance
- Latency: < 100ms (no cold start)

**What it does**:
1. Receives incoming request from dashboard/curl
2. Routes to health_agent (might be cold start)
3. Routes to diagnosis_agent if needed (might be cold start)
4. Aggregates results
5. Returns to caller

---

### Health Agent (Worker - On-Demand)

**Configuration**:
```yaml
minInstances: 0
maxInstances: 3
timeout: 30 seconds
```

**Operational Model**:
- ❌ **Does NOT run indefinitely**
- Scales to 0 when idle (no cost)
- Spins up on-demand when orchestrator calls it
- Cost: ~$0-10/month (depends on usage)
- Latency: 2-3 seconds (cold start included)

**Lifecycle**:
```
Idle (no instances)
  ↓ (orchestrator requests health analysis)
Cold start: 2-3 seconds (pull image, initialize container)
  ↓
Running: 30 seconds max (analyze device)
  ↓
Results returned
  ↓
Idle (scale to zero after 60s no traffic)
```

---

### Diagnosis Agent (Worker - On-Demand)

**Configuration**:
```yaml
minInstances: 0
maxInstances: 3
timeout: 60 seconds
```

**Operational Model**:
- ❌ **Does NOT run indefinitely**
- Scales to 0 when idle
- Spins up when orchestrator calls it
- Cost: ~$0-10/month
- Latency: 2-3 seconds (cold start)

**Lifecycle**:
```
Idle (no instances)
  ↓ (orchestrator requests diagnosis)
Cold start: 2-3 seconds
  ↓
Running: 60 seconds max
  ├─ Root cause analysis
  └─ Call MCP tools via gateway (if action needed)
  ↓
Results returned
  ↓
Idle (scale to zero)
```

---

## Complete Request Flow & Timing

```
t=0:   Dashboard sends request to orchestrator endpoint
       (or Lambda wrapper sends device data)

t=0-100ms: Orchestrator (running, always-on) receives request

t=100ms: Orchestrator triggers health_agent
         (cold start if scaled to zero)

t=100-2300ms: Health_agent cold start
              • Container image pulled (~500ms)
              • Python dependencies initialized (~1000ms)
              • App startup (~800ms)

t=2300ms: Health_agent running, analyzes device health

t=2300-2800ms: Health analysis (500ms)

t=2800ms: Results returned to orchestrator

t=2800ms: Orchestrator checks result
          - If diagnosis needed: trigger diagnosis_agent
          - Else: return results

t=2800-5600ms: Diagnosis_agent cold start (if needed)

t=5600-15000ms: Diagnosis analysis + MCP tool calls

t=15000ms: Complete results returned to caller

Total latency: ~15 seconds (first request after idle)
Subsequent requests: ~10 seconds (health_agent already warm)
```

---

## Cost Model

**Assuming**:
- 50 device analyses per day
- Average 30 seconds compute per analysis
- AWS pricing: $0.00001667 per vCPU-second

**Monthly costs**:

| Agent | minInstances | Always Running | On-Demand | Total/Month |
|-------|--------------|----------------|-----------|-------------|
| Orchestrator | 1 | Yes | - | ~$45 (always 256 CPU) |
| Health_agent | 0 | No | Yes | ~$5 (50 requests × 30s) |
| Diagnosis_agent | 0 | No | Yes | ~$8 (50 requests × 60s) |
| **Total** | - | - | - | **~$58/month** |

**Cost optimization options**:
1. Reduce orchestrator minInstances to 0 (cold start on first request, ~3s)
2. Use API Gateway caching to reduce agent calls
3. Batch process devices (send 10 at a time)
4. Schedule batch jobs at off-peak hours

---

## Cold Start Behavior

### Why Does Health Agent Have 2-3 Second Cold Start?

When an agent instance scales from 0 to 1:

1. **Container pull** (500-800ms):
   - ECR pulls 160MB docker image
   - Decompresses and loads

2. **Python startup** (300-500ms):
   - Python interpreter initializes
   - AWS Lambda runtime boots

3. **App initialization** (1000-1500ms):
   - Import all modules (src.agents, src.utils, etc.)
   - Load Cognito credentials from env vars
   - Initialize boto3 clients (S3, Bedrock)
   - Initialize LLM provider (Azure OpenAI)
   - Start FastAPI server

4. **Ready** (total: 2-3 seconds)

### How to Reduce Cold Start?

1. **Option 1**: Increase minInstances for health_agent to 1
   - Cost: +$45/month
   - Latency: < 100ms (always warm)
   - Downside: Constant cost

2. **Option 2**: Use Python lambda layer for common code
   - Pre-compile dependencies
   - Reduce import time by 20-30%
   - Latency improvement: ~500ms

3. **Option 3**: Keep current setup (minInstances=0)
   - Cost: ~$5-8/month (minimal)
   - Latency: 2-3 seconds (acceptable)
   - Best for: Development, testing, low-traffic systems

---

## Comparison: Local Docker vs AgentCore Runtime

| Aspect | Local Docker | AgentCore Runtime |
|--------|--------------|-------------------|
| **Always running** | Yes (docker-compose up) | Configurable (minInstances) |
| **Startup time** | 0 (already running) | 2-3s (cold start) |
| **Scaling** | Manual | Automatic (based on traffic) |
| **Cost** | $0 (compute provided) | ~$58/month (example) |
| **High availability** | No (single instance) | Yes (auto-failover) |
| **Load balancing** | Manual | Automatic |

---

## Recommended Configuration

**For development/testing** (cost-conscious):
```yaml
orchestrator:
  minInstances: 1    # Always on (entry point)
  maxInstances: 3

health_agent:
  minInstances: 0    # Scale to zero (save money)
  maxInstances: 2

diagnosis_agent:
  minInstances: 0    # Scale to zero
  maxInstances: 2

Expected cost: ~$50-60/month
Expected latency: 10-15s (includes cold start)
```

**For production** (performance-focused):
```yaml
orchestrator:
  minInstances: 2    # High availability
  maxInstances: 5

health_agent:
  minInstances: 1    # Always warm
  maxInstances: 3

diagnosis_agent:
  minInstances: 1    # Always warm
  maxInstances: 3

Expected cost: ~$150-200/month
Expected latency: < 2s (no cold starts)
```

**For demonstration** (balance both):
```yaml
orchestrator:
  minInstances: 1    # Entry point always available
  maxInstances: 3

health_agent:
  minInstances: 0    # Scale to zero (dev cost)
  maxInstances: 2

diagnosis_agent:
  minInstances: 0    # Scale to zero
  maxInstances: 2

Expected cost: ~$50-60/month
Expected latency: 10-15s (acceptable for demos)
```

---

## Operational Patterns

### Pattern 1: Dashboard User Clicks "Analyze"

```
Dashboard
  ↓ (user clicks button)
REST API (via API Gateway + Lambda)
  ↓
Lambda handler (always running? depends)
  ↓
Orchestrator (minInstances=1, always on)
  ↓ (cold start 2-3s)
Health_agent (minInstances=0, scales up)
  ↓ (cold start 2-3s)
Diagnosis_agent (minInstances=0, scales up if needed)
  ↓
MCP tools (via gateway)
  ↓
Results back to dashboard

Total time: 10-15 seconds

User experience: "Analyzing..." spinner, then results
```

### Pattern 2: Scheduled Batch Processing

```
EventBridge (scheduled daily at 2 AM)
  ↓
Lambda handler (batch processor)
  ↓
For each device:
  Orchestrator (already warm from previous request)
  ↓ (< 100ms)
  Health_agent (warm after first request)
  ↓
  Results accumulated
  ↓
  Save to S3/database

Cost: Very cheap (agents stay warm, process 100s of devices)
Time: 5-10 seconds per device
```

### Pattern 3: Continuous Monitoring

```
Event source: Device health changes (S3, Kafka, SNS)
  ↓
Lambda triggered immediately
  ↓
Orchestrator (always on)
  ↓
Diagnosis_agent (scales up if needed)
  ↓
Work order created automatically

Latency: 3-5 seconds (health_agent might be cold)
Cost: Varies based on event frequency
```

---

## Next: Lambda + API Gateway Integration

### What Will Be Built

**API Gateway Endpoint**:
```
POST /orchestrate
Content-Type: application/json

{
  "device_id": "motor-004",
  "equipment_type": "MOTOR",
  "current_reading": {...}
}
```

**Lambda Handler**:
1. Receives request from API Gateway
2. Calls orchestrator agent endpoint (on AgentCore)
3. Returns results to API Gateway
4. API Gateway returns to caller

**Caller options**:
- curl (command line testing)
- Dashboard (browser)
- Other services (microservices architecture)

### Expected Experience

```bash
# Caller (curl or dashboard)
curl -X POST https://api.example.com/orchestrate \
  -H "Content-Type: application/json" \
  -d '{"device_id":"motor-004",...}'

# Response (after 10-15 seconds)
{
  "device_id": "motor-004",
  "health_status": "alert",
  "diagnosis": "Bearing degradation detected",
  "mcp_tools_used": ["get-spare-parts", "schedule-maintenance"],
  "tool_results": {...}
}
```

### Architecture

```
Caller (curl/dashboard)
  ↓ (HTTPS POST)
API Gateway (managed by AWS)
  ↓ (routes to Lambda)
Lambda Handler (runs for 60s)
  ↓ (calls agent endpoint)
AgentCore Orchestrator Runtime
  ├─ Health Agent (on-demand)
  ├─ Diagnosis Agent (on-demand)
  └─ MCP Tools (Lambda/S3)
  ↓
Lambda returns results
  ↓
API Gateway returns to caller
```

---

## Key Takeaways

✅ **Orchestrator**: Runs indefinitely (minInstances=1)  
✅ **Health/Diagnosis Agents**: Scale to zero (on-demand, minInstances=0)  
✅ **Cold start**: 2-3 seconds acceptable for most use cases  
✅ **Cost**: ~$50-60/month for development setup  
✅ **Performance**: Can be tuned by adjusting minInstances  
✅ **Architecture**: Lambda + API Gateway bridges dashboard and agents  

---

## Questions to Consider Before Next Session

1. Should we increase minInstances for health_agent to 1 for better latency?
   - Pro: No cold starts, faster response
   - Con: +$45/month extra cost

2. Should we implement caching in API Gateway?
   - Pro: Reduce duplicate agent calls
   - Con: Adds complexity, cached results may be stale

3. Should Lambda itself be always-on or on-demand?
   - Pro (always-on): < 100ms response, predictable cost
   - Con (always-on): Cost for Lambda execution
   - Recommendation: API Gateway handles invocation, Lambda only runs when called

4. How should we handle timeout scenarios?
   - What if agent takes > 60s?
   - Should we queue requests or return error?
   - Dashboard needs clear user feedback

5. Should we implement async invocation?
   - Current: Synchronous (dashboard waits for results)
   - Alternative: Async (dashboard polls for results)
   - Affects UX: wait vs. refresh pattern

---

**Status**: Ready for Phase 5 implementation (Lambda + API Gateway)  
**Estimated time**: 2-3 hours  
**Next session**: Create Lambda handlers and API Gateway endpoint
