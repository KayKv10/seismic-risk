"""Geographic utilities: Haversine distance and reverse geocoding."""

from __future__ import annotations

import math

import reverse_geocoder as rg


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance in km between two points on Earth."""
    earth_radius_km = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return earth_radius_km * 2 * math.asin(math.sqrt(a))


_MMI_THRESHOLD = 5.0  # MMI V: strong shaking, infrastructure concern
_MIN_FELT_RADIUS_KM = 5.0


def felt_radius_km(magnitude: float, depth_km: float) -> float:
    """Estimate the surface radius (km) where shaking reaches MMI V.

    Uses the Atkinson & Wald (2007) intensity prediction equation:
        MMI = 3.70 + 1.17*M - 1.26*ln(R) - 0.0012*R
    solved for MMI = 5.0 via Newton's method, then converts
    hypocentral distance to surface distance.

    Returns at least 5.0 km so that small/deep quakes remain visible.

    Reference:
        Atkinson, G. M. & Wald, D. J. (2007). "Did You Feel It?"
        Intensity Data: A Surprisingly Good Measure of Earthquake
        Ground Motion. Seismological Research Letters 78(3), 362-368.
    """
    # f(R) = c - 1.26*ln(R) - 0.0012*R = 0  where c = 3.70 + 1.17*M - MMI
    c = 3.70 + 1.17 * magnitude - _MMI_THRESHOLD

    # If c <= 0, even at R=1 km the MMI < V; return minimum
    if c <= 0:
        return _MIN_FELT_RADIUS_KM

    # Newton's method to solve for R_hypo
    r = 50.0  # initial guess (km)
    for _ in range(20):
        ln_r = math.log(r)
        f = c - 1.26 * ln_r - 0.0012 * r
        f_prime = -1.26 / r - 0.0012
        step = f / f_prime
        r_new = r - step
        if r_new <= 0:
            r_new = r / 2  # safeguard
        if abs(r_new - r) < 0.01:
            break
        r = r_new

    r_hypo = r  # hypocentral distance where MMI = V

    # Convert to surface distance
    depth = max(depth_km, 0.0)
    if r_hypo <= depth:
        return _MIN_FELT_RADIUS_KM

    d_surface = math.sqrt(r_hypo**2 - depth**2)
    return max(round(d_surface, 1), _MIN_FELT_RADIUS_KM)


def reverse_geocode_batch(
    coords: list[tuple[float, float]],
) -> list[dict[str, str]]:
    """Reverse-geocode a batch of (latitude, longitude) pairs to country codes."""
    return rg.search(coords)
