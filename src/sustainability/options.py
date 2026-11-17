"""
Maintenance option enumeration and scoring.

Three options, deliberately. A fourth (replace the asset) needs an embodied-carbon
payback model that is a project of its own; three options done properly beat four
done thinly.

Scoring is lexicographic, not a single weighted blob:

  Stage 1 -- SAFETY GATE. The conformal deferral gate either permits an option or
             it does not. Nothing on the cost or carbon side can buy its way past
             a blocked option. This is what stops the agent trading safety for
             carbon, which is the single question every judge will ask.

  Stage 2 -- Among permitted options, minimise a normalised weighted sum of cost
             and CO2e. Weights are explicit and printed in the output so the
             recommendation is auditable rather than oracular.

Every option reports its full breakdown, so the dashboard can show the tradeoff
table rather than a bare verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.sustainability.conformal import DeferralVerdict
from src.sustainability.energy import EnergyWaste, waste_over_window
from src.sustainability.factors import EconomicFactors, TRAVEL_FACTORS

REPAIR_NOW = "REPAIR_NOW"
DEFER_TO_PLANNED_VISIT = "DEFER_TO_PLANNED_VISIT"
CONTINUE_MONITORING = "CONTINUE_MONITORING"


@dataclass
class OptionEvaluation:
    option: str
    defer_days: float
    permitted: bool
    blocked_reason: Optional[str]

    travel_km: float
    travel_co2_kg: float
    travel_cost_eur: float

    energy_waste_kwh: float
    energy_waste_co2_kg: float
    energy_waste_cost_eur: float

    parts_co2_kg: float
    labour_cost_eur: float
    downtime_cost_eur: float

    total_co2_kg: float
    total_cost_eur: float

    grid_g_per_kwh: float
    grid_source: str
    risk: Dict = field(default_factory=dict)
    score: Optional[float] = None
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "option": self.option,
            "defer_days": self.defer_days,
            "permitted": self.permitted,
            "blocked_reason": self.blocked_reason,
            "co2_kg": {
                "travel": round(self.travel_co2_kg, 2),
                "energy_waste": round(self.energy_waste_co2_kg, 2),
                "parts_embodied": round(self.parts_co2_kg, 2),
                "total": round(self.total_co2_kg, 2),
            },
            "cost_eur": {
                "travel": round(self.travel_cost_eur, 2),
                "energy_waste": round(self.energy_waste_cost_eur, 2),
                "labour": round(self.labour_cost_eur, 2),
                "downtime": round(self.downtime_cost_eur, 2),
                "total": round(self.total_cost_eur, 2),
            },
            "travel_km": round(self.travel_km, 1),
            "wasted_kwh": round(self.energy_waste_kwh, 1),
            "grid_intensity_g_per_kwh": round(self.grid_g_per_kwh, 1),
            "grid_source": self.grid_source,
            "risk": self.risk,
            "score": round(self.score, 4) if self.score is not None else None,
            "notes": self.notes,
        }


@dataclass
class ScoringWeights:
    """Explicit and printed in the output. Never a hidden constant."""

    cost_weight: float = 0.5
    co2_weight: float = 0.5

    def normalised(self) -> "ScoringWeights":
        total = self.cost_weight + self.co2_weight
        if total <= 0:
            raise ValueError("weights must sum to a positive number")
        return ScoringWeights(self.cost_weight / total, self.co2_weight / total)

    def describe(self) -> str:
        n = self.normalised()
        return f"cost {n.cost_weight:.0%} / CO2 {n.co2_weight:.0%}"


def build_option(
    *,
    option: str,
    defer_days: float,
    travel_km: float,
    energy_waste: EnergyWaste,
    grid_g_per_kwh: float,
    grid_source: str,
    economics: EconomicFactors,
    parts_co2_kg: float = 0.0,
    service_hours: float = 2.0,
    planned_downtime_hours: float = 0.0,
    unplanned_downtime_hours: float = 0.0,
    travel_factor_key: str = "van_diesel_average",
    verdict: Optional[DeferralVerdict] = None,
    notes: str = "",
) -> OptionEvaluation:
    """Cost and carbon a single option end to end."""
    travel_factor = TRAVEL_FACTORS[travel_factor_key]
    travel_co2 = travel_km * travel_factor.value
    travel_cost = travel_km * economics.vehicle_cost_eur_per_km

    window = waste_over_window(
        energy_waste,
        days=defer_days,
        grid_g_per_kwh=grid_g_per_kwh,
        price_eur_per_kwh=economics.electricity_price_eur_per_kwh,
    )

    labour_cost = service_hours * economics.technician_cost_eur_per_hour
    downtime_cost = (
        planned_downtime_hours * economics.planned_downtime_cost_eur_per_hour
        + unplanned_downtime_hours * economics.unplanned_downtime_cost_eur_per_hour
    )

    total_co2 = travel_co2 + window["co2_kg"] + parts_co2_kg
    total_cost = travel_cost + window["cost_eur"] + labour_cost + downtime_cost

    permitted = True
    blocked_reason = None
    risk: Dict = {}
    if verdict is not None:
        risk = verdict.to_dict()
        permitted = verdict.permitted
        if not permitted:
            blocked_reason = verdict.reason

    return OptionEvaluation(
        option=option,
        defer_days=defer_days,
        permitted=permitted,
        blocked_reason=blocked_reason,
        travel_km=travel_km,
        travel_co2_kg=travel_co2,
        travel_cost_eur=travel_cost,
        energy_waste_kwh=window["wasted_kwh"],
        energy_waste_co2_kg=window["co2_kg"],
        energy_waste_cost_eur=window["cost_eur"],
        parts_co2_kg=parts_co2_kg,
        labour_cost_eur=labour_cost,
        downtime_cost_eur=downtime_cost,
        total_co2_kg=total_co2,
        total_cost_eur=total_cost,
        grid_g_per_kwh=grid_g_per_kwh,
        grid_source=grid_source,
        risk=risk,
        notes=notes,
    )


def score_options(
    options: List[OptionEvaluation],
    weights: ScoringWeights = ScoringWeights(),
    baseline_option: str = REPAIR_NOW,
) -> List[OptionEvaluation]:
    """Score each option as a ratio to the conservative baseline (repair now).

    Deliberately NOT min-max normalisation. With only two eligible options,
    min-max forces one to 0 and the other to 1 on every axis, so at equal
    weights everything ties at 0.5 and the recommendation is decided by
    tie-breaking noise. Ratio-to-baseline keeps the magnitudes: an option at
    3.8x the baseline's carbon is visibly 3.8x, and the score means something.

    Score of 1.0 == same blended impact as repairing now. Below 1.0 is better.
    """
    w = weights.normalised()
    permitted = [o for o in options if o.permitted]
    if not permitted:
        return options

    baseline = next((o for o in options if o.option == baseline_option), None)
    if baseline is None:
        baseline = max(permitted, key=lambda o: o.total_cost_eur)

    cost_ref = baseline.total_cost_eur or 1e-9
    co2_ref = baseline.total_co2_kg or 1e-9

    for o in permitted:
        o.score = (
            w.cost_weight * (o.total_cost_eur / cost_ref)
            + w.co2_weight * (o.total_co2_kg / co2_ref)
        )
    return options


def breakeven_waste_kwh_per_day(
    travel_co2_avoided_kg: float, defer_days: float, grid_g_per_kwh: float
) -> float:
    """Daily energy waste at which deferring stops being carbon-positive.

    Above this figure the machine wastes more carbon while waiting than the
    avoided van trip saves. It is the single most useful number the agent
    produces, because it shows the decision has a threshold rather than a
    preference -- and the threshold moves with the grid.
    """
    if defer_days <= 0 or grid_g_per_kwh <= 0:
        return float("inf")
    return (travel_co2_avoided_kg * 1000.0) / (grid_g_per_kwh * defer_days)


def select_recommendation(
    options: List[OptionEvaluation],
) -> Optional[OptionEvaluation]:
    """Lowest score among permitted options. None if every option is blocked."""
    permitted = [o for o in options if o.permitted and o.score is not None]
    if not permitted:
        return None
    return min(permitted, key=lambda o: o.score)


def comparison_table(options: List[OptionEvaluation]) -> List[dict]:
    """Flat rows for the dashboard. Blocked options stay visible on purpose --
    showing what the agent rejected, and why, is most of the explainability."""
    rows = []
    for o in sorted(
        options, key=lambda x: (not x.permitted, x.score if x.score is not None else 1e9)
    ):
        rows.append(
            {
                "option": o.option,
                "defer_days": o.defer_days,
                "status": "eligible" if o.permitted else "blocked",
                "total_co2_kg": round(o.total_co2_kg, 1),
                "total_cost_eur": round(o.total_cost_eur, 0),
                "travel_km": round(o.travel_km, 0),
                "wasted_kwh": round(o.energy_waste_kwh, 0),
                "reason": o.blocked_reason or o.notes,
            }
        )
    return rows
