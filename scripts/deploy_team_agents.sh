#!/bin/bash
#
# All-in-one: build + push this team's agent images, then deploy/update them
# on AWS Bedrock AgentCore Runtime.
#
# This is just a convenience wrapper around two existing scripts - it does
# not do anything they don't already do:
#   1. deployment/agentcore-runtime/build_and_push.sh   (build ARM64 images, push to ECR tagged :$TEAM_ID)
#   2. scripts/deploy_to_agentcore_boto3.py             (create/update this team's AgentCore Runtimes)
#
# Requires TEAM_ID in .agentcore.env (see .agentcore.env.team01.example). Safe to
# re-run any time - both underlying scripts create-if-missing/update-if-exists,
# so this never touches the shared runtimes or another team's.
#
# Usage:
#   ./scripts/deploy_team_agents.sh                  # build + deploy all 3 agents
#   ./scripts/deploy_team_agents.sh health_agent      # only rebuild + redeploy one agent
#
# Run from the repository root.

set -e

if [ -f ".agentcore.env" ]; then
    # shellcheck disable=SC1091
    set -a; source .agentcore.env; set +a
fi

if [ -z "$TEAM_ID" ]; then
    echo "Error: TEAM_ID is not set. Add TEAM_ID=<yourteam> to .agentcore.env first." >&2
    exit 1
fi

AGENT="$1"

echo "================================================================================"
echo "Team '$TEAM_ID' - build + deploy agents"
[ -n "$AGENT" ] && echo "Scope: $AGENT only"
echo "================================================================================"

echo ""
echo "Step 1/2: build + push ARM64 images (tag :$TEAM_ID)"
./deployment/agentcore-runtime/build_and_push.sh "$AGENT"

echo ""
echo "Step 2/2: register/update AgentCore Runtime(s)"
if [ -n "$AGENT" ]; then
    python3 scripts/deploy_to_agentcore_boto3.py --agent "$AGENT"
else
    python3 scripts/deploy_to_agentcore_boto3.py
fi

echo ""
echo "Done. Endpoints written to agent_endpoints.${TEAM_ID}.json"
echo "Smoke-test with: python3 scripts/invoke_agentcore_runtime.py orchestrator"
