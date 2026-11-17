"""
Fleet-level trip batching.

One device deferred to Friday is a scheduling tweak. Three jobs across a region
merged into a single van run is an optimisation, and it produces the number that
goes on the slide: kilometres avoided.

This also makes the Sustainability Agent's job genuinely hard. Scoring one
device is arithmetic. Choosing which subset of pending jobs to co-schedule,
subject to each job's conformal deadline, is a real decision.

Algorithm: greedy seed-and-grow clustering. Jobs join a cluster if they are
within `radius_km` of the seed and their conformal deadlines admit a common
service date. Route cost is nearest-neighbour from the depot. Good enough for a
fleet of tens; swap in OR-Tools if you outgrow it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

EARTH_RADIUS_KM = 6371.0


def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


@dataclass
class PendingJob:
    device_id: str
    site_lat: float
    site_lon: float
    earliest_day: int          # days from today the job can start
    latest_day: int            # hard deadline from the conformal gate
    service_hours: float = 2.0
    site_name: str = ""

    def coords(self) -> Tuple[float, float]:
        return (self.site_lat, self.site_lon)


@dataclass
class TripPlan:
    service_day: int
    jobs: List[PendingJob]
    route_km: float
    solo_km_equivalent: float
    km_saved: float
    devices: List[str] = field(default_factory=list)

    def co2_saved_kg(self, kg_per_km: float) -> float:
        return self.km_saved * kg_per_km


@dataclass
class BatchingResult:
    trips: List[TripPlan]
    total_route_km: float
    total_solo_km: float
    total_km_saved: float
    trips_before: int
    trips_after: int

    def co2_saved_kg(self, kg_per_km: float) -> float:
        return round(self.total_km_saved * kg_per_km, 2)

    def headline(self, kg_per_km: float) -> str:
        return (
            f"{self.trips_before} separate call-outs merged into {self.trips_after} trips: "
            f"{self.total_solo_km:.0f} km cut to {self.total_route_km:.0f} km, "
            f"saving {self.total_km_saved:.0f} km and "
            f"{self.co2_saved_kg(kg_per_km):.1f} kg CO2e."
        )


def _route_length(depot: Tuple[float, float], stops: List[PendingJob]) -> float:
    """Nearest-neighbour round trip from depot through all stops and back."""
    if not stops:
        return 0.0
    remaining = list(stops)
    here = depot
    total = 0.0
    while remaining:
        nxt = min(remaining, key=lambda j: haversine_km(here, j.coords()))
        total += haversine_km(here, nxt.coords())
        here = nxt.coords()
        remaining.remove(nxt)
    total += haversine_km(here, depot)
    return total


def _solo_round_trips(depot: Tuple[float, float], stops: List[PendingJob]) -> float:
    return sum(2.0 * haversine_km(depot, j.coords()) for j in stops)


def plan_trips(
    jobs: List[PendingJob],
    depot: Tuple[float, float],
    radius_km: float = 60.0,
    max_jobs_per_trip: int = 4,
    max_hours_per_trip: float = 10.0,
    travel_speed_kmh: float = 80.0,
) -> BatchingResult:
    """Group pending jobs into shared van trips.

    Every job keeps its own conformal deadline. A cluster is only valid if some
    single day satisfies all members' [earliest, latest] windows, so batching can
    never push a device past the date its risk bound permits.
    """
    unassigned = sorted(jobs, key=lambda j: (j.latest_day, j.device_id))
    trips: List[TripPlan] = []

    while unassigned:
        seed = unassigned.pop(0)
        cluster = [seed]
        window_start, window_end = seed.earliest_day, seed.latest_day

        for candidate in list(unassigned):
            if len(cluster) >= max_jobs_per_trip:
                break
            if haversine_km(seed.coords(), candidate.coords()) > radius_km:
                continue

            new_start = max(window_start, candidate.earliest_day)
            new_end = min(window_end, candidate.latest_day)
            if new_start > new_end:
                continue  # deadlines incompatible -- respect the risk bound

            trial = cluster + [candidate]
            route_km = _route_length(depot, trial)
            service_hours = sum(j.service_hours for j in trial)
            if route_km / travel_speed_kmh + service_hours > max_hours_per_trip:
                continue

            cluster = trial
            window_start, window_end = new_start, new_end
            unassigned.remove(candidate)

        route_km = _route_length(depot, cluster)
        solo_km = _solo_round_trips(depot, cluster)
        # Schedule as late as the tightest deadline allows: maximum chance of
        # picking up further jobs, still inside every member's bound.
        service_day = window_end

        trips.append(
            TripPlan(
                service_day=service_day,
                jobs=cluster,
                route_km=round(route_km, 1),
                solo_km_equivalent=round(solo_km, 1),
                km_saved=round(solo_km - route_km, 1),
                devices=[j.device_id for j in cluster],
            )
        )

    total_route = sum(t.route_km for t in trips)
    total_solo = sum(t.solo_km_equivalent for t in trips)

    return BatchingResult(
        trips=trips,
        total_route_km=round(total_route, 1),
        total_solo_km=round(total_solo, 1),
        total_km_saved=round(total_solo - total_route, 1),
        trips_before=len(jobs),
        trips_after=len(trips),
    )


def marginal_travel_for_device(
    device_id: str, result: BatchingResult, depot: Tuple[float, float]
) -> Optional[Dict[str, float]]:
    """Travel cost attributable to one device once batched.

    Allocation matters for fairness: a device that joins an existing trip should
    not be charged a full round trip. Shared route kilometres are split evenly
    across the jobs on the trip, and reported against what a solo call-out to
    that site would have cost.
    """
    for trip in result.trips:
        if device_id not in trip.devices:
            continue
        job = next(j for j in trip.jobs if j.device_id == device_id)
        solo_km = 2.0 * haversine_km(depot, job.coords())
        allocated = trip.route_km / max(1, len(trip.jobs))
        return {
            "allocated_km": round(allocated, 1),
            "solo_km": round(solo_km, 1),
            "km_avoided": round(solo_km - allocated, 1),
            "trip_route_km": trip.route_km,
            "jobs_on_trip": len(trip.jobs),
            "service_day": trip.service_day,
        }
    return None
