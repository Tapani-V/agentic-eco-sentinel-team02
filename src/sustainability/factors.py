"""
Emission factor registry.

Design rule for this module: NO BARE CONSTANTS.
Every factor carries its source, publication year and unit, so the agent can
cite provenance for any gram of CO2e it reports. If a judge asks "where does
0.24 come from?", `EmissionFactor.cite()` answers it.

Factors that are contested or site-specific are marked `needs_local_override`
so they show up in the audit report instead of silently propagating.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(frozen=True)
class EmissionFactor:
    key: str
    value: float
    unit: str
    source: str
    source_year: int
    notes: str = ""
    needs_local_override: bool = False

    def cite(self) -> str:
        base = f"{self.value} {self.unit} ({self.source}, {self.source_year})"
        if self.needs_local_override:
            base += " [DEFAULT — override with site data]"
        return base


# ---------------------------------------------------------------------------
# Travel
# ---------------------------------------------------------------------------
# UK DESNZ/DEFRA GHG conversion factors are the usual citable public source for
# vehicle factors. Verify the exact workbook cell for your reporting year before
# using these in anything that leaves the hackathon room -- the value differs by
# van class (Class I/II/III) and by TTW vs TTW+WTT scope.
TRAVEL_FACTORS: Dict[str, EmissionFactor] = {
    "van_diesel_average": EmissionFactor(
        key="van_diesel_average",
        value=0.24,
        unit="kgCO2e/km",
        source="UK DESNZ/DEFRA GHG conversion factors, average diesel van, tank-to-wheel",
        source_year=2025,
        notes="Reconcile against the exact workbook cell for your van class.",
        needs_local_override=True,
    ),
    "van_electric_average": EmissionFactor(
        key="van_electric_average",
        value=0.20,
        unit="kWh/km",
        source="Fleet average electric LCV consumption",
        source_year=2025,
        notes="Unit is ENERGY not CO2 -- multiply by live grid intensity.",
        needs_local_override=True,
    ),
    "car_medium_diesel": EmissionFactor(
        key="car_medium_diesel",
        value=0.17,
        unit="kgCO2e/km",
        source="UK DESNZ/DEFRA GHG conversion factors, medium diesel car, tank-to-wheel",
        source_year=2025,
        needs_local_override=True,
    ),
}


# ---------------------------------------------------------------------------
# Embodied carbon of spare parts
# ---------------------------------------------------------------------------
# In the AWS build these come from a Bedrock Knowledge Base over LCA/EPD
# documents so the agent can quote the source document per part. The dict below
# is the offline fallback used when the KB is unreachable.
PART_EMBODIED_CARBON: Dict[str, EmissionFactor] = {
    "bearing": EmissionFactor(
        key="bearing",
        value=12.0,
        unit="kgCO2e/unit",
        source="Steel component LCA proxy (cradle-to-gate)",
        source_year=2024,
        needs_local_override=True,
    ),
    "seal": EmissionFactor(
        key="seal",
        value=3.5,
        unit="kgCO2e/unit",
        source="Elastomer component LCA proxy (cradle-to-gate)",
        source_year=2024,
        needs_local_override=True,
    ),
    "valve": EmissionFactor(
        key="valve",
        value=28.0,
        unit="kgCO2e/unit",
        source="Cast/machined metal component LCA proxy (cradle-to-gate)",
        source_year=2024,
        needs_local_override=True,
    ),
}


# ---------------------------------------------------------------------------
# Fallback grid intensities, used ONLY when the live API is unavailable.
# ---------------------------------------------------------------------------
FALLBACK_GRID_INTENSITY: Dict[str, EmissionFactor] = {
    "FI": EmissionFactor(
        key="FI",
        value=70.0,
        unit="gCO2/kWh",
        source="Fingrid annual emission coefficient, Finnish electricity system",
        source_year=2024,
        notes="Fallback only. Live value comes from Fingrid dataset 265/266.",
    ),
    "PL": EmissionFactor(
        key="PL",
        value=650.0,
        unit="gCO2/kWh",
        source="Published national grid average, coal-dominant system",
        source_year=2024,
        notes="Fallback only. Use ElectricityMaps live where available.",
    ),
    "DE": EmissionFactor(
        key="DE",
        value=350.0,
        unit="gCO2/kWh",
        source="Published national grid average",
        source_year=2024,
    ),
    "FR": EmissionFactor(
        key="FR",
        value=60.0,
        unit="gCO2/kWh",
        source="Published national grid average, nuclear-dominant system",
        source_year=2024,
    ),
    "DEFAULT": EmissionFactor(
        key="DEFAULT",
        value=400.0,
        unit="gCO2/kWh",
        source="Global average electricity carbon intensity",
        source_year=2024,
        needs_local_override=True,
    ),
}


@dataclass
class EconomicFactors:
    """Money-side inputs. Site-specific: always override from the CMMS."""

    electricity_price_eur_per_kwh: float = 0.12
    technician_cost_eur_per_hour: float = 65.0
    vehicle_cost_eur_per_km: float = 0.45
    unplanned_downtime_cost_eur_per_hour: float = 2500.0
    planned_downtime_cost_eur_per_hour: float = 400.0
    source: str = "site defaults -- override from CMMS"


def audit_factors() -> Dict[str, list]:
    """Return every factor still on a default, for the provenance slide."""
    needs_override = []
    grounded = []
    for registry in (TRAVEL_FACTORS, PART_EMBODIED_CARBON, FALLBACK_GRID_INTENSITY):
        for factor in registry.values():
            (needs_override if factor.needs_local_override else grounded).append(
                f"{factor.key}: {factor.cite()}"
            )
    return {"grounded": grounded, "needs_local_override": needs_override}
