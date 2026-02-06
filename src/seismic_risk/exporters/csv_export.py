"""CSV exporter for seismic risk results."""

from __future__ import annotations

import csv
from pathlib import Path

from seismic_risk.models import CountryRiskResult

FIELDNAMES = [
    "country",
    "iso_alpha3",
    "iso_alpha2",
    "region",
    "capital",
    "population",
    "risk_score",
    "earthquake_count",
    "avg_magnitude",
    "pager_alert",
    "tsunami_warning",
    "significant_events",
    "airport_name",
    "iata_code",
    "municipality",
    "latitude",
    "longitude",
    "closest_quake_km",
    "exposure_score",
    "nearby_quake_count",
    "strongest_quake_mag",
    "strongest_quake_date",
]


def export_csv(
    results: list[CountryRiskResult],
    output_path: Path,
) -> Path:
    """Export risk results as a flat CSV with one row per exposed airport."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()

        for result in results:
            strongest = result.strongest_earthquake
            for airport in sorted(
                result.exposed_airports,
                key=lambda a: a.exposure_score,
                reverse=True,
            ):
                writer.writerow({
                    "country": result.country,
                    "iso_alpha3": result.iso_alpha3,
                    "iso_alpha2": result.iso_alpha2,
                    "region": result.region,
                    "capital": result.capital,
                    "population": result.population,
                    "risk_score": result.seismic_hub_risk_score,
                    "earthquake_count": result.earthquake_count,
                    "avg_magnitude": round(result.avg_magnitude, 2),
                    "pager_alert": result.highest_pager_alert or "",
                    "tsunami_warning": result.tsunami_warning_issued,
                    "significant_events": result.significant_events_count,
                    "airport_name": airport.name,
                    "iata_code": airport.iata_code,
                    "municipality": airport.municipality,
                    "latitude": airport.latitude,
                    "longitude": airport.longitude,
                    "closest_quake_km": airport.closest_quake_distance_km,
                    "exposure_score": airport.exposure_score,
                    "nearby_quake_count": len(airport.nearby_quakes),
                    "strongest_quake_mag": strongest.magnitude if strongest else "",
                    "strongest_quake_date": strongest.date if strongest else "",
                })

    return output_path
