# 🌍 Agentic-Eco-Sentinel Dashboard v2.0

Professional equipment monitoring dashboard with **real agent-driven insights** from your multi-agent orchestrator.

## 🎯 What's New in v2.0

### ✨ Major Updates
- **Real Orchestrator Integration**: 100% connected to your multi-agent system (no mock data!)
- **Professional UI**: Gradient backgrounds, enterprise colors, responsive design with globe icon 🌍
- **Structured Logging**: Color-coded console output with detailed debugging
- **Async Performance**: FastAPI with async/await for concurrent requests
- **Client-Focused**: Shows insights, confidence, recommendations (not internal agent details)
- **Production Ready**: Error handling, timeouts, retries, health checks

### 📊 Connected to Your System
- **Synthetic Device Data**: Real data from `data/generated/` (17 devices across 4 types)
- **Multi-Agent Orchestrator**: Fetches device health, degradation, and agent analysis
- **Health Agent**: Analyzes device status (healthy/warning/critical)
- **Diagnosis Agent**: Provides deeper analysis for problematic devices
- **Real Insights**: Shows recommendations with confidence levels

## 🚀 Quick Start

### Prerequisites
```bash
# Required
python 3.9+
orchestrator service (port 8000) running
device data in data/generated/
```

### Installation

```bash
cd src/dashboard
pip install -r requirements.txt
python app.py
```

**Dashboard available at**: http://localhost:8080

## 📊 Dashboard Tabs

### 1. 📊 Overview
- Fleet Health KPIs (healthy, warning, critical counts)
- Status Distribution Chart (doughnut)
- 7-Day Trend Chart (line)
- Real data from orchestrator `/devices` endpoint

### 2. 📱 Devices  
- Full device list with real health data
- Equipment types: PUMP, MOTOR, COMPRESSOR, GENERATOR
- Degradation scores from orchestrator
- Interactive device cards with health bars

### 3. 🚨 Alerts
- Active alerts based on device health states
- Severity filtering (critical, high)
- Sorted by urgency
- Real-time generation from device health

### 4. 🔧 Maintenance
- Maintenance schedule based on degradation
- Work orders with priority levels
- Preventive maintenance recommendations
- Spare parts tracking

### 5. 📈 Analytics
- Degradation trends
- Equipment type analysis  
- ROI metrics
- Failure predictions

## 🏗️ Architecture

### Data Sources

```
Your Multi-Agent System:
├── data/generated/        ← 17 synthetic devices (pump-001, motor-023, etc.)
├── orchestrator:8000      ← Main API endpoint
│   ├── Health Agent:8001
│   ├── Diagnosis Agent:8002
│   └── LangGraph Workflow
│
Connected by Dashboard:
├── /api/fleet-summary     ← KPI aggregation
├── /api/devices           ← Device list + real health data
├── /api/devices/{id}      ← Device detail + readings
├── /api/alerts            ← Alert generation from health states
├── /api/maintenance/*     ← Maintenance based on degradation
└── /api/analytics/*       ← Trend & ROI analysis
```

### Real API Integration

All endpoints fetch **live data**:

```python
# Example: Fleet Summary
async def fleet_summary():
    devices_data = await orchestrator.get("/devices")  # Real call!
    devices = devices_data.get('devices', [])
    
    # Calculate from real data
    healthy = sum(1 for d in devices if d.get('health_state') == 'healthy')
    warning = sum(1 for d in devices if d.get('health_state') == 'warning')
    critical = sum(1 for d in devices if d.get('health_state') == 'critical')
    
    return {
        "total_devices": len(devices),
        "healthy_devices": healthy,
        "warning_devices": warning,
        "critical_devices": critical,
        "fleet_health_percent": (healthy / len(devices) * 100)
    }
```

## 🔧 Configuration

### Environment Variables

```bash
# Orchestrator Connection
ORCHESTRATOR_URL=http://localhost:8000          # Your orchestrator
ORCHESTRATOR_TIMEOUT=30                          # API timeout seconds

# Dashboard Server
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8080

# Logging
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR

# Refresh Intervals (seconds)
KPI_REFRESH_INTERVAL=30         # Dashboard front-end auto-refresh
DEVICE_REFRESH_INTERVAL=60
ALERT_REFRESH_INTERVAL=20
ANALYTICS_REFRESH_INTERVAL=300  # 5 minutes
```

### Create `.env` File

```bash
cat > src/dashboard/.env << EOF
ORCHESTRATOR_URL=http://localhost:8000
DASHBOARD_PORT=8080
LOG_LEVEL=INFO
EOF
```

## 📝 Logging

### Color-Coded Console Output

```
[2026-06-23 15:30:45] DASHBOARD     🚀 AGENTIC-ECO-SENTINEL DASHBOARD STARTING
[2026-06-23 15:30:45] DASHBOARD     📡 Orchestrator Service: http://localhost:8000
[2026-06-23 15:30:45] DASHBOARD     🌐 Dashboard UI:         http://0.0.0.0:8080
[2026-06-23 15:30:45] DASHBOARD.API 📊 Fleet summary requested
[2026-06-23 15:30:45] ORCHESTRATOR_CLIENT 🔗 GET /devices
[2026-06-23 15:30:45] ORCHESTRATOR_CLIENT ✅ /devices - 200 OK
[2026-06-23 15:30:45] DASHBOARD.API ✅ Fleet: 15/17 healthy, 1 warning, 1 critical
```

### Enable Debug Logging

```bash
LOG_LEVEL=DEBUG python app.py
```

## 🎨 Visual Design

### Color Scheme (Enterprise Professional)
- **Primary**: Blue (#1e40af) - Main interactive elements
- **Secondary**: Teal (#0f766e) - Accents, gradients
- **Success**: Green (#10b981) - Healthy status
- **Warning**: Amber (#f59e0b) - Warning alerts
- **Critical**: Red (#dc2626) - Critical issues
- **Gradient Background**: Purple to Lavender (modern, professional)

### UI Components
- **Header**: Globe icon + gradient title, refresh button, live indicator
- **KPI Cards**: Color-coded, animated status dots
- **Charts**: Interactive doughnut and line charts
- **Device Cards**: Health bars with degradation visualization
- **Alerts**: Severity badges, priority sorting
- **Responsive**: Works on desktop, tablet, mobile

## 🔌 API Endpoints

### Fleet Summary
```
GET /api/fleet-summary
```
Returns: KPI metrics from orchestrator device list

### Devices
```
GET /api/devices?equipment_type=PUMP&health_status=critical&skip=0&limit=50
```
Returns: Real device data with pagination and filtering

### Device Detail
```
GET /api/devices/{device_id}
```
Returns: Current readings, health, degradation, agent analysis

### Alerts
```
GET /api/alerts?severity=critical
```
Returns: Active alerts derived from health states

### Maintenance
```
GET /api/maintenance/schedule
```
Returns: Work orders based on degradation scores

### Analytics
```
GET /api/analytics/overview
GET /api/analytics/trends?period=7d
```
Returns: Trends, metrics, ROI data

### Status
```
GET /api/status
GET /health
```
Returns: Service and orchestrator connectivity status

## 🐳 Docker Deployment

### Build & Run

```bash
# Build image
docker build -f Dockerfile.dashboard -t dashboard:v2.0 .

# Run container
docker run -p 8080:8080 \
  -e ORCHESTRATOR_URL=http://orchestrator:8000 \
  dashboard:v2.0
```

### Docker Compose

```yaml
services:
  orchestrator:
    image: orchestrator:latest
    ports:
      - "8000:8000"
  
  health-agent:
    image: health-agent:latest
    ports:
      - "8001:8001"
  
  diagnosis-agent:
    image: diagnosis-agent:latest
    ports:
      - "8002:8002"
  
  dashboard:
    build: ./src/dashboard
    ports:
      - "8080:8080"
    environment:
      ORCHESTRATOR_URL: http://orchestrator:8000
      LOG_LEVEL: INFO
    depends_on:
      - orchestrator
```

## 🧪 Testing

### Health Check
```bash
curl http://localhost:8080/health
```

### Fleet Summary
```bash
curl http://localhost:8080/api/fleet-summary | jq
```

### Devices (Real Data!)
```bash
curl http://localhost:8080/api/devices?limit=5 | jq
```

### Alerts
```bash
curl http://localhost:8080/api/alerts | jq
```

### Service Status
```bash
curl http://localhost:8080/api/status | jq
```

## 📁 Project Structure

```
src/dashboard/
├── app.py                    # FastAPI app with logging
├── config.py                 # Pydantic config (environment vars)
├── requirements.txt          # Dependencies
├── README.md                 # This file
│
├── routes/
│   ├── __init__.py
│   └── api.py               # Real orchestrator API client
│
├── templates/
│   └── index.html           # Professional UI (gradients, charts)
│
└── static/
    └── images/              # Assets (placeholder)
```

## 🛠️ Development

### Adding New Features

#### New API Endpoint
```python
# routes/api.py
@router.get("/my-endpoint")
async def my_endpoint():
    logger.info("🔍 My endpoint called")
    data = await orchestrator.get("/some-path")
    if not data:
        raise HTTPException(status_code=503, detail="Unavailable")
    return {"data": data}
```

#### Calling from Frontend
```javascript
// templates/index.html
const response = await fetch('/api/my-endpoint');
const data = await response.json();
```

### Styling Guidelines
- All CSS inline in `index.html` (`:root` variables)
- Use CSS custom properties for colors
- Responsive: 1200px, 768px, 480px breakpoints
- Smooth transitions (0.3s ease)

## ⚠️ Troubleshooting

### "Orchestrator unavailable"
```bash
# Check if orchestrator is running
curl http://localhost:8000/health

# Check configuration
echo $ORCHESTRATOR_URL
```

### "Cannot connect"
```bash
# Verify network connectivity
ping localhost
netstat -an | grep 8000

# Check if firewall blocks port
sudo ufw allow 8000
```

### Charts not showing
```bash
# Check browser console (F12)
# Verify Chart.js CDN is accessible
# Check for JavaScript errors
```

### Slow responses
```bash
# Increase timeout
ORCHESTRATOR_TIMEOUT=60

# Check orchestrator performance
curl -w "@- " http://localhost:8000/devices
```

## 📞 Support

1. **Check logs**: `LOG_LEVEL=DEBUG python app.py`
2. **Test connectivity**: `curl http://localhost:8080/api/status`
3. **Review orchestrator**: Verify `/devices` endpoint works
4. **Browser console**: Check for frontend errors (F12)

## 📚 Related Documentation

- **Design Spec**: `DASHBOARD_DESIGN_v1.0.md`
- **Implementation Guide**: `dashboard_implementation.md`
- **Orchestrator Docs**: `src/services/orchestrator/`

## 📋 Changelog

### v2.0.0 (June 23, 2026)
- ✨ **Real orchestrator integration** (removed all mock data)
- ✨ **Professional UI** with gradients and globe icon
- ✨ **Structured logging** with color output
- ✨ **Async architecture** for better performance
- ✨ **Client-focused** insights (confidence, recommendations)
- ✨ **Production deployment** ready

### v1.0.0
- Initial version with mock data

---

**🌍 Agentic-Eco-Sentinel Dashboard v2.0**  
*Professional equipment monitoring powered by multi-agent AI*

Built for the AGENTIC_AI_POC_Phase3_1 project
