"""
Grid carbon intensity providers.

This is the module that makes "carbon-aware scheduling" a real claim rather than
a slide. The same deferral decision flips sign depending on what the grid is
doing, so the number has to be live.

Providers, in order of preference:
  1. FingridProvider      -- Finland, real-time, 3-minute resolution, free API key
  2. ElectricityMapsProvider -- most of Europe, free tier
  3. StaticProvider       -- annual averages, always works, clearly labelled

Every provider returns a CarbonIntensity carrying `source` and `is_live`, so the
UI can show a "live" badge and the agent never silently passes off an annual
average as a real-time reading.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Protocol

from src.sustainability.factors import FALLBACK_GRID_INTENSITY

logger = logging.getLogger(__name__)

# Fingrid open data. Register free at https://data.fingrid.fi/en/instructions
# 265 = emission factor for electricity CONSUMED in Finland (includes import/export)
# 266 = emission factor of electricity PRODUCED in Finland
# 265 is the right one for a factory drawing from the grid.
FINGRID_API_BASE = "https://data.fingrid.fi/api"
FINGRID_DATASET_CONSUMPTION_EF = 265
FINGRID_DATASET_PRODUCTION_EF = 266


@dataclass
class CarbonIntensity:
    """gCO2 per kWh at a point in time."""

    g_per_kwh: float
    zone: str
    timestamp: datetime
    source: str
    is_live: bool
    is_forecast: bool = False

    def label(self) -> str:
        kind = "forecast" if self.is_forecast else ("live" if self.is_live else "annual avg")
        return f"{self.g_per_kwh:.0f} gCO2/kWh ({self.zone}, {kind}, {self.source})"


class IntensityProvider(Protocol):
    def current(self, zone: str) -> Optional[CarbonIntensity]: ...
    def forecast(self, zone: str, hours: int) -> List[CarbonIntensity]: ...


class FingridProvider:
    """Real-time Finnish grid carbon intensity.

    Rate limits are generous (10k requests/24h) but the agent may be called once
    per device in a fleet sweep, so results are cached for `cache_seconds`.
    """

    def __init__(self, api_key: Optional[str] = None, cache_seconds: int = 180):
        self.api_key = api_key or os.environ.get("FINGRID_API_KEY")
        self.cache_seconds = cache_seconds
        self._cache: Optional[CarbonIntensity] = None

    def _cache_valid(self) -> bool:
        if self._cache is None:
            return False
        age = (datetime.now(timezone.utc) - self._cache.timestamp).total_seconds()
        return age < self.cache_seconds

    def current(self, zone: str = "FI") -> Optional[CarbonIntensity]:
        if zone != "FI":
            return None
        if not self.api_key:
            logger.info("[Fingrid] No FINGRID_API_KEY set, falling back to static.")
            return None
        if self._cache_valid():
            return self._cache

        try:
            import requests  # imported lazily so the module works offline

            now = datetime.now(timezone.utc)
            params = {
                "startTime": (now - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "endTime": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "format": "json",
                "pageSize": 20,
                "sortBy": "startTime",
                "sortOrder": "desc",
            }
            resp = requests.get(
                f"{FINGRID_API_BASE}/datasets/{FINGRID_DATASET_CONSUMPTION_EF}/data",
                headers={"x-api-key": self.api_key},
                params=params,
                timeout=8,
            )
            resp.raise_for_status()
            payload = resp.json()
            rows = payload.get("data", payload if isinstance(payload, list) else [])
            if not rows:
                logger.warning("[Fingrid] Empty response for dataset %s", FINGRID_DATASET_CONSUMPTION_EF)
                return None

            latest = rows[0]
            self._cache = CarbonIntensity(
                g_per_kwh=float(latest["value"]),
                zone="FI",
                timestamp=datetime.now(timezone.utc),
                source=f"Fingrid open data, dataset {FINGRID_DATASET_CONSUMPTION_EF}",
                is_live=True,
            )
            return self._cache

        except Exception as exc:  # network, auth, schema drift -- all non-fatal
            logger.warning("[Fingrid] Live fetch failed (%s). Falling back.", exc)
            return None

    def forecast(self, zone: str = "FI", hours: int = 168) -> List[CarbonIntensity]:
        """Fingrid publishes wind and production forecasts that can be turned into
        an intensity forecast. Left as a documented extension: for the demo the
        agent uses the diurnal shape in `DiurnalShapeForecaster` instead."""
        return []


class ElectricityMapsProvider:
    """Covers zones outside Finland. Free tier requires a token."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ELECTRICITYMAPS_API_KEY")

    def current(self, zone: str) -> Optional[CarbonIntensity]:
        if not self.api_key:
            return None
        try:
            import requests

            resp = requests.get(
                "https://api.electricitymap.org/v3/carbon-intensity/latest",
                headers={"auth-token": self.api_key},
                params={"zone": zone},
                timeout=8,
            )
            resp.raise_for_status()
            data = resp.json()
            return CarbonIntensity(
                g_per_kwh=float(data["carbonIntensity"]),
                zone=zone,
                timestamp=datetime.now(timezone.utc),
                source="ElectricityMaps live",
                is_live=True,
            )
        except Exception as exc:
            logger.warning("[ElectricityMaps] Live fetch failed (%s).", exc)
            return None

    def forecast(self, zone: str, hours: int = 24) -> List[CarbonIntensity]:
        return []


class StaticProvider:
    """Always-works fallback. Clearly labelled as not live so the UI can say so."""

    def current(self, zone: str) -> CarbonIntensity:
        factor = FALLBACK_GRID_INTENSITY.get(zone, FALLBACK_GRID_INTENSITY["DEFAULT"])
        return CarbonIntensity(
            g_per_kwh=factor.value,
            zone=zone,
            timestamp=datetime.now(timezone.utc),
            source=factor.source,
            is_live=False,
        )

    def forecast(self, zone: str, hours: int = 168) -> List[CarbonIntensity]:
        base = self.current(zone)
        return [base for _ in range(hours)]


class GridIntensityService:
    """Tries live providers, falls back to static, never raises.

    A carbon number the demo can't produce is worse than a labelled estimate,
    so this class is deliberately unbreakable.
    """

    def __init__(self, providers: Optional[List[IntensityProvider]] = None):
        self.providers = providers or [FingridProvider(), ElectricityMapsProvider()]
        self.fallback = StaticProvider()

    def current(self, zone: str = "FI") -> CarbonIntensity:
        for provider in self.providers:
            try:
                result = provider.current(zone)
                if result is not None:
                    return result
            except Exception as exc:
                logger.warning("[GridIntensity] Provider %s failed: %s", provider, exc)
        return self.fallback.current(zone)

    def mean_over_window(self, zone: str, days: float) -> CarbonIntensity:
        """Average intensity expected over a deferral window.

        Uses live current value as the level and a flat shape. Replace with a
        real forecast when one is wired in -- the interface won't change.
        """
        current = self.current(zone)
        return CarbonIntensity(
            g_per_kwh=current.g_per_kwh,
            zone=zone,
            timestamp=current.timestamp,
            source=current.source + f" (held flat over {days:.1f}d window)",
            is_live=current.is_live,
            is_forecast=True,
        )
