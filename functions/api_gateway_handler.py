"""
FastAPI Lambda handler for the team01-orchestrator-api API Gateway.

Sits in front of lambda_orchestrator_handler and exposes a REST API
that CloudFront and the React dashboard consume:
    GET  /health, /devices, /devices/{id}, /devices/{id}/summary
    GET  /fleet-summary, /alerts, /work-orders, /maintenance-schedule,
         /spare-parts, /analytics/overview, /analytics/health-history
    POST /orchestrate  (proxied to the original handler)

work-orders/maintenance-schedule/alerts/fleet-summary are backed by real
per-device HealthAgent/DiagnosisAgent analysis (see _get_analyzed_devices),
not fabricated placeholders.

Deployed via Mangum as an AWS Lambda behind the {proxy+} route on
the team01-orchestrator-api REST API Gateway.
"""

import json
import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

# Import the original orchestrator handler functions
from lambda_orchestrator_handler import (
    invoke_orchestrator_action,
    invoke_orchestrator_agent,
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
    """Aggregate fleet KPIs from orchestrator device list, plus real MCP data."""
    logger.info("Fleet summary requested")

    devices: List[Dict[str, Any]] = _get_devices_list()

    total = len(devices)
    healthy = warning = critical = 0

    for d in devices:
        if isinstance(d, dict):
            state = d.get("health_state", "").lower()
            if state in ("healthy", "normal", "good"):
                healthy += 1
            elif state in ("warning", "degraded", "alert"):
                warning += 1
            elif state in ("critical", "failure", "failed"):
                critical += 1

    logger.info(f"Fleet: {total} devices, {healthy} healthy, {warning} warning, {critical} critical")

    analyzed = _get_analyzed_devices()
    work_orders: List[Dict[str, Any]] = []
    maintenance_schedules: List[Dict[str, Any]] = []
    spare_parts_by_id: Dict[str, Dict[str, Any]] = {}
    for d in analyzed:
        tool_results = d.get("tool_results", {})
        work_orders.extend(extract_work_orders(tool_results))
        maintenance_schedules.extend(extract_maintenance_schedules(tool_results))
        for part in extract_spare_parts(tool_results):
            part_id = part.get("part_id")
            if part_id and part_id not in spare_parts_by_id:
                spare_parts_by_id[part_id] = part

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
        "work_orders": work_orders,
        "maintenance_schedules": maintenance_schedules,
        "spare_parts": list(spare_parts_by_id.values()),
    }


# ---------------------------------------------------------------------------
# GET /alerts
# ---------------------------------------------------------------------------
@app.get("/alerts")
@app.get("/api/alerts")
async def get_alerts(severity: Optional[str] = None, skip: int = 0, limit: int = 50):
    """Real alerts derived from each device's live HealthAgent/DiagnosisAgent analysis."""
    devices = _get_analyzed_devices()

    alerts = []
    for d in devices:
        state = (d.get("health_status") or d.get("health_state") or "").lower()
        device_id = d.get("device_id", "unknown")

        if state == "critical":
            alerts.append({
                "id": f"alert-{device_id}-critical",
                "device_id": device_id,
                "severity": "critical",
                "title": f"Critical: {device_id} requires immediate attention",
                "description": d.get("diagnosis", "Device in critical state"),
                "timestamp": d.get("timestamp"),
                "action_required": True,
            })
        elif state == "warning":
            alerts.append({
                "id": f"alert-{device_id}-warning",
                "device_id": device_id,
                "severity": "high",
                "title": f"Warning: {device_id} anomaly detected",
                "description": d.get("diagnosis", "Device showing warning signs"),
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
    """Real maintenance schedules extracted from each device's MCP tool_results."""
    devices = _get_analyzed_devices()

    schedules: List[Dict[str, Any]] = []
    for d in devices:
        schedules.extend(extract_maintenance_schedules(d.get("tool_results", {})))

    urgent = sum(1 for s in schedules if s.get("priority") == "urgent")
    scheduled = sum(1 for s in schedules if s.get("priority") == "scheduled")
    total_cost = sum(s.get("estimated_cost", 0) for s in schedules)

    schedules.sort(key=lambda s: (0 if s.get("priority") == "urgent" else 1, s.get("start_date", "")))

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
    """Real work orders extracted from each device's DiagnosisAgent MCP tool_results."""
    devices = _get_analyzed_devices()

    work_orders: List[Dict[str, Any]] = []
    for d in devices:
        work_orders.extend(extract_work_orders(d.get("tool_results", {})))

    if status:
        work_orders = [wo for wo in work_orders if wo.get("status") == status]

    urgency_order = {"immediate": 0, "urgent": 1, "scheduled": 2}
    work_orders.sort(key=lambda wo: (urgency_order.get(wo.get("urgency"), 3), wo.get("created_at", "")))

    immediate = sum(1 for wo in work_orders if wo.get("urgency") == "immediate")
    urgent = sum(1 for wo in work_orders if wo.get("urgency") == "urgent")
    total_hours = sum(wo.get("estimated_hours", 0) for wo in work_orders)

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
    """Invalidate the per-device analysis cache and return a fresh fleet summary."""
    _ANALYSIS_CACHE["devices"] = None
    _DEVICES_LIST_CACHE["devices"] = None
    return await fleet_summary()


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
_DEVICES_LIST_CACHE: Dict[str, Any] = {"devices": None, "fetched_at": 0.0}
_DEVICES_LIST_CACHE_TTL_SECONDS = 300


def _get_devices_list() -> List[Dict[str, Any]]:
    """Fetch device list from orchestrator and return the devices array.

    Cached briefly: list_devices is itself a ~7s agent round trip, and
    fleet-summary needs it both directly (for health counts) and indirectly
    via _get_analyzed_devices() (for the device_id list to analyze) -
    caching avoids paying for it twice in the same request under API
    Gateway's 29s integration timeout.
    """
    now = time.time()
    if _DEVICES_LIST_CACHE["devices"] is not None and (now - _DEVICES_LIST_CACHE["fetched_at"]) < _DEVICES_LIST_CACHE_TTL_SECONDS:
        return _DEVICES_LIST_CACHE["devices"]

    result = invoke_orchestrator_action(action="list_devices")
    body = _unwrap(result)
    devices = [d for d in body.get("devices", []) if isinstance(d, dict)]

    _DEVICES_LIST_CACHE["devices"] = devices
    _DEVICES_LIST_CACHE["fetched_at"] = now
    return devices


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
# Per-device analysis cache
#
# work-orders/maintenance-schedule/alerts/fleet-summary all need each device's
# real tool_results, which only come back from action="get_device" (the full
# HealthAgent -> DiagnosisAgent workflow, ~3s per device). API Gateway REST
# APIs hard-cap integration time at 29s, and this fleet has 17 devices, so
# calls are fanned out with a thread pool instead of a sequential loop.
# Results are cached in memory for _ANALYSIS_CACHE_TTL_SECONDS; the cache lives
# at module scope, so it survives across warm Lambda invocations.
# ---------------------------------------------------------------------------
_ANALYSIS_CACHE: Dict[str, Any] = {"devices": None, "fetched_at": 0.0}
_ANALYSIS_CACHE_TTL_SECONDS = 300


def _get_analyzed_devices() -> List[Dict[str, Any]]:
    """Return real per-device analysis (health_status, diagnosis, tool_results) for the fleet."""
    now = time.time()
    if _ANALYSIS_CACHE["devices"] is not None and (now - _ANALYSIS_CACHE["fetched_at"]) < _ANALYSIS_CACHE_TTL_SECONDS:
        return _ANALYSIS_CACHE["devices"]

    device_ids = [d.get("device_id") for d in _get_devices_list() if d.get("device_id")]

    def _analyze_one(device_id: str) -> Optional[Dict[str, Any]]:
        result = invoke_orchestrator_action(action="get_device", device_id=device_id)
        body = _unwrap(result)
        if "error" in body:
            logger.warning(f"Skipping {device_id} in analysis cache: {body.get('error')}")
            return None
        body.setdefault("device_id", device_id)
        return body

    analyzed: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(len(device_ids), 1)) as pool:
        for body in pool.map(_analyze_one, device_ids):
            if body is not None:
                analyzed.append(body)

    _ANALYSIS_CACHE["devices"] = analyzed
    _ANALYSIS_CACHE["fetched_at"] = now
    return analyzed


# ---------------------------------------------------------------------------
# MCP tool_results extractors — ported from src/dashboard/routes/api.py so the
# Lambda's work-orders/maintenance-schedule/alerts routes show the same real
# data as the local dashboard, instead of fabricated placeholders.
# ---------------------------------------------------------------------------
def extract_maintenance_schedules(tool_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract maintenance schedule entries from tool_results['schedule-maintenance']."""
    schedules: List[Dict[str, Any]] = []
    if not tool_results or "schedule-maintenance" not in tool_results:
        return schedules

    data = tool_results.get("schedule-maintenance")
    if isinstance(data, dict) and "statusCode" in data and "body" in data:
        data = _unwrap(data)
    if isinstance(data, dict) and "success" in data and "data" in data:
        data = data.get("data") if data.get("success") else None
    elif isinstance(data, dict) and isinstance(data.get("maintenance"), list):
        data = data.get("maintenance")

    items = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    for item in items:
        if isinstance(item, dict) and item.get("maintenance_id"):
            schedules.append({
                "maintenance_id": item.get("maintenance_id"),
                "device_id": item.get("device_id", ""),
                "start_date": item.get("start_date"),
                "duration_hours": item.get("duration_hours", 0),
                "priority": item.get("priority", "scheduled"),
                "parts_needed": item.get("parts_needed", []),
                "estimated_cost": item.get("estimated_cost", 0),
                "reason": item.get("reason", ""),
                "status": "scheduled",
            })
    return schedules


def extract_work_orders(tool_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract work order entries from tool_results['create-work-order']."""
    work_orders: List[Dict[str, Any]] = []
    if not tool_results or "create-work-order" not in tool_results:
        return work_orders

    data = tool_results.get("create-work-order")
    raw_items = data if isinstance(data, list) else [data] if isinstance(data, dict) else []

    for item in raw_items:
        if not isinstance(item, dict):
            continue
        if "success" in item and "data" in item:
            item = item.get("data") if item.get("success") else {}
        if isinstance(item, dict) and item.get("work_order_id"):
            work_orders.append({
                "work_order_id": item.get("work_order_id"),
                "device_id": item.get("device_id", ""),
                "work_type": item.get("work_type", "Maintenance"),
                "urgency": item.get("urgency", "scheduled"),
                "assigned_to": item.get("assigned_to", "Unassigned"),
                "estimated_hours": item.get("estimated_hours", 0),
                "description": item.get("description", ""),
                "created_at": item.get("created_at"),
                "status": item.get("status", "open"),
            })
    return work_orders


def extract_spare_parts(tool_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract spare parts entries from tool_results['get-spare-parts']."""
    parts: List[Dict[str, Any]] = []
    if not tool_results or "get-spare-parts" not in tool_results:
        return parts

    data = tool_results.get("get-spare-parts")
    if isinstance(data, dict) and "statusCode" in data and "body" in data:
        data = _unwrap(data)
    if isinstance(data, dict) and "success" in data and "data" in data:
        data = data.get("data") if data.get("success") else None
    elif isinstance(data, dict) and isinstance(data.get("parts"), list):
        data = data.get("parts")

    items = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    for p in items:
        if not isinstance(p, dict) or not p.get("part_id"):
            continue
        qty = p.get("quantity_available") or p.get("stock_quantity") or 0
        availability = p.get("availability") or ("in_stock" if qty > 0 else "out_of_stock")
        parts.append({
            "part_id": p.get("part_id"),
            "part_name": p.get("part_name", ""),
            "equipment_type": p.get("equipment_type") or p.get("category", ""),
            "availability": availability,
            "quantity_available": qty,
            "lead_time_days": p.get("lead_time_days", 0),
            "unit_cost": p.get("unit_cost", 0),
            "criticality": p.get("criticality", "high"),
        })
    return parts


# ---------------------------------------------------------------------------
# Mangum handler (Lambda entry point)
# ---------------------------------------------------------------------------
handler = Mangum(app, lifespan="off")
