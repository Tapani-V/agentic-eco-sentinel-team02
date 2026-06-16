# Phase 2 Architecture - Serverless Agent Deployment

**Goal:** Move agents from local machine to AWS for production scalability.

---

## System Overview (Phase 2)

```
┌─────────────────────────────┐
│  INTERNET                   │
└──────────┬──────────────────┘
           │
           ▼
┌──────────────────────────┐
│  API GATEWAY             │
│  └─ /analyze endpoint    │
└──────────┬───────────────┘
           │ Trigger
           ▼
┌──────────────────────────┐
│  LAMBDA (Trigger)        │
│  ├─ Validate JWT         │
│  ├─ Create session       │
│  └─ Invoke AgentCore     │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│  AWS BEDROCK AGENTCORE RUNTIME       │
│  ├─ Supervisor Agent (managed)       │
│  ├─ Health Agent (managed)           │
│  ├─ Router Agent (managed)           │
│  └─ Diagnosis Agent (managed)        │
└──────────┬───────────────────────────┘
           │
    ┌──────┴─────────┬──────────┐
    ▼                ▼          ▼
┌─────────────┐ ┌──────────┐ ┌─────────────┐
│ Lambda      │ │ ECS      │ │ DynamoDB +  │
│ MCP-1, 2    │ │ MCP-3, 4 │ │ Cognito     │
└─────────────┘ └──────────┘ └─────────────┘
```

---

## Key Differences from Phase 1

| Aspect | Phase 1 | Phase 2 |
|--------|---------|---------|
| Agents | Local Python processes | AWS Lambda/ECS managed by AgentCore |
| API | FastAPI | API Gateway |
| Scaling | Limited to 1 machine | Auto-scales 0-1000s requests |
| Cost Model | Pay for uptime | Pay per request |
| DevOps | Simple (no IaC) | Professional (Terraform) |
| Debugging | Easy (local) | AWS CloudWatch logs |
| **LLM (MCP-3)** | **Same** | **Same (no change)** |

---

## Components

### API Gateway (New in Phase 2)

**Purpose:** Public entry point for requests

```
Client (React, mobile, curl) 
    ↓ HTTPS
API Gateway 
    ├─ Validate request format
    ├─ Rate limiting (1000 req/min)
    └─ Route to Lambda Trigger
```

**Why:** 
- Scales automatically
- Built-in rate limiting
- AWS WAF integration for security
- CloudWatch logging

### Lambda Trigger (New in Phase 2)

**Purpose:** Stateless request handler

```
Lambda Trigger Function:
1. Validate Cognito JWT token
2. Extract user_id, device_id
3. Create session_id
4. Call AgentCore invoke_agent()
5. Return session_id to client
```

**Why:**
- Stateless (always fast response)
- Runs only when needed (cost-efficient)
- No connection pooling needed
- Horizontal scaling built-in

### Bedrock AgentCore Runtime (Managed Agents)

**Purpose:** Managed agent execution - same role as Phase 1, now AWS-managed

```
AgentCore manages:
- Agent lifecycle and scaling
- Tool routing to Lambda/ECS (via registered tool endpoints)
- Conversation memory (DynamoDB)
- Identity validation (Cognito tokens)
- Error handling, timeouts, and retries
- Tool discovery (agents query available tools from Gateway)
```

**Phase 1 vs Phase 2 Comparison:**
- Phase 1: Agents run locally, call AgentCore Gateway (boto3 SDK)
- Phase 2: Agents run in AgentCore, still call Gateway for tools
- Tool schema, routing logic, memory management: **UNCHANGED**
- LLM integration in MCP-3: **UNCHANGED**

**Why:**
- AWS handles scaling
- Agents become managed workloads
- Reduced operational overhead
- Built-in monitoring
- Zero code changes to agent logic (already uses AgentCore patterns)

### Same Tools + Gateway from Phase 1

**Tools (Already Deployed in Phase 1):**
- Lambda (MCP-1, MCP-2) - Unchanged, same endpoints
- ECS (MCP-3 with GPT-4o LLM, MCP-4) - Unchanged, same endpoints
- **Tool registration with AgentCore** - Reused from Phase 1

**Infrastructure (Unchanged):**
- DynamoDB - Same table for conversation memory
- Cognito - Same user pool for authentication
- **Azure OpenAI (GPT-4o)** - Same LLM in MCP-3
- **AgentCore Gateway** - Same routing, memory, identity patterns

**Critical:** Phase 2 agents use **identical tool calling patterns** as Phase 1:
1. Agent calls: `gateway.call_tool(tool_name, inputs, memory_id)`
2. Gateway routes to registered Lambda/ECS endpoint
3. Gateway handles retry logic, timeouts, token validation
4. Results stored in DynamoDB via memory_id

The only difference: Agents now run in AgentCore instead of locally.

---

## Memory Management: DynamoDB (Phase 1-2) vs AgentCore Memory (Phase 3+)

### Current Approach (Phase 1-2): Custom DynamoDB

**Used for:**
- Conversation history storage
- Session management
- Cross-agent knowledge sharing
- Long-term interaction context

**Architecture:**
- Agents read/write to DynamoDB via AgentCore Gateway
- Custom table schema (session_id, timestamp, message)
- Pay-per-request billing
- Full control over data retention

**Managed by:** Development team

### Future Option (Phase 3+): AWS AgentCore Memory

**AWS AgentCore Memory** is a fully managed service that gives agents the ability to remember past interactions:
- Enables context-aware, personalized conversations
- Handles both short-term context and long-term knowledge retention
- No infrastructure management needed
- Native integration with Bedrock AgentCore agents

**Differences from DynamoDB:**

| Aspect | DynamoDB (Phase 1-2) | AgentCore Memory (Phase 3+) |
|--------|---------------------|---------------------------|
| **Managed by** | Development team | AWS (fully managed) |
| **Purpose** | Conversation history, session tracking | Past interactions, context awareness |
| **Short-term context** | Yes | Yes |
| **Long-term retention** | Yes | Yes |
| **Infrastructure** | We design, scale, maintain | AWS manages all |
| **Cost model** | Pay-per-request | Bedrock pricing |
| **Integration** | Via Gateway (manual) | Native to AgentCore agents |

**Recommendation:**
- **Phase 1-2:** Stick with DynamoDB (explicit control, learning opportunity)
- **Phase 3+:** Consider AgentCore Memory for reduced operational overhead
- Could replace DynamoDB OR use alongside (complementary approaches)

**Note:** AgentCore Memory is optional. If we switch to it, agents would query it directly instead of through Gateway.

---

## Data Flow

### Synchronous Request (Simple Analysis)
```
1. React: POST /analyze {device_id, metrics}
2. API Gateway: Forward to Lambda Trigger
3. Lambda Trigger: 
   - Validate JWT token
   - Create session_id
   - Invoke AgentCore
4. AgentCore runs agents (parallel execution)
5. Agents call tools (Lambda/ECS)
6. Results → DynamoDB
7. Lambda Trigger: Return {session_id}
8. React: GET /results/{session_id}
9. FastAPI: Retrieve from DynamoDB
10. React: Display results
```

**Execution Time:** ~2-10 seconds (agents run in parallel)

**Important:** Agents in AgentCore still use the same tool routing pattern as Phase 1:
- Agents call AgentCore Gateway for each tool
- Gateway handles routing to Lambda/ECS
- Gateway manages memory (DynamoDB) and identity (Cognito)
- Same tool schemas, timeouts, retry logic
- Agents remain tool-agnostic (discover tools from Gateway)

### Asynchronous Request (Long Analysis)
```
For operations >10 seconds:

1. React: POST /analyze-async
2. Lambda Trigger: Start Step Function
3. Step Function: Orchestrates long-running agents (via AgentCore)
4. Upon completion: POST to WebSocket
5. React: Receives real-time update
```

**Execution Time:** Varies (agents run sequentially as needed)

---

## Deployment Model

### Infrastructure as Code (Terraform)

```
terraform/
├── variables.tf
├── providers.tf
├── api_gateway.tf
├── lambda_trigger.tf
├── agentcore.tf
├── iam_roles.tf
└── main.tf
```

**Why Terraform:**
- Version control for infrastructure
- Repeatable deployments
- Team collaboration
- Rollback capability

### CI/CD Pipeline

```
Git Push
    ↓
CodeBuild (build agents)
    ↓
CodeDeploy (to AgentCore)
    ↓
CloudFormation (update infrastructure)
    ↓
Production Live
```

---

## Cost Model Changes

| Component | Phase 1 | Phase 2 |
|-----------|---------|---------|
| Lambda Trigger | N/A | $0.20 per million requests |
| Agents (local) | $0 | Included in AgentCore pricing |
| API Gateway | N/A | $3.50 per million requests |
| Data Transfer | Low | ~$0.09 per GB out |
| MCP-3 ECS (same) | $15-30 | $15-30 |
| Azure OpenAI (same) | $5-15 | $5-15 |
| **Total (100K reqs/month)** | **$35-80** | **$60-130** |

**Key insight:** Phase 2 scales linearly with usage (pay per request). LLM costs stay the same in both phases.

---

## Monitoring & Observability (Phase 2)

### CloudWatch Dashboards
- Agent execution times
- Tool success rates
- Error frequency
- Cost tracking

### X-Ray Tracing
- Request tracing through all components
- Latency breakdown
- Dependency mapping

### Alarms
- High error rate (>1%)
- Slow responses (>30s)
- Cost anomalies (>$200/month)
- Unused resources

---

## Migration Path from Phase 1

1. **Extract agent code** from local Python
2. **Package agents** for AgentCore (no code changes needed - agents already use AgentCore Gateway from Phase 1)
3. **Deploy infrastructure** with Terraform (API Gateway, Lambda Trigger)
4. **Register agents** with AgentCore (same agent code, now managed by AWS)
5. **Tools already registered** from Phase 1 (Lambda/ECS MCP-1 through MCP-4)
6. **Run parallel tests** (Phase 1 + Phase 2)
7. **Switch traffic** to Phase 2
8. **Monitor** for 24 hours
9. **Shut down** Phase 1

**Estimated time:** 1-2 days with no downtime

---

## Security Enhancements (Phase 2)

**Network Security**
- API Gateway + AWS WAF
- DDoS protection (AWS Shield)
- TLS 1.3 required

**Access Control**
- Cognito with MFA
- RBAC for agents
- Audit logging in CloudTrail

**Data Protection**
- Encryption in transit (TLS)
- Encryption at rest (KMS keys)
- PII data masking

**Compliance**
- HIPAA ready (if needed)
- SOC 2 audit trail
- GDPR compliance options

---

## Scaling Characteristics

### Phase 1 Limits
- ~20 concurrent requests per machine
- 1-2 GB RAM for agents
- Network bandwidth limited by ISP

### Phase 2 Unlimited
- 1000+ concurrent requests (default)
- 10000+ with warm Lambda pools
- AWS handles networking

### Example Scaling Scenarios
- 100 requests/day → Phase 1 sufficient
- 1000 requests/day → Phase 1 OK, Phase 2 recommended
- 10000+ requests/day → Phase 2 required

---

## When to Move to Phase 2

**Move when:**
- Phase 1 tested and stable
- Need 24/7 availability
- Multiple developers/teams
- Ready for production launch
- Traffic exceeds 1000 req/day

**Don't move if:**
- Still in development
- Need frequent code changes
- Single developer
- Testing not complete
- Traffic <100 req/day

---

## Fallback Strategy

**If Phase 2 has issues:**
1. Traffic switches back to Phase 1 (via Route 53)
2. No data loss (DynamoDB unchanged)
3. Agents still running locally
4. Debug Phase 2 while Phase 1 serves users

**This is possible because:**
- Same DynamoDB backend
- Same Cognito auth
- Same tool interfaces
- Stateless agents

---

**Next:** Read [PHASE_2_IMPLEMENTATION.md](PHASE_2_IMPLEMENTATION.md) when ready to deploy.
