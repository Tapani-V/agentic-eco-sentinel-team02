"""
FastAPI Lambda handler for the team01-orchestrator-api API Gateway.

Sits in front of lambda_orchestrator_handler and exposes a REST API
that CloudFront and the React dashboard consume:
    GET  /api/fleet-summary
    GET  /api/devices
    GET  /api/devices/{device_id}
    GET  /api/devices/{device_id}/summary
    GET  /api/health
    POST /api/orchestrate  (proxied to the original handler)

Deployed via Mangum as an AWS Lambda behind the {proxy+} route on
the team01-orchestrator-api REST API Gateway.
"""

import json
import os
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

# Import the original orchestrator handler functions
from lambda_orchestrator_handler import (
    invoke_orchestrator_action,
    invoke_orchestrator_agent,
    parse_api_gateway_event,
)

logger = logging.getLogger("API_GW_HANDLER")
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(title="Eco-Sentinel Orchestrator API", root_path="/prod")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------
@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "healthy"}


# ---------------------------------------------------------------------------
# GET /devices
# ---------------------------------------------------------------------------
@app.get("/devices")
@app.get("/api/devices")
async def list_devices():
    result = invoke_orchestrator_action(action="list_devices")
    body = _unwrap(result)
    return body


# ---------------------------------------------------------------------------
# GET /devices/{device_id}
# ---------------------------------------------------------------------------
@app.get("/devices/{device_id}")
@app.get("/api/devices/{device_id}")
async def get_device(device_id: str):
    result = invoke_orchestrator_action(action="get_device", device_id=device_id)
    body = _unwrap(result)
    if "error" in body:
        raise HTTPException(status_code=body.get("statusCode", 404), detail=body["error"])
    return body


# ---------------------------------------------------------------------------
# GET /devices/{device_id}/summary
# ---------------------------------------------------------------------------
@app.get("/devices/{device_id}/summary")
@app.get("/api/devices/{device_id}/summary")
async def get_device_summary(device_id: str):
    result = invoke_orchestrator_action(action="get_device_summary", device_id=device_id)
    body = _unwrap(result)
    if "error" in body:
        raise HTTPException(status_code=body.get("statusCode", 404), detail=body["error"])
    return body


# ---------------------------------------------------------------------------
# GET /fleet-summary
# ---------------------------------------------------------------------------
@app.get("/fleet-summary")
@app.get("/api/fleet-summary")
async def fleet_summary():
    """Aggregate fleet KPIs from orchestrator device list."""
    logger.info("Fleet summary requested")

    devices_result = invoke_orchestrator_action(action="list_devices")
    devices_body = _unwrap(devices_result)
    devices: List[Dict[str, Any]] = devices_body.get("devices", [])

    total = len(devices)
    healthy = warning = critical = 0

    for d in devices:
        if isinstance(d, dict):
            state = d.get("health_state", "").lower()
            if state in ("healthy", "normal", "good"):
                healthy += 1
            elif state in ("warning", "degraded"):
                warning += 1
            elif state in ("critical", "failure", "failed"):
                critical += 1

    logger.info(f"Fleet: {total} devices, {healthy} healthy, {warning} warning, {critical} critical")

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_devices": total,
        "healthy_devices": healthy,
        "warning_devices": warning,
        "critical_devices": critical,
        "fleet_health_percent": round((healthy / total * 100) if total else 0),
        "degradation_trend": "stable",
        "devices_list": devices,
        "_problematic_devices": [
            d for d in devices
            if isinstance(d, dict)
            and d.get("health_state", "").lower() not in ("healthy", "normal", "good", "")
        ],
        "work_orders": [],
        "maintenance_schedules": [],
        "spare_parts": [],
    }


# ---------------------------------------------------------------------------
# POST /orchestrate
# ---------------------------------------------------------------------------
@app.post("/orchestrate")
@app.post("/api/orchestrate")
async def orchestrate(body: Dict[str, Any]):
    """Proxy to the original orchestrator agent invocation."""
    device_id = body.get("device_id")
    equipment_type = body.get("equipment_type")
    current_reading = body.get("current_reading")

    if not all([device_id, equipment_type, current_reading]):
        raise HTTPException(status_code=400, detail="Missing required fields")

    result = invoke_orchestrator_agent(
        device_id=device_id,
        equipment_type=equipment_type,
        current_reading=current_reading,
    )
    if "error" in result:
        raise HTTPException(status_code=result.get("statusCode", 500), detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# GET /status  (lightweight check the React dashboard polls)
# ---------------------------------------------------------------------------
@app.get("/status")
@app.get("/api/status")
async def status():
    return {"status": "ok", "service": "orchestrator"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _unwrap(result: Any) -> Dict[str, Any]:
    """Unwrap the {statusCode, body} envelope returned by the agent."""
    if not isinstance(result, dict):
        return {}
    if "body" in result:
        body = result["body"]
        if isinstance(body, str):
            try:
                return json.loads(body)
            except (json.JSONDecodeError, ValueError):
                return {"raw": body}
        if isinstance(body, dict):
            return body
    return result


# ---------------------------------------------------------------------------
# Mangum handler (Lambda entry point)
# ---------------------------------------------------------------------------
handler = Mangum(app, lifespan="off")
