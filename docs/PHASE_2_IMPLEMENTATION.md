# Phase 2 Implementation - Serverless Deployment

**Duration:** 2-3 weeks after Phase 1 complete  
**Prerequisites:** Phase 1 fully tested and stable

---

## Overview

Move agents and API from local machine to AWS serverless infrastructure.

**Before starting Phase 2:**
- Phase 1 agents tested and working
- All E2E tests passing
- Phase 1 code clean and documented
- AWS account with sufficient credits

---

## Week 1: Infrastructure Setup

### Day 1-3: Terraform Setup + IAM

**Build:**
- `terraform/variables.tf` - Configuration variables
- `terraform/providers.tf` - AWS provider setup
- `terraform/iam_roles.tf` - Lambda, AgentCore, ECS roles
- `terraform/locals.tf` - Local values (common configs)

**What happens:**
- Terraform initializes AWS provider
- IAM roles created with least privilege
- Service accounts ready for deployments

**Deliverables:**
- ✅ Terraform initialized
- ✅ AWS provider configured
- ✅ IAM roles created
- ✅ `terraform plan` shows no errors

**Next Ask:** "Generate code for Phase 2 Week 1 Day 1-3: Terraform setup and IAM"

---

### Day 4-6: API Gateway + Lambda Trigger

**Build:**
- `terraform/api_gateway.tf` - HTTP API endpoint
- `terraform/lambda_trigger.tf` - Lambda function for /analyze
- `src/handlers/api_handler.py` - Trigger function code
- Deployment automation

**What happens:**
- API Gateway routes requests to Lambda
- Lambda validates JWT, invokes AgentCore
- Returns session_id to client

**Deliverables:**
- ✅ API Gateway deployed (endpoint URL)
- ✅ Lambda Trigger deployed
- ✅ Test invocation working
- ✅ CloudWatch logs showing execution

**Next Ask:** "Generate code for Phase 2 Week 1 Day 4-6: API Gateway and Lambda Trigger"

---

### Day 7: AgentCore Runtime + Tool Registration Verification

**Build:**
- `terraform/agentcore.tf` - Bedrock AgentCore resources
- `scripts/package_agents.py` - Package agent code for AgentCore
- Agent manifests (JSON configurations)
- `scripts/verify_tool_registration.py` - Verify Phase 1 tools still registered

**What happens:**
- Agent code packaged as CloudFormation template
- Registered with AgentCore
- Tool routes configured (MCP-1, MCP-2, MCP-3, MCP-4)
- Verify all 4 tools still registered from Phase 1 deployment

**Important:** Tools registered in Phase 1 (Day 13) are reused in Phase 2. Agents need them available.

**Deliverables:**
- ✅ Agent manifests created
- ✅ AgentCore resources deployed
- ✅ Agents registered and callable
- ✅ All 4 tools verified as registered and reachable

**Next Ask:** "Generate code for Phase 2 Week 1 Day 7: AgentCore runtime setup and tool verification"

---

## Week 2: Agent Migration

### Day 8-10: Extract & Package Agents

**Build:**
- Extract agent code from Phase 1 into AgentCore format
- Create agent manifests (tool definitions)
- Update tool call interfaces
- Package as CloudFormation
- **Keep LLM configuration intact** (moves with MCP-3)

**Changes from Phase 1:**
- Agents no longer run locally
- AgentCore manages agent lifecycle and scaling
- Tool calls use same standard interface (no code changes)
- Error handling same pattern
- **LLM integration in MCP-3 unchanged**
- **Tool definitions unchanged** (registered in Phase 1, reused in Phase 2)

**No code logic changes needed:**
- Agents already call AgentCore Gateway (Phase 1 code pattern)
- AgentCore still handles tool discovery (same as Phase 1)
- Tool routing logic identical
- Memory management through memory_id: UNCHANGED
- Identity validation through Cognito: UNCHANGED

**Only difference:** Agents now run in AgentCore instead of locally (AWS manages execution, auto-scaling)

**Deliverables:**
- ✅ All agents packaged
- ✅ Tool definitions complete
- ✅ CloudFormation templates validated
- ✅ LLM configuration preserved

**Next Ask:** "Generate code for Phase 2 Week 2 Day 8-10: Extract and package agents for AgentCore"

---

### Day 11-12: Deploy & Test Agents

**Build:**
- Deploy agents to AgentCore
- Create test harness for agent calls
- Verify tool routing
- Performance benchmarks

**Testing:**
- Call each agent via API
- Verify tool calls working
- Check response times
- Monitor CloudWatch logs

**Deliverables:**
- ✅ All agents deployed
- ✅ Agent calls working via API
- ✅ Tool routing verified
- ✅ Performance acceptable

**Next Ask:** "Generate code for Phase 2 Week 2 Day 11-12: Deploy and test agents"

---

### Day 13-14: FastAPI→API Gateway Migration

**Build:**
- Update React to call API Gateway instead of FastAPI
- Migrate FastAPI endpoints to Lambda Triggers
- Update error handling
- Test all endpoints

**What changes:**
- React calls API Gateway directly
- No more FastAPI server
- Lambda handles routing
- DynamoDB results retrieval same

**Deliverables:**
- ✅ React calling API Gateway
- ✅ All endpoints working
- ✅ Error handling proper
- ✅ Integration tests passing

**Next Ask:** "Generate code for Phase 2 Week 2 Day 13-14: FastAPI to API Gateway migration"

---

## Week 3: Finalization & Deployment

### Day 15-17: Full E2E Testing

**Build:**
- E2E tests against Phase 2 infrastructure
- Load testing (simulate 100+ concurrent requests)
- Failover testing
- Rollback procedures

**Testing Scenarios:**
1. Simple request: React → API Gateway → Lambda → AgentCore → Tools
2. Complex request with long-running agent
3. Tool timeout handling
4. Concurrent requests
5. Error scenarios

**Deliverables:**
- ✅ E2E tests passing
- ✅ Load test results documented
- ✅ Performance acceptable
- ✅ Rollback procedures tested

**Next Ask:** "Generate code for Phase 2 Week 3 Day 15-17: E2E and load testing"

---

### Day 18-20: Deployment & Monitoring

**Build:**
- CI/CD pipeline (CodeBuild → CodeDeploy)
- CloudWatch dashboards
- Alarms for errors/latency
- Cost monitoring

**Monitoring Setup:**
- Agent execution times
- Tool success rates
- Error frequency
- API latency (p50, p95, p99)
- Cost per request

**Deliverables:**
- ✅ CI/CD pipeline working
- ✅ Dashboards created
- ✅ Alarms configured
- ✅ Ready for production

**Next Ask:** "Generate code for Phase 2 Week 3 Day 18-20: Deployment and monitoring setup"

---

### Day 21: Production Launch

**Build:**
- Runbook for switching traffic
- Monitoring during switch
- Validation procedures

**Steps:**
1. **Parallel Run (24h):** Both Phase 1 and Phase 2 serving traffic
2. **Validation:** Check both systems performing correctly
3. **Switch:** Route 100% traffic to Phase 2
4. **Monitor:** First 24h intensive monitoring
5. **Shutdown:** Turn off Phase 1 when stable

**Deliverables:**
- ✅ Traffic switched to Phase 2
- ✅ All systems operational
- ✅ Monitoring active
- ✅ Ready for production

**Next Ask:** "Generate code for Phase 2 Week 3 Day 21: Production launch and verification"

---

## Terraform Commands

```bash
# Initialize Terraform
terraform init

# Plan infrastructure changes
terraform plan

# Apply infrastructure
terraform apply

# Destroy all infrastructure (use with caution!)
terraform destroy

# Get outputs (API endpoint, etc.)
terraform output
```

---

## Migration Checklist

Before Phase 2:
- [ ] Phase 1 all E2E tests passing
- [ ] Phase 1 code clean and documented
- [ ] Agents code extracted to modules
- [ ] Tool interfaces standardized
- [ ] AWS credits verified
- [ ] Team trained on Terraform
- [ ] Rollback strategy documented

During Phase 2 Deployment:
- [ ] API Gateway endpoint created
- [ ] Lambda Trigger deployed
- [ ] AgentCore agents deployed
- [ ] Tool routing verified
- [ ] E2E tests passing
- [ ] Load tests successful
- [ ] Monitoring configured
- [ ] Runbook completed

After Phase 2 Launch:
- [ ] Traffic switched (1% → 10% → 100%)
- [ ] Error rates monitored
- [ ] Response times acceptable
- [ ] Cost within budget
- [ ] 24h stability check passed
- [ ] Phase 1 shut down
- [ ] Documentation updated

---

## Cost Optimization (Phase 2)

### Reserved Capacity
- Reserve Lambda execution time (~20% savings)
- Reserve ECS Fargate (~20% savings)
- Use Compute Savings Plans (~30% savings)

### Caching
- API Gateway caching (reduces backend calls)
- Agent result caching (DynamoDB)
- Tool response caching

### Auto-scaling
- Configure Lambda concurrency
- ECS task scaling policies
- API Gateway throttling

---

## Troubleshooting

**"AgentCore agent not found"**
- Verify agent deployed: `aws bedrock list-agents`
- Check CloudFormation stack status
- Review CloudWatch logs

**"API timeout"**
- Check tool response times
- Increase Lambda timeout
- Monitor ECS task performance

**"High costs"**
- Review API call frequency
- Check tool cache hit rates
- Optimize agent execution

**"Traffic switch failed"**
- Rollback to Phase 1 via Route 53
- Debug Phase 2 in parallel
- Keep Phase 1 running during debugging

---

## Rollback Strategy

If Phase 2 has critical issues:

```bash
# Switch DNS back to Phase 1
aws route53 change-resource-record-sets \
  --hosted-zone-id $ZONE_ID \
  --change-batch file://rollback.json

# Destroy Phase 2 infrastructure
terraform destroy -auto-approve
```

**Advantages:**
- Phase 1 still running (zero downtime)
- Same DynamoDB backend
- No data loss
- Time to debug Phase 2

---

## Next Steps After Phase 2 Stable

1. **Production Hardening**
   - Add rate limiting per user
   - Implement request signing
   - Add request/response validation

2. **Advanced Features**
   - Async job processing (Step Functions)
   - WebSocket for real-time updates
   - Multi-region deployment

3. **Team Scaling**
   - Add more agents (developers in parallel)
   - Increase tool capacity
   - Handle 10x traffic

---

**Status:** Phase 2 ready when Phase 1 complete and all E2E tests passing.
