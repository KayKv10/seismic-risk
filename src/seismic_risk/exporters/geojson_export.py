"""GeoJSON exporter for seismic risk results."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from seismic_risk.geo import felt_radius_km
from seismic_risk.models import CountryRiskResult, Earthquake, ExposedAirport


def _make_airport_feature(
    airport: ExposedAirport,
    country_result: CountryRiskResult,
) -> dict[str, Any]:
    """Create a GeoJSON Feature for an airport."""
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [airport.longitude, airport.latitude],
        },
        "properties": {
            "feature_type": "airport",
            "name": airport.name,
            "iata_code": airport.iata_code,
            "municipality": airport.municipality,
            "country": country_result.country,
            "iso_alpha2": country_result.iso_alpha2,
            "iso_alpha3": country_result.iso_alpha3,
            "closest_quake_km": airport.closest_quake_distance_km,
            "exposure_score": airport.exposure_score,
            "nearby_quake_count": len(airport.nearby_quakes),
            "country_risk_score": country_result.seismic_hub_risk_score,
            "earthquake_count": country_result.earthquake_count,
            "pager_alert": country_result.highest_pager_alert,
        },
    }


def _make_earthquake_feature(
    earthquake: Earthquake,
    country_result: CountryRiskResult,
) -> dict[str, Any]:
    """Create a GeoJSON Feature for an earthquake."""
    date_str = datetime.fromtimestamp(
        earthquake.time_ms / 1000, tz=timezone.utc
    ).strftime("%Y-%m-%d")
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [earthquake.longitude, earthquake.latitude],
        },
        "properties": {
            "feature_type": "earthquake",
            "earthquake_id": earthquake.id,
            "magnitude": earthquake.magnitude,
            "depth_km": earthquake.depth_km,
            "felt_radius_km": felt_radius_km(earthquake.magnitude, earthquake.depth_km),
            "date": date_str,
            "place": earthquake.place,
            "country": country_result.country,
            "iso_alpha3": country_result.iso_alpha3,
        },
    }


def _make_connection_feature(
    airport: ExposedAirport,
    nq: Any,
) -> dict[str, Any]:
    """Create a GeoJSON LineString connecting an airport to a nearby earthquake."""
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [airport.longitude, airport.latitude],
                [nq.longitude, nq.latitude],
            ],
        },
        "properties": {
            "feature_type": "connection",
            "airport_iata": airport.iata_code,
            "earthquake_id": nq.earthquake_id,
            "distance_km": nq.distance_km,
            "exposure_contribution": nq.exposure_contribution,
            "pga_g": nq.pga_g,
            "mmi": nq.mmi,
        },
    }


def export_geojson(
    results: list[CountryRiskResult],
    output_path: Path,
) -> Path:
    """Export risk results as a GeoJSON FeatureCollection.

    Creates a FeatureCollection with three feature types:
    - "airport": Exposed airports with per-airport exposure scores
    - "earthquake": All earthquakes in qualifying countries
    - "connection": Lines linking airports to their nearby earthquakes

    GeoJSON coordinates are [longitude, latitude] per spec.
    """
    features: list[dict[str, Any]] = []
    total_quakes = 0

    for result in results:
        # Add airport features and their connections
        for airport in result.exposed_airports:
            features.append(_make_airport_feature(airport, result))
            for nq in airport.nearby_quakes:
                features.append(_make_connection_feature(airport, nq))

        # Add all earthquake features (deduplicated within each country)
        for eq in result.earthquakes:
            features.append(_make_earthquake_feature(eq, result))
            total_quakes += 1

    geojson = {
        "type": "FeatureCollection",
        "metadata": {
            "generated": datetime.now(tz=timezone.utc).isoformat(),
            "source": "seismic-risk",
            "country_count": len(results),
            "airport_count": sum(len(r.exposed_airports) for r in results),
            "earthquake_count": total_quakes,
        },
        "features": features,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2, ensure_ascii=False)

    return output_path
