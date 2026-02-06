"""Markdown exporter for seismic risk results."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from seismic_risk.models import CountryRiskResult


def export_markdown(
    results: list[CountryRiskResult],
    output_path: Path,
) -> Path:
    """Export risk results as Markdown with country summary and airport detail tables."""
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        "# Seismic Risk Report",
        f"Generated: {timestamp}",
        "",
        "## Country Summary",
        "",
        "| Country | ISO | Region | Score | Avg Mag | Strongest | Quakes"
        " | Airports | Alert | Tsunami | Sig. Events |",
        "|:--------|:----|:-------|------:|--------:|:----------|-------:"
        "|---------:|:------|:--------|------------:|",
    ]

    for r in results:
        strongest = r.strongest_earthquake
        strongest_str = (
            f"M{strongest.magnitude} ({strongest.date})" if strongest else "-"
        )
        lines.append(
            f"| {r.country} | {r.iso_alpha3} | {r.region}"
            f" | {r.seismic_hub_risk_score:.1f}"
            f" | {r.avg_magnitude:.1f} | {strongest_str}"
            f" | {r.earthquake_count} | {len(r.exposed_airports)}"
            f" | {r.highest_pager_alert or '-'}"
            f" | {'Yes' if r.tsunami_warning_issued else 'No'}"
            f" | {r.significant_events_count} |"
        )

    lines.extend([
        "",
        "## Airport Details",
        "",
        "| Airport | IATA | Municipality | Country | Exposure"
        " | Closest Quake (km) | Nearby Quakes |",
        "|:--------|:-----|:-------------|:--------|--------:"
        "|-------------------:|--------------:|",
    ])

    for r in results:
        for airport in sorted(
            r.exposed_airports,
            key=lambda a: a.exposure_score,
            reverse=True,
        ):
            lines.append(
                f"| {airport.name} | {airport.iata_code}"
                f" | {airport.municipality} | {r.country}"
                f" | {airport.exposure_score:.1f}"
                f" | {airport.closest_quake_distance_km}"
                f" | {len(airport.nearby_quakes)} |"
            )

    lines.append("")  # trailing newline

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path
