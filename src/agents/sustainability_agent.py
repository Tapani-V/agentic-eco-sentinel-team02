"""
SustainabilityAgent - carbon- and risk-aware maintenance scheduling.

Sits after the Diagnosis Agent. Diagnosis answers "what is wrong". This answers
"given that, when and how should we act".

Boundaries this agent respects, in order of importance:

  1. It CANNOT downgrade an urgent repair. If the Diagnosis Agent or the Health
     Agent flags critical, the agent is bypassed entirely. It optimises only
     within SCHEDULE_MAINTENANCE and MONITOR_ONLY. This is a hard structural
     guarantee, not a prompt instruction, and it is checked first.

  2. It cannot exceed the conformal deferral bound. Every deferral option passes
     through a calibrated risk gate that can block it outright.

  3. It does not call maintenance tools directly. It emits a tool plan that the
     Orchestrator executes through the existing gateway, preserving the
     baseline's separation between agents and maintenance tooling.

Four decision steps:
  Step 1  Safety precheck        -- is this agent even allowed to run?
  Step 2  Ground the physics     -- live grid intensity + energy waste model
  Step 3  Enumerate and gate     -- three options, each risk-gated
  Step 4  Score, explain, plan   -- pick, narrate via Bedrock, emit tool args
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from src.sustainability.batching import (
    BatchingResult,
    PendingJob,
    marginal_travel_for_device,
    plan_trips,
)
from src.sustainability.conformal import ConformalDeferralGate
from src.sustainability.energy import (
    AssetEnergyProfile,
    estimate_energy_waste,
)
from src.sustainability.factors import (
    EconomicFactors,
    PART_EMBODIED_CARBON,
    TRAVEL_FACTORS,
    audit_factors,
)
from src.sustainability.grid import GridIntensityService
from src.sustainability.narrative import build_fact_table, generate_narrative
from src.sustainability.options import (
    CONTINUE_MONITORING,
    breakeven_waste_kwh_per_day,
    DEFER_TO_PLANNED_VISIT,
    REPAIR_NOW,
    OptionEvaluation,
    ScoringWeights,
    build_option,
    comparison_table,
    score_options,
    select_recommendation,
)

logger = logging.getLogger(__name__)

try:  # keep the module runnable standalone for the demo
    from src.agents.base_agent import BaseAgent
except Exception:  # pragma: no cover

    class BaseAgent:  # minimal shim matching the baseline interface
        def __init__(self, name: str, capability: str):
            self.name = name
            self.capability = capability

        def _log_execution(self, device_id: str, status: str, message: str) -> None:
            logger.info("[%s] %s | %s | %s", self.name, device_id, status, message)


# Actions the Sustainability Agent is permitted to touch. Anything else passes
# through untouched.
OPTIMISABLE_ACTIONS = {"SCHEDULE_MAINTENANCE", "MONITOR_ONLY"}

PART_FOR_FAULT = {
    "bearing": "bearing",
    "cavitation": "bearing",
    "valve": "valve",
    "seal": "seal",
    "impeller": "valve",
    "misalignment": "bearing",
    "unknown": "bearing",
}


class SustainabilityAgent(BaseAgent):
    def __init__(
        self,
        grid_service: Optional[GridIntensityService] = None,
        deferral_gate: Optional[ConformalDeferralGate] = None,
        economics: Optional[EconomicFactors] = None,
        weights: Optional[ScoringWeights] = None,
    ):
        super().__init__("SustainabilityAgent", "sustainability_optimisation")
        self.grid = grid_service or GridIntensityService()
        self.gate = deferral_gate
        self.economics = economics or EconomicFactors()
        self.weights = weights or ScoringWeights()

    # ------------------------------------------------------------------
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Input (from Orchestrator, carrying Health + Diagnosis output):
        {
          'device_id': str,
          'equipment_type': str,
          'health_status': str,                 # healthy | warning | critical
          'degradation_score': float,           # 0..1, 1 = end of life
          'diagnosis': str,                     # root cause text
          'action': str,                        # Diagnosis Agent's intent
          'anomalies': [str],
          'predicted_ttf_days': float,          # from Prediction Agent
          'asset': {                            # from the asset register
             'rated_power_kw': float, 'duty_cycle': float,
             'site_lat': float, 'site_lon': float, 'grid_zone': 'FI'
          },
          'logistics': {
             'depot_lat': float, 'depot_lon': float,
             'travel_distance_km': float,       # one way, optional
             'next_planned_visit_days': int,
             'spare_part_available': bool
          },
          'fleet_pending_jobs': [ {...} ]       # optional, enables batching
        }
        """
        device_id = input_data.get("device_id", "unknown")
        try:
            equipment_type = input_data.get("equipment_type", "UNKNOWN")
            health_status = input_data.get("health_status", "unknown")
            upstream_action = input_data.get("action", "MONITOR_ONLY")
            root_cause = input_data.get("diagnosis", "")
            anomalies = input_data.get("anomalies", []) or []
            degradation = float(input_data.get("degradation_score", 0.5))
            predicted_ttf = float(input_data.get("predicted_ttf_days", 30.0))

            asset_cfg = input_data.get("asset", {}) or {}
            logistics = input_data.get("logistics", {}) or {}

            logger.info(
                "[SustainabilityAgent] %s (%s) upstream_action=%s health=%s",
                device_id, equipment_type, upstream_action, health_status,
            )

            # -- STEP 1: safety precheck ---------------------------------
            gate_result = self._safety_precheck(health_status, upstream_action)
            if not gate_result["may_optimise"]:
                logger.info("[SustainabilityAgent] Bypassed: %s", gate_result["reason"])
                return self._passthrough(device_id, upstream_action, gate_result["reason"])

            # -- STEP 2: ground the physics ------------------------------
            zone = asset_cfg.get("grid_zone", "FI")
            grid_now = self.grid.current(zone)

            profile = AssetEnergyProfile(
                device_id=device_id,
                rated_power_kw=float(asset_cfg.get("rated_power_kw", 75.0)),
                duty_cycle=float(asset_cfg.get("duty_cycle", 0.85)),
            )
            waste = estimate_energy_waste(profile, degradation, root_cause, anomalies)

            logger.info(
                "[SustainabilityAgent] Grid %s | waste %.1f kWh/day (%.1f kg CO2/day)",
                grid_now.label(), waste.excess_kwh_per_day,
                waste.co2_kg_per_day(grid_now.g_per_kwh),
            )

            # -- STEP 3: enumerate and risk-gate options -----------------
            batching = self._maybe_batch(input_data, logistics)
            options = self._build_options(
                device_id=device_id,
                equipment_type=equipment_type,
                waste=waste,
                grid_g_per_kwh=grid_now.g_per_kwh,
                grid_source=grid_now.source,
                logistics=logistics,
                predicted_ttf=predicted_ttf,
                batching=batching,
            )

            # -- STEP 4: score, explain, plan ----------------------------
            options = score_options(options, self.weights)
            chosen = select_recommendation(options)

            if chosen is None:
                # Every deferral blocked and repair-now somehow unavailable:
                # fail safe upward, never downward.
                logger.warning("[SustainabilityAgent] All options blocked -> escalating.")
                return self._passthrough(
                    device_id,
                    "SCHEDULE_MAINTENANCE",
                    "No option cleared the risk gate. Escalated to upstream action.",
                )

            baseline = self._baseline_delta(options, chosen)
            facts = build_fact_table(
                device_id=device_id,
                equipment_type=equipment_type,
                root_cause=root_cause,
                recommendation=chosen.to_dict(),
                all_options=[o.to_dict() for o in options],
                risk=chosen.risk,
                grid={
                    "zone": zone,
                    "g_per_kwh": round(grid_now.g_per_kwh, 1),
                    "is_live": grid_now.is_live,
                    "source": grid_now.source,
                },
                baseline=baseline,
            )
            narrative = generate_narrative(facts)
            tool_plan = self._build_tool_plan(device_id, chosen, waste, logistics)

            result = {
                "device_id": device_id,
                "status": "completed",
                "recommendation": chosen.option,
                "defer_days": chosen.defer_days,
                "scheduled_date": self._service_date(chosen.defer_days),
                "explanation": narrative["text"],
                "explanation_source": narrative["source"],
                "business_reason": self._business_reason(baseline),
                "sustainability_reason": self._sustainability_reason(baseline),
                "carbon_breakeven": self._breakeven(options, grid_now.g_per_kwh, waste),
                "risk_verdict": chosen.risk,
                "risk_level": self._risk_label(chosen),
                "options_considered": comparison_table(options),
                "energy_waste": {
                    "excess_kw": waste.excess_kw,
                    "kwh_per_day": waste.excess_kwh_per_day,
                    "co2_kg_per_day": round(waste.co2_kg_per_day(grid_now.g_per_kwh), 2),
                    "fault_mode": waste.fault_mode,
                    "basis": waste.basis,
                },
                "grid_intensity": {
                    "zone": zone,
                    "g_per_kwh": round(grid_now.g_per_kwh, 1),
                    "is_live": grid_now.is_live,
                    "source": grid_now.source,
                },
                "batching": self._batching_summary(device_id, batching, logistics),
                "scoring_weights": self.weights.describe(),
                "factor_provenance": audit_factors(),
                "tool_plan": tool_plan,
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            }

            self._log_execution(
                device_id,
                "completed",
                f"{chosen.option} in {chosen.defer_days:.0f}d | "
                f"-{baseline['co2_saved_kg']:.1f} kgCO2e | -EUR {baseline['cost_saved_eur']:.0f}",
            )
            return result

        except Exception as exc:
            logger.error("[SustainabilityAgent] %s failed: %s", device_id, exc, exc_info=True)
            # Fail safe: hand back the upstream action unchanged.
            return self._passthrough(
                device_id,
                input_data.get("action", "SCHEDULE_MAINTENANCE"),
                f"Sustainability optimisation errored ({exc}). Upstream action preserved.",
                status="error",
            )

    # ------------------------------------------------------------------
    # Step 1
    # ------------------------------------------------------------------
    @staticmethod
    def _safety_precheck(health_status: str, upstream_action: str) -> Dict[str, Any]:
        """The hard guarantee. Structural, not advisory."""
        if str(health_status).lower() == "critical":
            return {
                "may_optimise": False,
                "reason": (
                    "Health status is critical. Sustainability optimisation is bypassed; "
                    "urgent repair proceeds unchanged."
                ),
            }
        if upstream_action not in OPTIMISABLE_ACTIONS:
            return {
                "may_optimise": False,
                "reason": (
                    f"Upstream action {upstream_action} is outside this agent's remit. "
                    f"Only {sorted(OPTIMISABLE_ACTIONS)} may be optimised."
                ),
            }
        return {"may_optimise": True, "reason": ""}

    @staticmethod
    def _passthrough(
        device_id: str, action: str, reason: str, status: str = "bypassed"
    ) -> Dict[str, Any]:
        return {
            "device_id": device_id,
            "status": status,
            "recommendation": action,
            "optimisation_applied": False,
            "explanation": reason,
            "risk_level": "High" if action == "URGENT_REPAIR" else "Unchanged",
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Step 3
    # ------------------------------------------------------------------
    def _maybe_batch(
        self, input_data: Dict[str, Any], logistics: Dict[str, Any]
    ) -> Optional[BatchingResult]:
        raw_jobs = input_data.get("fleet_pending_jobs")
        if not raw_jobs:
            return None
        depot = (
            float(logistics.get("depot_lat", 60.1699)),
            float(logistics.get("depot_lon", 24.9384)),
        )
        jobs = [PendingJob(**j) for j in raw_jobs]
        return plan_trips(jobs, depot=depot)

    def _build_options(
        self,
        *,
        device_id: str,
        equipment_type: str,
        waste,
        grid_g_per_kwh: float,
        grid_source: str,
        logistics: Dict[str, Any],
        predicted_ttf: float,
        batching: Optional[BatchingResult],
    ) -> List[OptionEvaluation]:
        one_way_km = float(logistics.get("travel_distance_km", 60.0))
        solo_round_trip_km = 2.0 * one_way_km
        planned_visit_days = float(logistics.get("next_planned_visit_days", 14))
        monitoring_days = float(logistics.get("monitoring_review_days", 30))
        part_available = bool(logistics.get("spare_part_available", True))

        part_key = PART_FOR_FAULT.get(waste.fault_mode, "bearing")
        part_co2 = PART_EMBODIED_CARBON[part_key].value

        options: List[OptionEvaluation] = []

        # Option 1 -- repair now, dedicated call-out. Always permitted: this is
        # the conservative choice and must never be gated out.
        options.append(
            build_option(
                option=REPAIR_NOW,
                defer_days=0.0,
                travel_km=solo_round_trip_km,
                energy_waste=waste,
                grid_g_per_kwh=grid_g_per_kwh,
                grid_source=grid_source,
                economics=self.economics,
                parts_co2_kg=part_co2,
                service_hours=3.0,
                planned_downtime_hours=4.0,
                verdict=None,
                notes="Dedicated trip today. Highest travel emissions, zero waiting risk.",
            )
        )

        # Option 2 -- ride along with the next planned visit.
        # A planned visit to this region is happening anyway. Charging this
        # device a full round trip would be double counting: the correct
        # accounting is to allocate the shared trip's kilometres across the
        # jobs it serves. Default assumes the visit already carries one other
        # job, so this device picks up half.
        jobs_on_planned_visit = int(logistics.get("planned_visit_jobs", 2))
        batched_km = solo_round_trip_km / max(1, jobs_on_planned_visit)
        batch_note = (
            f"Rides along with a visit already scheduled for this region; "
            f"trip kilometres split {jobs_on_planned_visit} ways."
        )
        if batching is not None:
            alloc = marginal_travel_for_device(
                device_id,
                batching,
                (
                    float(logistics.get("depot_lat", 60.1699)),
                    float(logistics.get("depot_lon", 24.9384)),
                ),
            )
            if alloc:
                batched_km = alloc["allocated_km"]
                planned_visit_days = float(alloc["service_day"])
                batch_note = (
                    f"Batched with {alloc['jobs_on_trip'] - 1} other job(s) on one van run: "
                    f"{alloc['km_avoided']:.0f} km avoided versus a solo call-out."
                )

        verdict_defer = self._gate_verdict(equipment_type, predicted_ttf, planned_visit_days)
        options.append(
            build_option(
                option=DEFER_TO_PLANNED_VISIT,
                defer_days=planned_visit_days,
                travel_km=batched_km,
                energy_waste=waste,
                grid_g_per_kwh=grid_g_per_kwh,
                grid_source=grid_source,
                economics=self.economics,
                parts_co2_kg=part_co2 if part_available else part_co2,
                service_hours=2.5,
                planned_downtime_hours=3.0,
                verdict=verdict_defer,
                notes=batch_note
                + ("" if part_available else " Spare part must be procured first."),
            )
        )

        # Option 3 -- keep monitoring. NOT free: the machine wastes energy every
        # day it runs degraded, which is the whole point of this agent.
        verdict_monitor = self._gate_verdict(equipment_type, predicted_ttf, monitoring_days)
        options.append(
            build_option(
                option=CONTINUE_MONITORING,
                defer_days=monitoring_days,
                travel_km=0.0,
                energy_waste=waste,
                grid_g_per_kwh=grid_g_per_kwh,
                grid_source=grid_source,
                economics=self.economics,
                parts_co2_kg=0.0,
                service_hours=0.0,
                planned_downtime_hours=0.0,
                verdict=verdict_monitor,
                notes=(
                    "No trip and no parts, but the machine keeps wasting energy every "
                    "hour it runs degraded."
                ),
            )
        )
        return options

    def _gate_verdict(self, equipment_type: str, predicted_ttf: float, defer_days: float):
        if self.gate is None:
            return None
        return self.gate.evaluate(equipment_type, predicted_ttf, defer_days)

    # ------------------------------------------------------------------
    # Step 4
    # ------------------------------------------------------------------
    @staticmethod
    def _baseline_delta(
        options: List[OptionEvaluation], chosen: OptionEvaluation
    ) -> Dict[str, float]:
        """Savings quoted against repair-now, the conservative default.

        When repair-now IS the recommendation, savings against itself are zero
        and quoting them reads as a bug. In that case the comparison flips: we
        report what deferring WOULD have cost, which is the more interesting
        number anyway -- it is the agent declining to greenwash a delay.
        """
        baseline = next((o for o in options if o.option == REPAIR_NOW), None)
        if baseline is None:
            return {
                "co2_saved_kg": 0.0, "cost_saved_eur": 0.0,
                "co2_saved_pct": 0.0, "cost_saved_pct": 0.0,
                "baseline": REPAIR_NOW, "direction": "none",
            }

        if chosen.option == REPAIR_NOW:
            alternatives = [
                o for o in options if o.option != REPAIR_NOW and o.permitted
            ]
            if not alternatives:
                return {
                    "co2_saved_kg": 0.0, "cost_saved_eur": 0.0,
                    "co2_saved_pct": 0.0, "cost_saved_pct": 0.0,
                    "baseline": REPAIR_NOW, "direction": "only_option",
                }
            worst = max(alternatives, key=lambda o: o.total_co2_kg)
            co2_avoided = worst.total_co2_kg - chosen.total_co2_kg
            cost_delta = worst.total_cost_eur - chosen.total_cost_eur
            return {
                "co2_saved_kg": round(co2_avoided, 2),
                "cost_saved_eur": round(cost_delta, 2),
                "co2_saved_pct": round(
                    100.0 * co2_avoided / worst.total_co2_kg if worst.total_co2_kg else 0.0, 1
                ),
                "cost_saved_pct": round(
                    100.0 * cost_delta / worst.total_cost_eur if worst.total_cost_eur else 0.0, 1
                ),
                "baseline": worst.option,
                "direction": "acting_now_avoids_waste",
            }

        co2_saved = baseline.total_co2_kg - chosen.total_co2_kg
        cost_saved = baseline.total_cost_eur - chosen.total_cost_eur
        return {
            "co2_saved_kg": round(co2_saved, 2),
            "cost_saved_eur": round(cost_saved, 2),
            "co2_saved_pct": round(
                100.0 * co2_saved / baseline.total_co2_kg if baseline.total_co2_kg else 0.0, 1
            ),
            "cost_saved_pct": round(
                100.0 * cost_saved / baseline.total_cost_eur if baseline.total_cost_eur else 0.0, 1
            ),
            "baseline": REPAIR_NOW,
            "direction": "deferral_saves",
        }

    @staticmethod
    def _business_reason(baseline: Dict[str, float]) -> str:
        if baseline.get("direction") == "acting_now_avoids_waste":
            delta = baseline["cost_saved_eur"]
            alt = baseline["baseline"].replace("_", " ").lower()
            if delta >= 0:
                return (
                    f"Acting now avoids EUR {delta:.0f} of energy waste and downtime "
                    f"versus {alt}"
                )
            # Honest case: the low-carbon choice is the more expensive one.
            return (
                f"Acting now costs EUR {abs(delta):.0f} more than {alt}. The agent "
                f"recommends it on carbon grounds, not cost -- override if the budget "
                f"weighting says otherwise"
            )
        if baseline.get("direction") == "only_option":
            return "No eligible alternative cleared the risk gate"
        return (
            f"EUR {baseline['cost_saved_eur']:.0f} lower cost than an immediate "
            f"dedicated call-out ({baseline['cost_saved_pct']:.0f}% reduction)"
        )

    @staticmethod
    def _sustainability_reason(baseline: Dict[str, float]) -> str:
        if baseline.get("direction") == "acting_now_avoids_waste":
            return (
                f"{baseline['co2_saved_kg']:.1f} kg CO2e avoided by not waiting "
                f"({baseline['co2_saved_pct']:.0f}% lower than deferring)"
            )
        if baseline.get("direction") == "only_option":
            return "Deferral options were blocked on reliability risk"
        return (
            f"{baseline['co2_saved_kg']:.1f} kg CO2e avoided "
            f"({baseline['co2_saved_pct']:.0f}% reduction)"
        )

    @staticmethod
    def _breakeven(
        options: List[OptionEvaluation], grid_g_per_kwh: float, waste
    ) -> Dict[str, Any]:
        """At what daily waste does deferring stop being carbon-positive?"""
        repair = next((o for o in options if o.option == REPAIR_NOW), None)
        defer = next((o for o in options if o.option == DEFER_TO_PLANNED_VISIT), None)
        if repair is None or defer is None or defer.defer_days <= 0:
            return {}
        travel_avoided = repair.travel_co2_kg - defer.travel_co2_kg
        threshold = breakeven_waste_kwh_per_day(
            travel_avoided, defer.defer_days, grid_g_per_kwh
        )
        return {
            "threshold_kwh_per_day": round(threshold, 1),
            "actual_kwh_per_day": round(waste.excess_kwh_per_day, 1),
            "deferral_is_carbon_positive": waste.excess_kwh_per_day < threshold,
            "explanation": (
                f"On a {grid_g_per_kwh:.0f} gCO2/kWh grid, deferring "
                f"{defer.defer_days:.0f} days pays back the avoided trip only if the "
                f"machine wastes less than {threshold:.0f} kWh/day. It wastes "
                f"{waste.excess_kwh_per_day:.0f}."
            ),
        }

    @staticmethod
    def _risk_label(chosen: OptionEvaluation) -> str:
        if chosen.option == REPAIR_NOW:
            return "Low"
        risk = chosen.risk or {}
        lb = risk.get("ttf_lower_bound_days")
        if lb is None:
            return "Unquantified"
        headroom = lb - chosen.defer_days
        if headroom > 7:
            return "Low"
        if headroom > 2:
            return "Moderate"
        return "Elevated"

    @staticmethod
    def _service_date(defer_days: float) -> str:
        return (datetime.now(timezone.utc) + timedelta(days=defer_days)).strftime("%Y-%m-%d")

    def _build_tool_plan(
        self, device_id: str, chosen: OptionEvaluation, waste, logistics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Tool arguments for the Orchestrator to execute via the gateway.

        The agent does not call tools itself. It hands over arguments, which the
        Orchestrator runs through the existing controlled tool layer.
        """
        if chosen.option == CONTINUE_MONITORING:
            return {
                "tool": None,
                "arguments": {},
                "rationale": (
                    f"Re-evaluate in {chosen.defer_days:.0f} days. Estimated "
                    f"{chosen.energy_waste_kwh:.0f} kWh wasted in the meantime."
                ),
            }

        part_key = PART_FOR_FAULT.get(waste.fault_mode, "bearing")
        if not logistics.get("spare_part_available", True):
            return {
                "tool": "create-work-order",
                "arguments": {
                    "work_order_type": "procurement",
                    "priority": "high",
                    "description": (
                        f"Procure {part_key} for {device_id} ahead of maintenance on "
                        f"{self._service_date(chosen.defer_days)}."
                    ),
                },
                "rationale": "Part unavailable; procurement precedes the scheduled visit.",
            }

        return {
            "tool": "schedule-maintenance",
            "arguments": {
                "device_id": device_id,
                "maintenance_type": "preventive",
                "scheduled_date": self._service_date(chosen.defer_days),
            },
            "rationale": (
                f"Date chosen by the Sustainability Agent, inside the "
                f"{chosen.risk.get('coverage_level', 0.9):.0%} conformal life bound."
            ),
        }

    @staticmethod
    def _batching_summary(
        device_id: str, batching: Optional[BatchingResult], logistics: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if batching is None:
            return None
        kg_per_km = TRAVEL_FACTORS["van_diesel_average"].value
        return {
            "headline": batching.headline(kg_per_km),
            "trips_before": batching.trips_before,
            "trips_after": batching.trips_after,
            "km_saved": batching.total_km_saved,
            "co2_saved_kg": batching.co2_saved_kg(kg_per_km),
            "trips": [
                {
                    "service_day": t.service_day,
                    "devices": t.devices,
                    "route_km": t.route_km,
                    "km_saved": t.km_saved,
                }
                for t in batching.trips
            ],
        }