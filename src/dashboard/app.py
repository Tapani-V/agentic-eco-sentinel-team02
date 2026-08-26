#!/usr/bin/env python3
"""
Agentic-Eco-Sentinel Dashboard - FastAPI Application

Professional device monitoring dashboard connected to multi-agent orchestrator system.
Displays device health, maintenance insights, and agent-driven recommendations.

Architecture:
    Orchestrator (FastAPI on 8000)
         ├─ Health Agent (8001)
         ├─ Diagnosis Agent (8002)
         ├─ Multi-Agent Workflow (LangGraph)
         └─ Synthetic Device Data
    
    Dashboard (FastAPI on 8080) ← THIS SERVICE
         ├─ Real-time device data fetching
         ├─ Client-focused visualization (insights, confidence, recommendations)
         └─ Professional monitoring interface

Usage:
    python -m src.dashboard.app
    Visit: http://localhost:8080
"""

import logging
import sys
from datetime import datetime
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
import os
import uvicorn

from .config import settings
from .routes import api

# ============================================================================
# STRUCTURED LOGGING SYSTEM
# ============================================================================

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[92m',       # Green
        'WARNING': '\033[93m',    # Yellow
        'ERROR': '\033[91m',      # Red
        'CRITICAL': '\033[41m',   # Red background
    }
    RESET = '\033[0m'
    
    def format(self, record):
        levelname = record.levelname
        color = self.COLORS.get(levelname, self.RESET)
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        
        # Format with colors and proper spacing
        message = f"{color}[{timestamp}]{self.RESET} {color}{levelname:8}{self.RESET} {record.name}: {record.getMessage()}"
        
        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"
        
        return message

# Setup root logger
root_logger = logging.getLogger()
root_logger.setLevel(settings.LOG_LEVEL)

# Console handler with colors
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ColoredFormatter())
root_logger.addHandler(console_handler)

# Dashboard logger
logger = logging.getLogger('DASHBOARD')
logger.setLevel(settings.LOG_LEVEL)

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title=settings.APP_NAME,
    description="Equipment monitoring dashboard with agent insights",
    version=settings.APP_VERSION,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Include API routes
app.include_router(api.router, prefix="/api", tags=["api"])


@app.get("/", name="home")
async def root(request: Request):
    """Serve main dashboard page with version and metadata"""
    logger.info("📊 Dashboard page requested")
    # This venv's Starlette (1.3.1) requires the request-first signature.
    return templates.TemplateResponse(request, "index.html", {
        "app_version": settings.APP_VERSION,
        "app_name": settings.APP_NAME,
    })


@app.get("/health", name="health_check")
async def health_check():
    """Health check endpoint with orchestrator connectivity"""
    logger.debug("🏥 Health check requested")
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "orchestrator": settings.ORCHESTRATOR_URL,
        "timestamp": datetime.now().isoformat()
    }


@app.on_event("startup")
async def startup_event():
    """Events on application startup"""
    logger.info("=" * 90)
    logger.info("🚀 AGENTIC-ECO-SENTINEL DASHBOARD STARTING")
    logger.info("=" * 90)
    logger.info(f"📡 Orchestrator Service: {settings.ORCHESTRATOR_URL}")
    logger.info(f"🌐 Dashboard UI:         http://{settings.DASHBOARD_HOST}:{settings.DASHBOARD_PORT}")
    logger.info(f"📝 Log Level:            {settings.LOG_LEVEL}")
    logger.info(f"🔄 KPI Refresh:          {settings.KPI_REFRESH_INTERVAL}s")
    logger.info(f"🔄 Device Refresh:       {settings.DEVICE_REFRESH_INTERVAL}s")
    logger.info(f"🔄 Alert Refresh:        {settings.ALERT_REFRESH_INTERVAL}s")
    logger.info("=" * 90)
    logger.info("✅ Dashboard ready to serve client-focused equipment monitoring interface")


@app.on_event("shutdown")
async def shutdown_event():
    """Events on application shutdown"""
    logger.info("⏹️  Dashboard service shutting down")
    logger.info("=" * 90)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.dashboard.app:app",
        host=settings.DASHBOARD_HOST,
        port=settings.DASHBOARD_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
