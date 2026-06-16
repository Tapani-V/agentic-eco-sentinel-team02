#!/bin/bash

# Docker Compose + End-to-End Testing Runner
# Usage: ./run_e2e_tests.sh [build|test|clean|logs]

set -e

PROJECT_DIR="/home/skroy/AGENTIC_AI_POC_Phase3_1"
VENV_PATH="$PROJECT_DIR/venv"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Commands
build() {
    print_header "Building Docker Images"
    cd "$PROJECT_DIR"
    docker-compose build --no-cache
    print_success "Docker images built successfully"
}

start() {
    print_header "Starting Services"
    cd "$PROJECT_DIR"
    docker compose up -d --build
    
    print_info "Waiting for services to be healthy..."
    sleep 5
    
    # Check health
    print_info "Checking service health..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1 && \
           curl -s http://localhost:8001/health > /dev/null 2>&1 && \
           curl -s http://localhost:8002/health > /dev/null 2>&1; then
            print_success "All services healthy!"
            return 0
        fi
        echo -n "."
        sleep 1
    done
    
    print_error "Services not healthy after 30 seconds"
    docker-compose logs
    return 1
}

health_check() {
    print_header "Health Check"
    
    echo "Orchestrator (Port 8000):"
    curl -s http://localhost:8000/health | jq . || echo "⚠ Not responding"
    
    echo -e "\nHealthAgent (Port 8001):"
    curl -s http://localhost:8001/health | jq . || echo "⚠ Not responding"
    
    echo -e "\nDiagnosisAgent (Port 8002):"
    curl -s http://localhost:8002/health | jq . || echo "⚠ Not responding"
}

test_services() {
    print_header "Running End-to-End Tests"
    
    cd "$PROJECT_DIR"
    
    # Activate venv
    if [ ! -d "$VENV_PATH" ]; then
        print_error "Virtual environment not found at $VENV_PATH"
        return 1
    fi
    
    source "$VENV_PATH/bin/activate"
    
    # Run tests
    print_info "Executing test suite..."
    python tests/test_e2e_all_stories.py
    
    local exit_code=$?
    deactivate
    
    if [ $exit_code -eq 0 ]; then
        print_success "All tests passed!"
    else
        print_error "Some tests failed (exit code: $exit_code)"
    fi
    
    return $exit_code
}

logs() {
    print_header "Service Logs"
    cd "$PROJECT_DIR"
    docker compose logs -f
}

stop() {
    print_header "Stopping Services"
    cd "$PROJECT_DIR"
    docker-compose down
    print_success "Services stopped"
}

clean() {
    print_header "Cleaning Up"
    cd "$PROJECT_DIR"
    docker compose down -v --rmi all
    print_success "Cleanup complete"
}

ps_status() {
    print_header "Service Status"
    cd "$PROJECT_DIR"
    docker-compose ps
}

# Main
main() {
    case "${1:-test}" in
        build)
            build
            ;;
        start)
            start
            ;;
        test)
            start && health_check && test_services
            ;;
        health)
            health_check
            ;;
        logs)
            logs
            ;;
        stop)
            stop
            ;;
        clean)
            clean
            ;;
        ps)
            ps_status
            ;;
        *)
            echo "Usage: $0 [build|start|test|health|logs|stop|clean|ps]"
            echo ""
            echo "Commands:"
            echo "  build   - Build Docker images"
            echo "  start   - Start all services"
            echo "  test    - Start services and run end-to-end tests"
            echo "  health  - Check service health"
            echo "  logs    - Stream service logs"
            echo "  stop    - Stop all services"
            echo "  clean   - Remove all containers, images, volumes"
            echo "  ps      - Show running containers"
            echo ""
            echo "Default: test (start + health + test)"
            exit 1
            ;;
    esac
}

main "$@"
