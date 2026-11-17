#!/usr/bin/env python3
"""
`estimate-carbon-impact` -- Lambda handler for the AgentCore Gateway tool layer.

Registering this as an MCP tool alongside the existing `get-spare-parts`,
`schedule-maintenance` and `create-work-order` keeps the baseline's architecture
intact: agents never touch operational systems directly, they go through the
controlled tool layer. The Sustainability Agent can either import the library
directly (fast path, used in the demo) or call this tool through the gateway
(the path that matches the baseline and is what you should show in the
architecture diagram).

Deploy: Lambda (Python 3.12) + a DynamoDB table for the emission factor
registry, fronted by AgentCore Gateway.

Event shape:
{
  "device_id": "PUMP-1043",
  "equipment_type": "PUMP",
  "root_cause": "Bearing wear",
  "degradation_score": 0.30,
  "rated_power_kw": 45.0,
  "duty_cycle": 0.9,
  "grid_zone": "FI",
  "defer_days": 12.0,
  "travel_km": 120.0
}
"""

from __future__ import annotations

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.sustainability.energy import (
    AssetEnergyProfile,
    estimate_energy_waste,
    waste_over_window,
)
from src.sustainability.factors import EconomicFactors, TRAVEL_FACTORS
from src.sustainability.grid import GridIntensityService

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_GRID = GridIntensityService()
_ECONOMICS = EconomicFactors()


def estimate_carbon_impact(payload: dict) -> dict:
    zone = payload.get("grid_zone", "FI")
    grid = _GRID.current(zone)

    profile = AssetEnergyProfile(
        device_id=payload.get("device_id", "unknown"),
        rated_power_kw=float(payload.get("rated_power_kw", 75.0)),
        duty_cycle=float(payload.get("duty_cycle", 0.85)),
    )
    waste = estimate_energy_waste(
        profile,
        degradation_score=float(payload.get("degradation_score", 0.5)),
        root_cause=payload.get("root_cause", ""),
        anomalies=payload.get("anomalies"),
    )

    defer_days = float(payload.get("defer_days", 0.0))
    window = waste_over_window(
        waste,
        days=defer_days,
        grid_g_per_kwh=grid.g_per_kwh,
        price_eur_per_kwh=_ECONOMICS.electricity_price_eur_per_kwh,
    )

    travel_km = float(payload.get("travel_km", 0.0))
    travel_factor = TRAVEL_FACTORS["van_diesel_average"]
    travel_co2 = travel_km * travel_factor.value

    return {
        "device_id": payload.get("device_id"),
        "grid": {
            "zone": zone,
            "g_per_kwh": round(grid.g_per_kwh, 1),
            "is_live": grid.is_live,
            "source": grid.source,
        },
        "energy_waste": {
            "fault_mode": waste.fault_mode,
            "excess_kw": waste.excess_kw,
            "kwh_per_day": waste.excess_kwh_per_day,
            "co2_kg_per_day": round(waste.co2_kg_per_day(grid.g_per_kwh), 2),
            "basis": waste.basis,
        },
        "over_window": window,
        "travel": {
            "km": travel_km,
            "co2_kg": round(travel_co2, 2),
            "factor": travel_factor.cite(),
        },
        "total_co2_kg": round(window["co2_kg"] + travel_co2, 2),
        "total_cost_eur": round(
            window["cost_eur"] + travel_km * _ECONOMICS.vehicle_cost_eur_per_km, 2
        ),
    }


def lambda_handler(event, context):  # noqa: ARG001
    """AgentCore Gateway entry point."""
    try:
        body = event.get("body", event)
        if isinstance(body, str):
            body = json.loads(body)
        result = estimate_carbon_impact(body)
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as exc:
        logger.error("estimate-carbon-impact failed: %s", exc, exc_info=True)
        return {"statusCode": 500, "body": json.dumps({"error": str(exc)})}


# MCP tool schema for gateway registration.
TOOL_SCHEMA = {
    "name": "estimate-carbon-impact",
    "description": (
        "Estimate CO2e and cost of a maintenance option, combining live grid "
        "carbon intensity, continuous energy waste from the diagnosed fault, and "
        "technician travel. Returns a full breakdown with factor provenance."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
            "equipment_type": {"type": "string"},
            "root_cause": {"type": "string"},
            "degradation_score": {"type": "number", "minimum": 0, "maximum": 1},
            "rated_power_kw": {"type": "number"},
            "duty_cycle": {"type": "number", "minimum": 0, "maximum": 1},
            "grid_zone": {"type": "string"},
            "defer_days": {"type": "number", "minimum": 0},
            "travel_km": {"type": "number", "minimum": 0},
        },
        "required": ["device_id", "root_cause", "degradation_score", "defer_days"],
    },
}


if __name__ == "__main__":
    print(
        json.dumps(
            estimate_carbon_impact(
                {
                    "device_id": "PUMP-1043",
                    "root_cause": "Bearing wear",
                    "degradation_score": 0.30,
                    "rated_power_kw": 45.0,
                    "duty_cycle": 0.9,
                    "grid_zone": "FI",
                    "defer_days": 12.0,
                    "travel_km": 120.0,
                }
            ),
            indent=2,
        )
    )
