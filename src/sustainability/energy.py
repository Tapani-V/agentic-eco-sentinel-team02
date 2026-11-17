"""
Degradation -> wasted energy -> CO2 and euros.

This is the module that fixes the biggest conceptual error in a naive
sustainability agent: treating "keep monitoring" as the zero-emission option.

A degraded machine is not idle. It is burning extra electricity every hour it
runs. Bearing wear adds friction; a worn impeller or valve makes the pump work
harder for the same hydraulic output. That waste is continuous, and over a
two-week deferral it can dwarf the emissions of the van trip you avoided.

Whether deferral is greener therefore depends on the grid. That is the whole
demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

# Fractional efficiency loss bands per fault mode, indexed by severity of
# degradation. Format: (loss at onset, loss at end-of-life).
#
# These bands are engineering estimates. In production they should be fitted
# per asset class from historical power draw vs. condition data -- which is
# exactly what the existing sensor history in Eco Sentinel enables. Flagged in
# the audit report so nobody mistakes them for measured values.
FAULT_EFFICIENCY_LOSS_BANDS: Dict[str, tuple] = {
    "bearing": (0.02, 0.14),
    "cavitation": (0.05, 0.25),
    "valve": (0.03, 0.18),
    "seal": (0.01, 0.08),
    "impeller": (0.04, 0.20),
    "misalignment": (0.02, 0.10),
    "unknown": (0.02, 0.10),
}

FAULT_KEYWORDS = {
    "bearing": ["bearing", "vibration"],
    "cavitation": ["cavitation"],
    "valve": ["valve", "pressure"],
    "seal": ["seal", "leak"],
    "impeller": ["impeller", "flow"],
    "misalignment": ["alignment", "misalign"],
}


@dataclass
class AssetEnergyProfile:
    """What the agent needs to know about the machine to price its waste."""

    device_id: str
    rated_power_kw: float
    duty_cycle: float = 0.85          # fraction of the day actually running
    baseline_efficiency: float = 0.80  # healthy operating efficiency

    def running_hours_per_day(self) -> float:
        return 24.0 * self.duty_cycle


@dataclass
class EnergyWaste:
    excess_kw: float
    excess_kwh_per_day: float
    efficiency_loss_fraction: float
    fault_mode: str
    basis: str

    def co2_kg_per_day(self, grid_g_per_kwh: float) -> float:
        return self.excess_kwh_per_day * grid_g_per_kwh / 1000.0

    def cost_eur_per_day(self, price_eur_per_kwh: float) -> float:
        return self.excess_kwh_per_day * price_eur_per_kwh


def classify_fault_mode(root_cause: str, anomalies: Optional[list] = None) -> str:
    """Map the Diagnosis Agent's free-text root cause onto an efficiency band."""
    haystack = (root_cause or "").lower()
    if anomalies:
        haystack += " " + " ".join(str(a).lower() for a in anomalies)

    for mode, keywords in FAULT_KEYWORDS.items():
        if any(kw in haystack for kw in keywords):
            return mode
    return "unknown"


def estimate_energy_waste(
    profile: AssetEnergyProfile,
    degradation_score: float,
    root_cause: str,
    anomalies: Optional[list] = None,
) -> EnergyWaste:
    """Estimate continuous excess power draw caused by the diagnosed fault.

    degradation_score is expected on [0, 1] where 1 is end-of-life. If your
    Health Agent emits a health score where 1 is healthy, invert before calling.
    """
    degradation_score = max(0.0, min(1.0, float(degradation_score)))
    mode = classify_fault_mode(root_cause, anomalies)
    loss_min, loss_max = FAULT_EFFICIENCY_LOSS_BANDS.get(
        mode, FAULT_EFFICIENCY_LOSS_BANDS["unknown"]
    )

    # Degradation-to-loss is superlinear: wear accelerates near end of life.
    loss_fraction = loss_min + (loss_max - loss_min) * (degradation_score ** 1.5)

    excess_kw = profile.rated_power_kw * loss_fraction
    excess_kwh_per_day = excess_kw * profile.running_hours_per_day()

    return EnergyWaste(
        excess_kw=round(excess_kw, 3),
        excess_kwh_per_day=round(excess_kwh_per_day, 2),
        efficiency_loss_fraction=round(loss_fraction, 4),
        fault_mode=mode,
        basis=(
            f"{profile.rated_power_kw} kW rated x {loss_fraction:.1%} efficiency loss "
            f"({mode} band, degradation {degradation_score:.2f}) "
            f"x {profile.running_hours_per_day():.1f} h/day"
        ),
    )


def waste_over_window(
    waste: EnergyWaste,
    days: float,
    grid_g_per_kwh: float,
    price_eur_per_kwh: float,
) -> Dict[str, float]:
    """Integrate the waste over a deferral window.

    Held flat over the window. A refinement worth doing if you have time: let
    degradation grow over the window so a long deferral is penalised twice --
    more days AND worse efficiency each day.
    """
    kwh = waste.excess_kwh_per_day * days
    return {
        "days": round(days, 2),
        "wasted_kwh": round(kwh, 1),
        "co2_kg": round(kwh * grid_g_per_kwh / 1000.0, 2),
        "cost_eur": round(kwh * price_eur_per_kwh, 2),
        "grid_g_per_kwh": round(grid_g_per_kwh, 1),
    }
