#!/bin/bash

# Pre-Flight Check: Verify all components are ready for E2E testing

PROJECT_DIR="/home/skroy/AGENTIC_AI_POC_Phase3_1"
CHECKS_PASSED=0
CHECKS_FAILED=0

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((CHECKS_PASSED++))
}

print_fail() {
    echo -e "${RED}✗${NC} $1"
    ((CHECKS_FAILED++))
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check files exist
print_header "Checking File Structure"

files_to_check=(
    "src/agents/health_agent.py"
    "src/agents/diagnosis_agent.py"
    "src/gateway/client.py"
    "src/graph/workflow.py"
    "src/services/orchestrator/app.py"
    "src/services/health_agent/app.py"
    "src/services/diagnosis_agent/app.py"
    "deployment/docker-compose/orchestrator.Dockerfile"
    "deployment/docker-compose/health_agent.Dockerfile"
    "deployment/docker-compose/diagnosis_agent.Dockerfile"
    "docker-compose.yml"
    "tests/test_e2e_all_stories.py"
    ".agentcore.env"
)

for file in "${files_to_check[@]}"; do
    if [ -f "$PROJECT_DIR/$file" ]; then
        print_pass "$file exists"
    else
        print_fail "$file MISSING"
    fi
done

# Check directories exist
print_header "Checking Directories"

dirs_to_check=(
    "src/agents"
    "src/services"
    "src/services/orchestrator"
    "src/services/health_agent"
    "src/services/diagnosis_agent"
    "tests"
)

for dir in "${dirs_to_check[@]}"; do
    if [ -d "$PROJECT_DIR/$dir" ]; then
        print_pass "$dir exists"
    else
        print_fail "$dir MISSING"
    fi
done

# Check Python environment
print_header "Checking Python Environment"

if [ -d "$PROJECT_DIR/venv" ]; then
    print_pass "Virtual environment exists"
    
    # Check if requirements are installed
    if "$PROJECT_DIR/venv/bin/pip" show fastapi > /dev/null 2>&1; then
        print_pass "FastAPI installed"
    else
        print_warning "FastAPI not installed (will install on first run)"
    fi
else
    print_fail "Virtual environment missing (run: python -m venv venv)"
fi

# Check Docker
print_header "Checking Docker"

if command -v docker &> /dev/null; then
    print_pass "Docker installed"
    
    # Check Docker daemon
    if docker info > /dev/null 2>&1; then
        print_pass "Docker daemon running"
    else
        print_fail "Docker daemon not running (run: docker-compose up)"
    fi
else
    print_fail "Docker not installed"
fi

if command -v docker-compose &> /dev/null; then
    print_pass "Docker Compose installed"
else
    print_fail "Docker Compose not installed"
fi

# Check configuration files
print_header "Checking Configuration"

if [ -f "$PROJECT_DIR/.agentcore.env" ]; then
    print_pass ".agentcore.env exists"
    
    # Check for required variables
    if grep -q "COGNITO_APP_CLIENT_ID" "$PROJECT_DIR/.agentcore.env"; then
        print_pass "COGNITO_APP_CLIENT_ID configured"
    else
        print_warning "COGNITO_APP_CLIENT_ID not set"
    fi
else
    print_fail ".agentcore.env missing (copy from .agentcore.env.team01.example)"
fi

# Check docker-compose configuration
print_header "Checking Docker Compose Configuration"

if grep -q "orchestrator" "$PROJECT_DIR/docker-compose.yml"; then
    print_pass "Orchestrator service defined"
else
    print_fail "Orchestrator service not found in docker-compose.yml"
fi

if grep -q "health-agent" "$PROJECT_DIR/docker-compose.yml"; then
    print_pass "HealthAgent service defined"
else
    print_fail "HealthAgent service not found in docker-compose.yml"
fi

if grep -q "diagnosis-agent" "$PROJECT_DIR/docker-compose.yml"; then
    print_pass "DiagnosisAgent service defined"
else
    print_fail "DiagnosisAgent service not found in docker-compose.yml"
fi

# Check test files
print_header "Checking Test Files"

if [ -f "$PROJECT_DIR/tests/test_e2e_all_stories.py" ]; then
    if grep -q "story_1_happy_path" "$PROJECT_DIR/tests/test_e2e_all_stories.py"; then
        print_pass "Story 1 test defined"
    else
        print_fail "Story 1 test not found"
    fi
    
    if grep -q "story_4_emergency" "$PROJECT_DIR/tests/test_e2e_all_stories.py"; then
        print_pass "Story 4 test defined"
    else
        print_fail "Story 4 test not found"
    fi
else
    print_fail "Test file missing"
fi

# Summary
print_header "Pre-Flight Check Summary"

total=$((CHECKS_PASSED + CHECKS_FAILED))
echo "Passed: $CHECKS_PASSED/$total"
echo "Failed: $CHECKS_FAILED/$total"

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! Ready to run tests.${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Start services: docker-compose up -d --build"
    echo "2. Check health: curl http://localhost:8000/health"
    echo "3. Run tests: python -m pytest tests/ -v"
    exit 0
else
    echo -e "${RED}✗ Some checks failed. Please fix issues above.${NC}"
    exit 1
fi
