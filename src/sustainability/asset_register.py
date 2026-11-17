#!/usr/bin/env python3
"""
Asset register and service logistics -- DEMO STAND-IN.

The Sustainability Agent needs two things the sensor stream does not carry:

  asset      -- how much power the machine draws and how hard it runs.
                Without this there is no energy-waste model, and "keep
                monitoring" collapses back to looking free.

  logistics  -- how far the technician travels and when the next planned
                visit to that region is. Without this there is nothing to
                batch and no trip to avoid.

In production both come from the CMMS / asset master. This module is the
stand-in for the hackathon, and it is deliberately honest about that: every
record carries a `source` field, and `provenance_note()` prints exactly what
is real and what is assumed. Say that line out loud in the demo -- a judge who
discovers invented data trusts nothing else you showed. A judge you told first
just nods.

Any device_id not listed still works: it falls back to a per-equipment-type
default, flagged as such.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, Optional

# ---------------------------------------------------------------------------
# Typical ratings by equipment class.
# Ranges are ordinary industrial sizes, not measurements from any real site.
# ---------------------------------------------------------------------------
EQUIPMENT_TYPE_DEFAULTS: Dict[str, dict] = {
    "PUMP": {
        "rated_power_kw": 45.0,
        "duty_cycle": 0.90,      # process pumps run nearly continuously
        "baseline_efficiency": 0.78,
    },
    "MOTOR": {
        "rated_power_kw": 30.0,
        "duty_cycle": 0.75,
        "baseline_efficiency": 0.92,
    },
    "COMPRESSOR": {
        "rated_power_kw": 90.0,  # the big energy consumer on most sites
        "duty_cycle": 0.65,      # load/unload cycling
        "baseline_efficiency": 0.70,
    },
    "GENERATOR": {
        "rated_power_kw": 250.0,
        "duty_cycle": 0.15,      # standby: idle most of the time
        "baseline_efficiency": 0.85,
    },
    "UNKNOWN": {
        "rated_power_kw": 40.0,
        "duty_cycle": 0.70,
        "baseline_efficiency": 0.80,
    },
}


@dataclass
class Site:
    """A physical location. Distances are computed from the depot, not typed in."""

    site_id: str
    name: str
    lat: float
    lon: float
    grid_zone: str = "FI"
    next_planned_visit_days: int = 14
    planned_visit_jobs: int = 2  # jobs the scheduled visit already carries


# Depot: Helsinki. Change to wherever your service crew is based.
DEPOT = {"lat": 60.1699, "lon": 24.9384, "name": "Helsinki service depot"}

SITES: Dict[str, Site] = {
    "TAMPERE": Site("TAMPERE", "Tampere plant", 61.4991, 23.7871, "FI", 12, 3),
    "TURKU": Site("TURKU", "Turku plant", 60.4518, 22.2666, "FI", 9, 2),
    "OULU": Site("OULU", "Oulu plant", 65.0121, 25.4651, "FI", 21, 1),
    "VANTAA": Site("VANTAA", "Vantaa facility", 60.2934, 25.0378, "FI", 5, 4),
    # Second grid zone -- this is what makes the region-flip demo possible.
    "KATOWICE": Site("KATOWICE", "Katowice plant", 50.2649, 19.0238, "PL", 12, 2),
}


@dataclass
class AssetRecord:
    device_id: str
    equipment_type: str
    rated_power_kw: float
    duty_cycle: float
    site_id: str
    baseline_efficiency: float = 0.80
    spare_part_available: bool = True
    source: str = "demo asset register (assumed)"

    def to_asset_input(self) -> dict:
        """The `asset` block the Sustainability Agent expects."""
        site = SITES[self.site_id]
        return {
            "rated_power_kw": self.rated_power_kw,
            "duty_cycle": self.duty_cycle,
            "grid_zone": site.grid_zone,
            "baseline_efficiency": self.baseline_efficiency,
        }


# ---------------------------------------------------------------------------
# The demo fleet. Sized so the scenarios land on different recommendations --
# a fleet where every device gets the same answer proves nothing.
# ---------------------------------------------------------------------------
ASSET_REGISTER: Dict[str, AssetRecord] = {
    # Mid-size pump: the balanced case. Deferral usually wins in Finland.
    "PUMP-1043": AssetRecord("PUMP-1043", "PUMP", 45.0, 0.90, "TAMPERE"),
    "PUMP-1101": AssetRecord("PUMP-1101", "PUMP", 37.0, 0.88, "TAMPERE"),
    # Large pump: wastes enough energy that waiting rarely pays off.
    "PUMP-2201": AssetRecord("PUMP-2201", "PUMP", 110.0, 0.95, "VANTAA"),
    # Motors: smaller waste, deferral almost always wins.
    "MOTOR-0788": AssetRecord("MOTOR-0788", "MOTOR", 22.0, 0.70, "TAMPERE"),
    "MOTOR-0912": AssetRecord("MOTOR-0912", "MOTOR", 30.0, 0.80, "TURKU"),
    # Compressor: biggest consumer on site, and the part is out of stock --
    # exercises the procurement branch of the tool plan.
    "COMP-0450": AssetRecord(
        "COMP-0450", "COMPRESSOR", 90.0, 0.65, "TURKU", spare_part_available=False
    ),
    # Standby generator: low duty cycle, so almost no waste while waiting.
    "GEN-0301": AssetRecord("GEN-0301", "GENERATOR", 250.0, 0.15, "OULU"),
    # Same spec as PUMP-1043, different grid. This pair IS the region-flip demo.
    "PUMP-9001": AssetRecord("PUMP-9001", "PUMP", 45.0, 0.90, "KATOWICE"),
}


def get_asset(device_id: str, equipment_type: str = "UNKNOWN") -> dict:
    """Asset block for a device. Falls back to type defaults, flagged as such."""
    record = ASSET_REGISTER.get(device_id)
    if record is not None:
        return record.to_asset_input()

    defaults = EQUIPMENT_TYPE_DEFAULTS.get(
        equipment_type.upper(), EQUIPMENT_TYPE_DEFAULTS["UNKNOWN"]
    )
    return {
        **defaults,
        "grid_zone": "FI",
        "source": f"type default for {equipment_type} -- device not in register",
    }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math

    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def get_logistics(device_id: str, equipment_type: str = "UNKNOWN") -> dict:
    """Logistics block for a device.

    Travel distance is COMPUTED from real coordinates rather than typed in, so
    the batching numbers and the single-device numbers cannot contradict each
    other -- which they will if you hardcode both.
    """
    record = ASSET_REGISTER.get(device_id)
    site = SITES[record.site_id] if record else SITES["TAMPERE"]

    one_way_km = haversine_km(DEPOT["lat"], DEPOT["lon"], site.lat, site.lon)

    return {
        "travel_distance_km": round(one_way_km, 1),
        "next_planned_visit_days": site.next_planned_visit_days,
        "planned_visit_jobs": site.planned_visit_jobs,
        "monitoring_review_days": 30,
        "spare_part_available": record.spare_part_available if record else True,
        "depot_lat": DEPOT["lat"],
        "depot_lon": DEPOT["lon"],
        "site_name": site.name,
    }


def build_agent_input(
    device_id: str,
    equipment_type: str,
    health_status: str,
    degradation_score: float,
    diagnosis: str,
    action: str,
    predicted_ttf_days: float,
    anomalies: Optional[list] = None,
) -> dict:
    """One call that assembles everything the Sustainability Agent needs.

    Use this in the orchestrator so the wiring is a single line.
    """
    return {
        "device_id": device_id,
        "equipment_type": equipment_type,
        "health_status": health_status,
        "degradation_score": degradation_score,
        "diagnosis": diagnosis,
        "action": action,
        "anomalies": anomalies or [],
        "predicted_ttf_days": predicted_ttf_days,
        "asset": get_asset(device_id, equipment_type),
        "logistics": get_logistics(device_id, equipment_type),
    }


def provenance_note() -> str:
    """Print this in the demo. Say it before a judge asks."""
    return (
        "Asset ratings and service logistics are demo stand-ins, not site "
        "measurements. In production both come from the CMMS asset master. "
        "Travel distances ARE computed from real coordinates. Grid intensity "
        "and emission factors are real and sourced -- only the asset ratings "
        "are assumed."
    )


if __name__ == "__main__":
    print(provenance_note())
    print()
    print(f"{'device':<14}{'type':<12}{'kW':>7}{'duty':>7}{'zone':>7}{'km':>8}{'visit':>7}")
    print("-" * 64)
    for device_id, rec in ASSET_REGISTER.items():
        a = get_asset(device_id, rec.equipment_type)
        l = get_logistics(device_id, rec.equipment_type)
        print(
            f"{device_id:<14}{rec.equipment_type:<12}{a['rated_power_kw']:>7.0f}"
            f"{a['duty_cycle']:>7.2f}{a['grid_zone']:>7}"
            f"{l['travel_distance_km']:>8.0f}{l['next_planned_visit_days']:>7}"
        )
    print()
    print("Unlisted device falls back to type defaults:")
    print("  BOILER-999 ->", get_asset("BOILER-999", "COMPRESSOR"))


def build_sustainability_input(
    device_id: str,
    health_output: dict,
    diagnosis_output: dict,
    predicted_ttf_days: float = 30.0,
) -> dict:
    """Dict-in wrapper around build_agent_input.

    The orchestrator already holds the Health and Diagnosis result dicts, so
    this saves unpacking eight fields by hand at the call site.
    """
    equipment_type = (
        health_output.get("equipment_type")
        or diagnosis_output.get("equipment_type")
        or "UNKNOWN"
    )
    return build_agent_input(
        device_id=device_id,
        equipment_type=equipment_type,
        health_status=health_output.get("health_status", "unknown"),
        degradation_score=health_output.get("degradation_score", 0.5),
        diagnosis=diagnosis_output.get("diagnosis", ""),
        action=diagnosis_output.get("action", "MONITOR_ONLY"),
        predicted_ttf_days=predicted_ttf_days,
        anomalies=health_output.get("anomalies", []),
    )
