"""CSV exporter for seismic risk results."""

from __future__ import annotations

import csv
from pathlib import Path

from seismic_risk.models import CountryRiskResult

FIELDNAMES = [
    "country",
    "iso_alpha3",
    "risk_score",
    "pager_alert",
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
                    "risk_score": result.seismic_hub_risk_score,
                    "pager_alert": result.highest_pager_alert or "",
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
