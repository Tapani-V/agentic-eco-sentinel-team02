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
from datetime import datetime, timedelta
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
# GET /alerts
# ---------------------------------------------------------------------------
@app.get("/alerts")
@app.get("/api/alerts")
async def get_alerts(severity: Optional[str] = None, skip: int = 0, limit: int = 50):
    """Generate alerts from devices with critical/warning health states."""
    devices = _get_devices_list()

    alerts = []
    for d in devices:
        if not isinstance(d, dict):
            continue
        state = d.get("health_state", "").lower()
        device_id = d.get("device_id", "unknown")
        deg = d.get("degradation_score", 0)

        if state == "critical" or state == "failure":
            alerts.append({
                "id": f"alert-{device_id}-critical",
                "device_id": device_id,
                "severity": "critical",
                "title": f"Critical: {device_id} requires immediate attention",
                "description": f"Device degradation score {deg:.2f}. Immediate inspection recommended.",
                "timestamp": d.get("timestamp"),
                "action_required": True,
            })
        elif state == "warning" or state == "degraded":
            alerts.append({
                "id": f"alert-{device_id}-warning",
                "device_id": device_id,
                "severity": "high",
                "title": f"Warning: {device_id} anomaly detected",
                "description": f"Device degradation score {deg:.2f}. Schedule maintenance soon.",
                "timestamp": d.get("timestamp"),
                "action_required": False,
            })

    if severity:
        alerts = [a for a in alerts if a["severity"] == severity.lower()]

    return {
        "alerts": alerts[skip : skip + limit],
        "total": len(alerts),
        "critical_count": sum(1 for a in alerts if a["severity"] == "critical"),
        "high_count": sum(1 for a in alerts if a["severity"] == "high"),
        "timestamp": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /maintenance-schedule
# ---------------------------------------------------------------------------
@app.get("/maintenance-schedule")
@app.get("/api/maintenance-schedule")
async def get_maintenance_schedule():
    """Generate maintenance schedules from devices needing attention."""
    devices = _get_devices_list()

    schedules = []
    for d in devices:
        if not isinstance(d, dict):
            continue
        state = d.get("health_state", "").lower()
        device_id = d.get("device_id", "unknown")
        equip = d.get("equipment_type", "UNKNOWN")
        deg = d.get("degradation_score", 0)

        if state in ("critical", "failure"):
            schedules.append({
                "device_id": device_id,
                "priority": "urgent",
                "reason": f"Critical health state — degradation {deg:.2f}",
                "start_date": datetime.utcnow().isoformat(),
                "duration_hours": 4,
                "estimated_cost": 2500.0,
                "parts_needed": [f"{equip.lower()}-repair-kit"],
            })
        elif state in ("warning", "degraded"):
            schedules.append({
                "device_id": device_id,
                "priority": "scheduled",
                "reason": f"Warning state — degradation {deg:.2f}",
                "start_date": datetime.utcnow().isoformat(),
                "duration_hours": 2,
                "estimated_cost": 800.0,
                "parts_needed": [],
            })

    urgent = sum(1 for s in schedules if s["priority"] == "urgent")
    scheduled = sum(1 for s in schedules if s["priority"] == "scheduled")
    total_cost = sum(s["estimated_cost"] for s in schedules)

    schedules.sort(key=lambda s: (0 if s["priority"] == "urgent" else 1, s["start_date"]))

    return {
        "schedules": schedules,
        "total": len(schedules),
        "by_priority": {"urgent": urgent, "scheduled": scheduled},
        "total_estimated_cost": round(total_cost, 2),
        "timestamp": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /work-orders
# ---------------------------------------------------------------------------
@app.get("/work-orders")
@app.get("/api/work-orders")
async def get_work_orders(status: Optional[str] = None, skip: int = 0, limit: int = 50):
    """Generate work orders from critical devices."""
    devices = _get_devices_list()

    work_orders = []
    for d in devices:
        if not isinstance(d, dict):
            continue
        state = d.get("health_state", "").lower()
        device_id = d.get("device_id", "unknown")
        equip = d.get("equipment_type", "UNKNOWN")

        if state in ("critical", "failure"):
            work_orders.append({
                "work_order_id": f"WO-{device_id}",
                "device_id": device_id,
                "urgency": "immediate",
                "description": f"Immediate repair required for {equip} {device_id}",
                "assigned_to": "Maintenance Team A",
                "estimated_hours": 4,
                "created_at": datetime.utcnow().isoformat(),
                "status": "open",
            })
        elif state in ("warning", "degraded"):
            work_orders.append({
                "work_order_id": f"WO-{device_id}",
                "device_id": device_id,
                "urgency": "urgent",
                "description": f"Preventive maintenance for {equip} {device_id}",
                "assigned_to": "Maintenance Team B",
                "estimated_hours": 2,
                "created_at": datetime.utcnow().isoformat(),
                "status": "open",
            })

    if status:
        work_orders = [wo for wo in work_orders if wo["status"] == status]

    immediate = sum(1 for wo in work_orders if wo["urgency"] == "immediate")
    urgent = sum(1 for wo in work_orders if wo["urgency"] == "urgent")
    total_hours = sum(wo["estimated_hours"] for wo in work_orders)

    return {
        "work_orders": work_orders[skip : skip + limit],
        "total": len(work_orders),
        "by_urgency": {"immediate": immediate, "urgent": urgent},
        "total_estimated_hours": total_hours,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /spare-parts
# ---------------------------------------------------------------------------
@app.get("/spare-parts")
@app.get("/api/spare-parts")
async def get_spare_parts(availability: Optional[str] = None, skip: int = 0, limit: int = 50):
    """Return spare parts inventory from MCP tool."""
    result = invoke_orchestrator_action(action="get_spare_parts")
    parts_body = _unwrap(result)
    parts = parts_body.get("parts", [])

    if availability:
        parts = [p for p in parts if p.get("availability") == availability]

    in_stock = sum(1 for p in parts if p.get("availability") == "in_stock")
    on_order = sum(1 for p in parts if p.get("availability") == "on_order")
    critical_unavail = sum(
        1 for p in parts
        if p.get("criticality") == "critical" and p.get("availability") != "in_stock"
    )

    return {
        "parts": parts[skip : skip + limit],
        "total": len(parts),
        "by_availability": {"in_stock": in_stock, "on_order": on_order},
        "critical_parts_unavailable": critical_unavail,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /analytics/overview
# ---------------------------------------------------------------------------
@app.get("/analytics/overview")
@app.get("/api/analytics/overview")
async def analytics_overview():
    """Aggregate analytics from device health data."""
    devices = _get_devices_list()

    equipment_counts: Dict[str, int] = {}
    degradation_scores = []

    for d in devices:
        if not isinstance(d, dict):
            continue
        equip = d.get("equipment_type", "UNKNOWN")
        equipment_counts[equip] = equipment_counts.get(equip, 0) + 1
        deg = d.get("degradation_score")
        if deg is not None:
            degradation_scores.append(deg)

    avg_deg = sum(degradation_scores) / len(degradation_scores) if degradation_scores else 0
    avg_conf = 1 - avg_deg

    return {
        "average_degradation": round(avg_deg, 3),
        "average_confidence": round(avg_conf, 3),
        "total_devices_analyzed": len(devices),
        "devices_by_type": equipment_counts,
        "trend": "stable",
        "timestamp": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /analytics/health-history
# ---------------------------------------------------------------------------
@app.get("/analytics/health-history")
@app.get("/api/analytics/health-history")
async def health_history():
    """Simulated health history for analytics chart."""
    devices = _get_devices_list()
    history_devices = []
    for d in devices:
        if not isinstance(d, dict):
            continue
        device_id = d.get("device_id", "unknown")
        equip = d.get("equipment_type", "UNKNOWN")
        deg = d.get("degradation_score", 0)
        base_health = max(0, round((1 - deg) * 100))
        data_points = [
            {
                "timestamp": (datetime.utcnow() - timedelta(hours=i * 4)).isoformat(),
                "health_percent": min(100, max(0, base_health + (i % 3 - 1) * 2)),
            }
            for i in range(24)
        ]
        history_devices.append({
            "device_id": device_id,
            "equipment_type": equip,
            "data_points": data_points,
        })
    return {"devices": history_devices, "total_devices": len(history_devices)}


# ---------------------------------------------------------------------------
# GET /cache-clear
# ---------------------------------------------------------------------------
@app.get("/cache-clear")
@app.get("/api/cache-clear")
async def cache_clear():
    """Clear any cached data and return fresh fleet summary."""
    return await fleet_summary()
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
# Helpers
# ---------------------------------------------------------------------------
def _get_devices_list() -> List[Dict[str, Any]]:
    """Fetch device list from orchestrator and return the devices array."""
    result = invoke_orchestrator_action(action="list_devices")
    body = _unwrap(result)
    devices = body.get("devices", [])
    return [d for d in devices if isinstance(d, dict)]


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
