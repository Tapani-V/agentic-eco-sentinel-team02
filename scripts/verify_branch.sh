#!/bin/bash
#
# Verify this branch end to end before the hackathon.
#
# Runs the local Docker Compose path (agents + LangGraph routing + real MCP
# tools/Gateway/Cognito/DynamoDB, via the existing test suite) by default.
# Pass --agentcore to additionally build/push/deploy/invoke the AWS Bedrock
# AgentCore Runtime path. Dashboard is a manual visual check (not automated
# here) - see the printed reminder at the end.
#
# Usage:
#   ./scripts/verify_branch.sh                 # local Docker Compose only
#   ./scripts/verify_branch.sh --agentcore      # also verify AgentCore Runtime
#   ./scripts/verify_branch.sh --agentcore --profile StandardAccess-450410489798

set -uo pipefail

RUN_AGENTCORE=false
PROFILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --agentcore) RUN_AGENTCORE=true; shift ;;
        --profile) PROFILE="$2"; shift 2 ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

declare -a RESULTS=()

record() {
    # record <label> <exit_code>
    if [ "$2" -eq 0 ]; then
        RESULTS+=("PASS|$1")
    else
        RESULTS+=("FAIL|$1")
    fi
}

section() {
    echo ""
    echo -e "${BLUE}================================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================================================================${NC}"
}

# ---------------------------------------------------------------------------
section "0. Pre-flight file/config checks"
# ---------------------------------------------------------------------------
bash scripts/preflight_check.sh
record "Pre-flight checks" $?

# ---------------------------------------------------------------------------
section "1. Local Docker Compose stack"
# ---------------------------------------------------------------------------
docker-compose up -d --build
record "docker-compose up --build" $?

echo "Waiting for services to report healthy..."
ALL_HEALTHY=false
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health >/dev/null 2>&1 && \
       curl -sf http://localhost:8001/health >/dev/null 2>&1 && \
       curl -sf http://localhost:8002/health >/dev/null 2>&1; then
        ALL_HEALTHY=true
        break
    fi
    sleep 2
done
if [ "$ALL_HEALTHY" = true ]; then
    record "orchestrator/health-agent/diagnosis-agent /health" 0
else
    record "orchestrator/health-agent/diagnosis-agent /health" 1
    echo -e "${RED}Services did not become healthy in time - check: docker-compose logs -f${NC}"
fi

echo ""
echo "Running pytest suite (agent + LangGraph routing logic)..."
python -m pytest tests/ -v
record "pytest tests/" $?

echo ""
echo "Running full 4-story e2e script (exercises MCP tools/Gateway/Cognito/DynamoDB)..."
python tests/test_e2e_all_stories.py
record "tests/test_e2e_all_stories.py (real MCP tools)" $?

# ---------------------------------------------------------------------------
if [ "$RUN_AGENTCORE" = true ]; then
    section "2. AWS Bedrock AgentCore Runtime"
    # -----------------------------------------------------------------------
    ./deployment/agentcore-runtime/build_and_push.sh
    record "build_and_push.sh (build + push ECR images)" $?

    PROFILE_ARG=()
    [ -n "$PROFILE" ] && PROFILE_ARG=(--profile "$PROFILE")
    python3 scripts/deploy_to_agentcore_boto3.py "${PROFILE_ARG[@]}"
    record "deploy_to_agentcore_boto3.py (register/update runtimes)" $?

    for agent in health_agent diagnosis_agent orchestrator; do
        python scripts/invoke_agentcore_runtime.py "$agent" ${PROFILE:+--profile "$PROFILE"}
        record "invoke_agentcore_runtime.py $agent" $?
    done
else
    echo ""
    echo -e "${YELLOW}Skipping AgentCore Runtime checks (pass --agentcore to include them).${NC}"
fi

# ---------------------------------------------------------------------------
section "Summary"
# ---------------------------------------------------------------------------
FAILED=0
for r in "${RESULTS[@]}"; do
    status="${r%%|*}"
    label="${r#*|}"
    if [ "$status" = "PASS" ]; then
        echo -e "${GREEN}PASS${NC}  $label"
    else
        echo -e "${RED}FAIL${NC}  $label"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo -e "${YELLOW}Reminder: manually spot-check the dashboard (cd src/dashboard && python app.py, http://localhost:8080).${NC}"

if [ "$FAILED" -eq 0 ]; then
    echo -e "${GREEN}All automated checks passed.${NC}"
    exit 0
else
    echo -e "${RED}$FAILED check(s) failed - see output above.${NC}"
    exit 1
fi
