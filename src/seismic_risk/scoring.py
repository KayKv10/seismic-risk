"""Seismic risk scoring and airport exposure calculation."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from seismic_risk.config import ScoringMethod
from seismic_risk.fetchers.shakemap import ShakeMapGrid, interpolate_pga
from seismic_risk.geo import haversine
from seismic_risk.models import (
    Airport,
    Earthquake,
    ExposedAirport,
    NearbyQuake,
    SignificantEvent,
    StrongestEarthquake,
)

ALERT_ORDER: dict[str, int] = {"green": 1, "yellow": 2, "orange": 3, "red": 4}


def _heuristic_contribution(magnitude: float, distance_km: float, depth_km: float) -> float:
    """Distance-weighted exposure contribution using GMPE-calibrated attenuation.

    Uses hypocentral distance, geometric spreading (R^-1.2), and anelastic
    absorption (e^-0.003R) to approximate real ground-motion decay.
    """
    r = math.sqrt(distance_km ** 2 + depth_km ** 2)
    energy = math.pow(10, 0.5 * magnitude)
    return energy / math.pow(r + 1, 1.2) * math.exp(-0.003 * r)


def find_exposed_airports(
    airports: list[Airport],
    earthquakes: list[Earthquake],
    max_distance_km: float = 200.0,
    shakemap_grids: dict[str, ShakeMapGrid] | None = None,
) -> list[ExposedAirport]:
    """Find airports within the exposure radius of at least one earthquake.

    Populates per-airport nearby_quakes and exposure_score.

    When *shakemap_grids* is provided, PGA from the ShakeMap grid is used
    as the exposure contribution (in %g) for quakes with available grids.
    Falls back to the heuristic formula for quakes without a grid or for
    airport locations outside the grid bounds.
    """
    exposed: list[ExposedAirport] = []
    for ap in airports:
        nearby: list[NearbyQuake] = []
        score = 0.0
        best = float("inf")

        for eq in earthquakes:
            d = haversine(ap.latitude, ap.longitude, eq.latitude, eq.longitude)
            if d <= max_distance_km:
                pga_g_val: float | None = None
                mmi_val: float | None = None

                if shakemap_grids and eq.id in shakemap_grids:
                    result = interpolate_pga(
                        shakemap_grids[eq.id], ap.latitude, ap.longitude,
                    )
                    if result is not None:
                        pga_pctg, mmi_interp = result
                        pga_g_val = round(pga_pctg / 100, 6)
                        mmi_val = round(mmi_interp, 1)
                        contribution = pga_pctg  # PGA in %g as contribution
                    else:
                        # Airport outside grid bounds — heuristic fallback
                        contribution = _heuristic_contribution(eq.magnitude, d, eq.depth_km)
                else:
                    # No grid for this quake — heuristic
                    contribution = _heuristic_contribution(eq.magnitude, d, eq.depth_km)

                score += contribution
                nearby.append(
                    NearbyQuake(
                        earthquake_id=eq.id,
                        magnitude=eq.magnitude,
                        latitude=eq.latitude,
                        longitude=eq.longitude,
                        depth_km=eq.depth_km,
                        time_ms=eq.time_ms,
                        place=eq.place,
                        distance_km=round(d, 1),
                        exposure_contribution=round(contribution, 2),
                        pga_g=pga_g_val,
                        mmi=mmi_val,
                    )
                )
                best = min(best, d)

        if nearby:
            nearby.sort(key=lambda q: q.distance_km)
            exposed.append(
                ExposedAirport(
                    name=ap.name,
                    iata_code=ap.iata_code,
                    latitude=round(ap.latitude, 6),
                    longitude=round(ap.longitude, 6),
                    municipality=ap.municipality,
                    closest_quake_distance_km=round(best, 1),
                    nearby_quakes=nearby,
                    exposure_score=round(score, 2),
                )
            )
    return exposed


def compute_seismic_stats(
    earthquakes: list[Earthquake],
) -> tuple[float, StrongestEarthquake]:
    """Compute average magnitude and strongest earthquake summary."""
    if not earthquakes:
        raise ValueError("Cannot compute stats for empty earthquake list")

    n = len(earthquakes)
    avg_mag = round(sum(eq.magnitude for eq in earthquakes) / n, 2)

    strongest = max(earthquakes, key=lambda eq: eq.magnitude)
    s_date = datetime.fromtimestamp(
        strongest.time_ms / 1000, tz=timezone.utc
    ).strftime("%Y-%m-%d")

    return avg_mag, StrongestEarthquake(
        magnitude=strongest.magnitude,
        date=s_date,
        depth_km=round(strongest.depth_km, 1),
        latitude=round(strongest.latitude, 4),
        longitude=round(strongest.longitude, 4),
    )


def compute_pager_context(
    earthquakes: list[Earthquake],
    significant_quakes: dict[str, SignificantEvent],
) -> tuple[str | None, int, bool, int]:
    """Extract PAGER alert context for a country's earthquakes.

    Returns (highest_alert, max_felt_reports, has_tsunami_warning, significant_count).
    """
    highest_alert: str | None = None
    max_felt: int = 0
    has_tsunami_warning: bool = False
    count = 0

    for eq in earthquakes:
        if eq.id in significant_quakes:
            s = significant_quakes[eq.id]
            count += 1
            if s.alert and ALERT_ORDER.get(s.alert, 0) > ALERT_ORDER.get(
                highest_alert or "", 0
            ):
                highest_alert = s.alert
            if s.felt > max_felt:
                max_felt = s.felt
            if s.tsunami:
                has_tsunami_warning = True

    return highest_alert, max_felt, has_tsunami_warning, count


def sum_airport_scores(exposed: list[ExposedAirport]) -> float:
    """Sum pre-computed per-airport exposure scores."""
    return round(sum(ap.exposure_score for ap in exposed), 2)


def calculate_exposure_score(
    airports: list[Airport],
    earthquakes: list[Earthquake],
    max_distance_km: float = 200.0,
) -> float:
    """Calculate distance-weighted exposure score.

    For each airport, sums exposure from all nearby earthquakes using
    GMPE-calibrated attenuation (see ``_heuristic_contribution``):

        exposure = sum( 10^(0.5 * mag) / (R + 1)^1.2 * e^(-0.003 * R) )

    where R = hypocentral distance (sqrt(epicentral² + depth²)).

    Returns the total exposure across all airports in the country.
    """
    total_exposure = 0.0

    for ap in airports:
        for eq in earthquakes:
            distance = haversine(ap.latitude, ap.longitude, eq.latitude, eq.longitude)
            if distance <= max_distance_km:
                total_exposure += _heuristic_contribution(
                    eq.magnitude, distance, eq.depth_km,
                )

    return round(total_exposure, 2)


def calculate_legacy_score(
    earthquake_count: int,
    avg_magnitude: float,
    exposed_airport_count: int,
) -> float:
    """Calculate the legacy Seismic Hub Risk Score.

    Formula: (earthquake_count * avg_magnitude) / exposed_airport_count

    This is the original formula, kept for backwards compatibility.
    """
    if exposed_airport_count == 0:
        raise ValueError("Cannot compute risk score with zero exposed airports")
    return round((earthquake_count * avg_magnitude) / exposed_airport_count, 2)


def calculate_risk_score(
    airports: list[Airport],
    earthquakes: list[Earthquake],
    max_distance_km: float = 200.0,
    method: ScoringMethod = "shakemap",
    # Legacy params (only used when method="legacy")
    earthquake_count: int | None = None,
    avg_magnitude: float | None = None,
    exposed_airport_count: int | None = None,
    # Pre-computed exposed airports (avoids redundant haversine)
    exposed_airports: list[ExposedAirport] | None = None,
) -> float:
    """Calculate risk score using the specified method.

    Args:
        airports: List of airports to evaluate
        earthquakes: List of earthquakes in the country
        max_distance_km: Maximum distance for exposure calculation
        method: Scoring method - "shakemap", "heuristic"/"exposure", or "legacy"
        earthquake_count: Required for legacy method
        avg_magnitude: Required for legacy method
        exposed_airport_count: Required for legacy method
        exposed_airports: Pre-computed exposed airports with scores (skips recomputation)

    Returns:
        Risk score (higher = more risk)
    """
    if method in ("shakemap", "exposure", "heuristic"):
        if exposed_airports is not None:
            return sum_airport_scores(exposed_airports)
        return calculate_exposure_score(airports, earthquakes, max_distance_km)
    elif method == "legacy":
        if earthquake_count is None or avg_magnitude is None or exposed_airport_count is None:
            raise ValueError(
                "Legacy method requires earthquake_count, avg_magnitude, and exposed_airport_count"
            )
        return calculate_legacy_score(earthquake_count, avg_magnitude, exposed_airport_count)
    else:
        raise ValueError(f"Unknown scoring method: {method}")
