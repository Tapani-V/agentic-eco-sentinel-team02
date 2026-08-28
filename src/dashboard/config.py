"""
Dashboard Configuration - Agentic-Eco-Sentinel

Environment-based configuration for dashboard service.
Connects to Orchestrator (port 8000) for real device data and agent analysis.

All settings can be overridden via environment variables (.env file).

Example .env:
    ORCHESTRATOR_URL=http://localhost:8000
    DASHBOARD_PORT=8080
    LOG_LEVEL=DEBUG
"""

import os
from pydantic_settings import BaseSettings
from typing import Optional


def _read_version() -> str:
    """Read version from VERSION file"""
    try:
        version_file = os.path.join(os.path.dirname(__file__), 'VERSION')
        with open(version_file, 'r') as f:
            return f.read().strip()
    except:
        return "1.0.0"


class Settings(BaseSettings):
    """Dashboard configuration settings with environment variable support"""
    
    # ========================================
    # Application Metadata
    # ========================================
    APP_NAME: str = "Agentic-Eco-Sentinel Dashboard"
    APP_VERSION: str = _read_version()
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # ========================================
    # Server Configuration
    # ========================================
    DASHBOARD_HOST: str = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    DASHBOARD_PORT: int = int(os.getenv("DASHBOARD_PORT", "8080"))
    
    # ========================================
    # Orchestrator Service Connection
    # ========================================
    # Points to the API Gateway stage root (Frankfurt), which proxies to the
    # Lambda -> Orchestrator AgentCore Runtime. No /orchestrate suffix - the
    # Lambda's routes are flat (/devices, /health, ...), confirmed via live testing.
    ORCHESTRATOR_URL: str = os.getenv("ORCHESTRATOR_URL", "https://smxdpw59j6.execute-api.eu-central-1.amazonaws.com/prod")
    ORCHESTRATOR_TIMEOUT: int = int(os.getenv("ORCHESTRATOR_TIMEOUT", "30"))
    
    # ========================================
    # Logging Configuration
    # ========================================
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # ========================================
    # Data Refresh Intervals (seconds) - PRODUCTION GRADE
    # ========================================
    # How often dashboard fetches fresh data from orchestrator
    KPI_REFRESH_INTERVAL: int = int(os.getenv("KPI_REFRESH_INTERVAL", "60"))  # 1 minute (changed from 30s)
    DEVICE_REFRESH_INTERVAL: int = int(os.getenv("DEVICE_REFRESH_INTERVAL", "60"))
    ALERT_REFRESH_INTERVAL: int = int(os.getenv("ALERT_REFRESH_INTERVAL", "20"))
    ANALYTICS_REFRESH_INTERVAL: int = int(os.getenv("ANALYTICS_REFRESH_INTERVAL", "300"))
    
    # ========================================
    # API Configuration
    # ========================================
    API_TIMEOUT: int = int(os.getenv("API_TIMEOUT", "15"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY: float = float(os.getenv("RETRY_DELAY", "0.5"))
    
    # ========================================
    # CORS Configuration
    # ========================================
    ALLOWED_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:8000",
    ]
    
    # ========================================
    # Cache Configuration - PRODUCTION GRADE
    # ========================================
    ENABLE_CACHE: bool = os.getenv("ENABLE_CACHE", "true").lower() == "true"
    CACHE_DURATION: int = int(os.getenv("CACHE_DURATION", "360"))  # 6 minutes (changed from 30s)
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields from .agentcore.env


settings = Settings()
