# 🌍 Dashboard v2.0 Quick Reference

## Status: ✅ PRODUCTION READY

---

## 🚀 Quick Start (30 seconds)

```bash
cd src/dashboard
pip install -r requirements.txt
python app.py
# Visit: http://localhost:8080
```

## 📊 What It Does Now

| Before (v1.0) | After (v2.0) |
|---|---|
| ❌ Mock data | ✅ Real orchestrator data |
| ❌ Navy/slate | ✅ Gradient + Globe 🌍 |
| ❌ Basic logs | ✅ Color-coded logs 🎨 |
| ❌ Not connected | ✅ Multi-agent integrated |

## 🔌 API Endpoints (All Real!)

```bash
# KPI Dashboard
curl http://localhost:8080/api/fleet-summary

# Your 17 Devices
curl http://localhost:8080/api/devices

# Real Alerts
curl http://localhost:8080/api/alerts

# Maintenance Schedule
curl http://localhost:8080/api/maintenance/schedule

# Analytics
curl http://localhost:8080/api/analytics/overview
```

## 🎨 New Visual Features

- ✨ Gradient background (purple→lavender)
- 🌍 Globe icon in header
- 🎯 Color-coded KPI cards
- 📊 Professional charts
- 🚨 Alert severity badges
- 📱 Responsive design
- ⚡ Smooth animations

## 📝 Configuration

```bash
# Create .env file (all optional - defaults work!)
ORCHESTRATOR_URL=http://localhost:8000
DASHBOARD_PORT=8080
LOG_LEVEL=INFO  # Change to DEBUG for detailed logs
```

## 🏗️ Architecture

```
Your Devices (data/generated/)
        ↓
Orchestrator (8000)
├─ Health Agent (8001)
├─ Diagnosis Agent (8002)
└─ LangGraph Workflow
        ↓
Dashboard API (8080)
├─ /api/fleet-summary
├─ /api/devices (REAL!)
├─ /api/alerts (REAL!)
├─ /api/maintenance
└─ /api/analytics
        ↓
Beautiful UI 🎨
```

## 🔍 Verify It Works

```bash
# 1. Is orchestrator running?
curl http://localhost:8000/health
✅ Should return: {"status": "healthy"}

# 2. Is dashboard running?
curl http://localhost:8080/health
✅ Should return: {"status": "healthy"}

# 3. Can we see real devices?
curl http://localhost:8080/api/devices
✅ Should return: 17 real devices

# 4. Can we see real KPIs?
curl http://localhost:8080/api/fleet-summary
✅ Should return: Real health percentages
```

## 📊 Tabs Explained

1. **Overview 📊**: Fleet KPIs, charts, real-time metrics
2. **Devices 📱**: All 17 devices, health bars, filtering
3. **Alerts 🚨**: Real alerts from device health states
4. **Maintenance 🔧**: Work orders based on degradation
5. **Analytics 📈**: Trends, ROI, predictions

## 🐳 Docker

```bash
# Build
docker build -f Dockerfile.dashboard -t dashboard:v2.0 .

# Run
docker run -p 8080:8080 \
  -e ORCHESTRATOR_URL=http://orchestrator:8000 \
  dashboard:v2.0
```

## 🛠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| "Orchestrator unavailable" | Check: `curl http://localhost:8000/health` |
| Charts not showing | Check browser console (F12) for JS errors |
| Slow loading | Increase `API_TIMEOUT` in `.env` |
| Want more logs | Set `LOG_LEVEL=DEBUG` |

## 📚 Files

```
src/dashboard/
├── app.py                    ← FastAPI + logging
├── config.py                 ← Configuration
├── routes/api.py             ← Real orchestrator client
├── templates/index.html      ← Professional UI
├── requirements.txt          ← Dependencies
└── README.md                 ← Full documentation
```

## 🎯 What Changed

### app.py
- Added ColoredFormatter for logging
- Structured startup/shutdown events
- Better error handling

### config.py
- Added timeouts, retries, intervals
- Better documentation
- Production-ready settings

### routes/api.py (BIG CHANGE! 🔥)
- **Removed**: All mock data functions
- **Added**: OrchestratorClient class
- **Now**: Real API calls to orchestrator
- **Result**: 100% real data!

### templates/index.html (DESIGN OVERHAUL! ✨)
- **Removed**: Boring navy header
- **Added**: Gradient background + globe icon 🌍
- **New**: Professional color scheme
- **New**: Smooth animations
- **New**: Better responsive design

### README.md
- Complete rewrite for v2.0
- Architecture diagrams
- All endpoints documented
- Troubleshooting guide

## ⚡ Performance

- ✅ Async/await (concurrent requests)
- ✅ Timeouts (prevent hanging)
- ✅ Retry logic (resilience)
- ✅ Color logs (instant visibility)
- ✅ Caching ready (extensible)

## 🔐 Production Checklist

- ✅ Error handling
- ✅ Timeouts configured
- ✅ Health checks working
- ✅ Logging comprehensive
- ✅ Configuration flexible
- ✅ Documentation complete
- ✅ Docker ready
- ✅ Responsive design

## 🚦 Next Steps

1. **Run it**: `python app.py`
2. **Open it**: http://localhost:8080
3. **Click tabs**: Watch real data load
4. **Test API**: `curl http://localhost:8080/api/devices`
5. **Check logs**: See color-coded output
6. **Enjoy!** 🎉

## 📞 Quick Help

```bash
# See what's happening
LOG_LEVEL=DEBUG python app.py

# Test one endpoint
curl -s http://localhost:8080/api/fleet-summary | jq

# Check orchestrator
curl http://localhost:8000/devices | jq '.devices | length'
# Output: 17 (your real devices!)

# Monitor real-time
watch curl http://localhost:8080/api/fleet-summary
```

## 🎨 UI Preview

```
Header:
┌─────────────────────────────────────────┐
│  🌍 Agentic-Eco-Sentinel  [🔄] [⚫Live] │
└─────────────────────────────────────────┘

KPI Row:
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ ✅ 15/17 │ │ ⚠️  1    │ │ 🚨  1    │ │ 📦 17    │
│ Healthy  │ │ Warning  │ │ Critical │ │ Total    │
└──────────┘ └──────────┘ └──────────┘ └──────────┘

Tabs:
  📊 Overview | 📱 Devices | 🚨 Alerts | 🔧 Maintenance | 📈 Analytics
  ━━━━━━━━

Content:
┌──────────────────────┐  ┌──────────────────────┐
│  Device Status       │  │  7-Day Trend         │
│  ├─ Healthy: 15 🟢   │  │  ↗ Trending ↗ ↗      │
│  ├─ Warning: 1  🟡   │  │                      │
│  └─ Critical: 1 🔴   │  │                      │
└──────────────────────┘  └──────────────────────┘
```

## 💡 Pro Tips

1. **Real data**: All 17 devices from `data/generated/` are live
2. **Agent insights**: Dashboard shows Health + Diagnosis Agent analysis
3. **Color logs**: Set `LOG_LEVEL=DEBUG` to see all API calls
4. **Fast refresh**: Dashboard auto-refreshes every 30-60 seconds
5. **Extensible**: Easy to add new endpoints and charts

## 🎉 You're All Set!

Dashboard v2.0 is ready to use. Your multi-agent system data is flowing through!

**Questions?** Check [README.md](src/dashboard/README.md) or [DASHBOARD_V2_UPGRADE_SUMMARY.md](DASHBOARD_V2_UPGRADE_SUMMARY.md)

---

**Version**: 2.0.0  
**Status**: ✅ Production Ready  
**Last Updated**: June 23, 2026

🌍 Agentic-Eco-Sentinel Dashboard • Professional Equipment Monitoring
