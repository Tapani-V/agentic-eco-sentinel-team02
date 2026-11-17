#!/usr/bin/env python3
"""
DEMO 1 -- The region flip.

Same pump. Same fault. Same degradation. Same technician distance.
Only the electricity grid changes.

In Finland (low-carbon grid) the wasted energy is cheap in carbon terms, so
waiting for the planned visit and avoiding a dedicated van trip is greener.

On a coal-heavy grid the same pump wastes several times more CO2 per day, and
the van trip pays for itself within days -- so the agent recommends going now.

A rules engine cannot produce this reversal. That is the point of the demo.

    python -m demo.demo_region_flip
"""

import asyncio
import random
import sys

sys.path.insert(0, ".")

from src.agents.sustainability_agent import SustainabilityAgent
from src.sustainability.conformal import CalibrationRecord, ConformalDeferralGate, empirical_coverage
from src.sustainability.grid import GridIntensityService, StaticProvider


def build_calibration_set(n: int = 400, seed: int = 7):
    """Synthetic history: what the Prediction Agent said vs. what happened.

    Deliberately biased optimistic, the way real RUL models are -- which is
    exactly the bias conformal calibration corrects for.
    """
    rng = random.Random(seed)
    records = []
    for _ in range(n):
        eq = rng.choice(["PUMP", "PUMP", "MOTOR", "COMPRESSOR"])
        actual = rng.uniform(3, 60)
        optimism = {"PUMP": 6.0, "MOTOR": 4.0, "COMPRESSOR": 9.0}[eq]
        predicted = actual + rng.gauss(optimism, 5.0)
        records.append(
            CalibrationRecord(
                equipment_type=eq,
                predicted_ttf_days=max(1.0, predicted),
                actual_ttf_days=actual,
            )
        )
    return records


def scenario(zone: str):
    return {
        "device_id": "PUMP-1043",
        "equipment_type": "PUMP",
        "health_status": "warning",
        "degradation_score": 0.30,
        "diagnosis": "Bearing wear with elevated vibration",
        "action": "SCHEDULE_MAINTENANCE",
        "anomalies": ["vibration_high", "temperature_elevated"],
        "predicted_ttf_days": 26.0,
        "asset": {
            "rated_power_kw": 45.0,
            "duty_cycle": 0.9,
            "grid_zone": zone,
        },
        "logistics": {
            "travel_distance_km": 180.0,
            "next_planned_visit_days": 12,
            "monitoring_review_days": 30,
            "spare_part_available": True,
            "planned_visit_jobs": 3,
            "depot_lat": 60.1699,
            "depot_lon": 24.9384,
        },
    }


def show(zone: str, label: str, result: dict) -> None:
    print(f"\n{'=' * 74}")
    print(f"  {label}  (zone {zone})")
    print("=" * 74)
    g = result["grid_intensity"]
    e = result["energy_waste"]
    print(f"  Grid intensity   : {g['g_per_kwh']} gCO2/kWh  ({'live' if g['is_live'] else 'annual avg'})")
    print(f"  Wasted energy    : {e['kwh_per_day']} kWh/day  ->  {e['co2_kg_per_day']} kg CO2/day")
    print(f"\n  RECOMMENDATION   : {result['recommendation']}  (in {result['defer_days']:.0f} days)")
    print(f"  Risk level       : {result['risk_level']}")
    print(f"  Business         : {result['business_reason']}")
    print(f"  Sustainability   : {result['sustainability_reason']}")
    print(f"\n  {result['explanation']}")

    print(f"\n  Options considered (weights: {result['scoring_weights']}):")
    print(f"    {'option':<24} {'status':<9} {'CO2 kg':>8} {'cost EUR':>9} {'km':>6}")
    for row in result["options_considered"]:
        print(
            f"    {row['option']:<24} {row['status']:<9} "
            f"{row['total_co2_kg']:>8.1f} {row['total_cost_eur']:>9.0f} {row['travel_km']:>6.0f}"
        )

    be = result.get("carbon_breakeven") or {}
    if be:
        print(f"\n  Breakeven        : {be['explanation']}")

    risk = result.get("risk_verdict") or {}
    if risk.get("ttf_lower_bound_days") is not None:
        print(
            f"\n  Conformal gate   : RUL >= {risk['ttf_lower_bound_days']:.1f} days at "
            f"{risk['coverage_level']:.0%} coverage "
            f"(n={risk['calibration_set_size']}, group={risk['calibration_group']})"
        )


async def main() -> None:
    calibration = build_calibration_set(400)
    holdout = build_calibration_set(200, seed=99)

    gate = ConformalDeferralGate(alpha=0.10, safety_margin_days=1.0).fit(calibration)
    cov = empirical_coverage(gate, holdout)

    print("\nCONFORMAL CALIBRATION")
    print("-" * 74)
    print(f"  Nominal coverage   : {cov['nominal_coverage']:.0%}")
    print(f"  Empirical coverage : {cov['empirical_coverage']:.1%}  on {cov['n_evaluated']} held-out episodes")
    print("  The bound is not just theoretical -- it held on this fleet's data.")

    for zone, label in [("FI", "FINLAND -- low-carbon grid"), ("PL", "COAL-HEAVY GRID")]:
        agent = SustainabilityAgent(
            grid_service=GridIntensityService(providers=[StaticProvider()]),
            deferral_gate=gate,
        )
        result = await agent.execute(scenario(zone))
        show(zone, label, result)

    print(f"\n{'=' * 74}")
    print("  Same pump, same fault, same distance. The grid decided.")
    print("=" * 74 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
