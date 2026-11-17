#!/usr/bin/env python3
"""
DEMO 2 -- The guardrail, and the fleet.

Part A answers the question every judge asks: "what stops your carbon agent
delaying a repair that should happen now?" Three independent mechanisms are
shown failing safe.

Part B shows the fleet-level win: separate call-outs merged into shared van
runs, with every device still inside its own risk deadline.

    python -m demo.demo_safety_and_batching
"""

import asyncio
import sys

sys.path.insert(0, ".")

from demo.demo_region_flip import build_calibration_set
from src.agents.sustainability_agent import SustainabilityAgent
from src.sustainability.batching import PendingJob, plan_trips
from src.sustainability.conformal import ConformalDeferralGate
from src.sustainability.factors import TRAVEL_FACTORS
from src.sustainability.grid import GridIntensityService, StaticProvider


def base_case(**overrides):
    case = {
        "device_id": "PUMP-2201",
        "equipment_type": "PUMP",
        "health_status": "warning",
        "degradation_score": 0.30,
        "diagnosis": "Bearing wear with elevated vibration",
        "action": "SCHEDULE_MAINTENANCE",
        "anomalies": ["vibration_high"],
        "predicted_ttf_days": 26.0,
        "asset": {"rated_power_kw": 45.0, "duty_cycle": 0.9, "grid_zone": "FI"},
        "logistics": {
            "travel_distance_km": 180.0,
            "next_planned_visit_days": 12,
            "monitoring_review_days": 30,
            "spare_part_available": True,
            "planned_visit_jobs": 3,
        },
    }
    case.update(overrides)
    return case


async def part_a(gate) -> None:
    print("\n" + "=" * 74)
    print("  PART A -- Three ways the agent refuses to trade safety for carbon")
    print("=" * 74)

    def agent():
        return SustainabilityAgent(
            grid_service=GridIntensityService(providers=[StaticProvider()]),
            deferral_gate=gate,
        )

    # 1. Critical health -- the agent is bypassed entirely, structurally.
    critical = base_case(health_status="critical", action="URGENT_REPAIR")
    r1 = await agent().execute(critical)
    print("\n  1. CRITICAL HEALTH STATUS")
    print(f"     recommendation      : {r1['recommendation']}")
    print(f"     optimisation applied: {r1.get('optimisation_applied')}")
    print(f"     {r1['explanation']}")

    # 2. Short remaining life -- conformal gate blocks every deferral.
    short_life = base_case(device_id="PUMP-2202", predicted_ttf_days=9.0)
    r2 = await agent().execute(short_life)
    print("\n  2. SHORT CERTIFIED REMAINING LIFE")
    print(f"     recommendation : {r2['recommendation']}")
    for row in r2["options_considered"]:
        if row["status"] == "blocked":
            print(f"     blocked        : {row['option']}")
            print(f"                      {row['reason']}")

    # 3. Calibration too thin to certify the requested confidence.
    thin_gate = ConformalDeferralGate(alpha=0.01, safety_margin_days=1.0).fit(
        build_calibration_set(30)
    )
    thin_agent = SustainabilityAgent(
        grid_service=GridIntensityService(providers=[StaticProvider()]),
        deferral_gate=thin_gate,
    )
    r3 = await thin_agent.execute(base_case(device_id="PUMP-2203"))
    print("\n  3. CALIBRATION TOO THIN FOR THE REQUESTED CONFIDENCE (99%)")
    print(f"     recommendation : {r3['recommendation']}")
    blocked = [r for r in r3["options_considered"] if r["status"] == "blocked"]
    if blocked:
        print(f"                      {blocked[0]['reason']}")
    print("\n     An agent that knows when it cannot answer beats one that always answers.")


def part_b() -> None:
    print("\n" + "=" * 74)
    print("  PART B -- Fleet batching: five call-outs become shared van runs")
    print("=" * 74)

    depot = (60.1699, 24.9384)  # Helsinki
    jobs = [
        PendingJob("PUMP-1043", 61.4991, 23.7871, 2, 12, 2.5, "Tampere"),
        PendingJob("MOTOR-0788", 61.4600, 23.8500, 0, 14, 2.0, "Tampere North"),
        PendingJob("PUMP-1101", 61.5300, 23.6500, 3, 11, 2.0, "Tampere West"),
        PendingJob("COMP-0450", 60.4518, 22.2666, 1, 9, 3.0, "Turku"),
        PendingJob("MOTOR-0912", 60.3900, 22.4000, 0, 10, 2.0, "Turku East"),
    ]

    result = plan_trips(
        jobs,
        depot=depot,
        radius_km=60.0,
        max_jobs_per_trip=4,
        max_hours_per_trip=10.0,   # one long service day
        travel_speed_kmh=80.0,     # motorway average
    )
    kg_per_km = TRAVEL_FACTORS["van_diesel_average"].value

    print(f"\n  {result.headline(kg_per_km)}\n")
    for trip in result.trips:
        print(f"    Day {trip.service_day:>2}  {', '.join(trip.devices)}")
        print(
            f"            route {trip.route_km:.0f} km  "
            f"(vs {trip.solo_km_equivalent:.0f} km solo, saves {trip.km_saved:.0f} km)"
        )
    print(
        "\n    Every device is still serviced inside its own conformal deadline -- "
        "\n    batching never pushes a machine past the date its risk bound permits."
    )


async def main() -> None:
    gate = ConformalDeferralGate(alpha=0.10, safety_margin_days=1.0).fit(
        build_calibration_set(400)
    )
    await part_a(gate)
    part_b()
    print()


if __name__ == "__main__":
    asyncio.run(main())
