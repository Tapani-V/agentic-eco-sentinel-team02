# Docker + End-to-End Testing Quick Start

**Goal:** Run all 3 services locally and test 4 real-world stories.

---

## Prerequisites

✅ All services built and ready:
- HealthAgent (Port 8001)
- DiagnosisAgent (Port 8002) 
- Orchestrator (Port 8000)

✅ `.agentcore.env` configured with AWS credentials

---

## Step 1: Start All 3 Services with Docker Compose

```bash
# From project root
cd /home/skroy/AGENTIC_AI_POC_Phase3_1

# Build and start all 3 services (detached)
docker-compose up -d --build

# Verify all services are running
docker-compose ps

# Expected output:
# NAME              STATUS              PORTS
# orchestrator      Up (healthy)        0.0.0.0:8000->8000/tcp
# diagnosis-agent   Up (healthy)        0.0.0.0:8002->8002/tcp
# health-agent      Up (healthy)        0.0.0.0:8001->8001/tcp
```

---

## Step 2: Check Service Health

```bash
# Quick health check (3-in-1)
curl http://localhost:8000/health && echo "✓ Orchestrator"
curl http://localhost:8001/health && echo "✓ HealthAgent"
curl http://localhost:8002/health && echo "✓ DiagnosisAgent"

# If all 3 return 200 OK, you're ready to test!
```

---

## Step 3: Run End-to-End Tests (4 Stories)

```bash
# Activate venv first
source venv/bin/activate

# Run all 4 story tests
python tests/test_e2e_all_stories.py

# Expected output:
# ✓ Story 1: Happy Path (Device is fine)
# ✓ Story 2: Simple Issue (Valve wear detected)
# ✓ Story 3: Ambiguous (Bearing wear - needs LLM + parts check)
# ✓ Story 4: Emergency (Critical pump failure)
```

---

## Step 4: Manual Testing (Optional)

### Test Story 1: Happy Path (Healthy Device)

```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "pump-001",
    "equipment_type": "PUMP",
    "current_reading": {
      "readings": {
        "temperature": {
          "value": 72,
          "unit": "°C",
          "normal_range": [20, 95]
        },
        "vibration": {
          "value": 2.1,
          "unit": "mm/s",
          "normal_range": [0, 3]
        },
        "pressure": {
          "value": 4.2,
          "unit": "bar",
          "normal_range": [4, 5]
        },
        "flow": {
          "value": 850,
          "unit": "L/min",
          "normal_range": [800, 900]
        }
      }
    }
  }'

# Expected: health_status="healthy", no action taken
```

### Test Story 4: Emergency (Critical Device)

```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "pump-002",
    "equipment_type": "PUMP",
    "current_reading": {
      "readings": {
        "temperature": {
          "value": 98,
          "unit": "°C",
          "normal_range": [20, 95]
        },
        "vibration": {
          "value": 5.2,
          "unit": "mm/s",
          "normal_range": [0, 3]
        },
        "pressure": {
          "value": 7.5,
          "unit": "bar",
          "normal_range": [4, 5]
        },
        "flow": {
          "value": 200,
          "unit": "L/min",
          "normal_range": [800, 900]
        }
      }
    }
  }'

# Expected: 
# - health_status="critical"
# - action_taken="work_order_created"
# - work_order_id returned from MCP tool
```

---

## Step 5: Monitor Logs (Optional)

```bash
# Watch all services in real-time
docker-compose logs -f

# Or watch specific service
docker-compose logs -f orchestrator

# Press Ctrl+C to stop
```

---

## Troubleshooting

### Services won't start

```bash
# Check for port conflicts
lsof -i :8000
lsof -i :8001
lsof -i :8002

# If ports are in use, kill the process or change ports in docker-compose.yml
kill -9 <PID>
```

### Service is unhealthy

```bash
# Check service logs
docker-compose logs health-agent
docker-compose logs diagnosis-agent
docker-compose logs orchestrator

# Rebuild and restart
docker-compose down
docker-compose up -d --build
```

### AWS credentials not working

```bash
# Verify .agentcore.env is present
cat .agentcore.env

# Check it's loaded in containers
docker-compose exec orchestrator env | grep COGNITO

# If missing, update and restart
docker-compose restart orchestrator
```

---

## Clean Up

```bash
# Stop all services
docker-compose down

# Remove images and volumes
docker-compose down -v

# Remove everything (including images)
docker-compose down --rmi all
```

---

## Expected Test Results

| Story | Device | Health Status | Action | Time |
|-------|--------|---------------|--------|------|
| **1: Happy** | Healthy pump | `healthy` | None | ~80ms |
| **2: Simple** | Compressor (valve wear) | `warning` | `schedule_maintenance` | ~200ms |
| **3: Ambiguous** | Motor (unclear) | `warning` | `check_parts_first` + LLM | ~450ms |
| **4: Critical** | Pump failure | `critical` | `create_work_order` | ~120ms |

---

## Next Steps

- ✅ Services running locally
- ✅ E2E tests passing
- ⬜ Deploy to AgentCore Runtime (AWS)
- ⬜ Set up continuous monitoring
- ⬜ Integrate with real device data streams

