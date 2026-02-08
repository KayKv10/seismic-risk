"""Markdown exporter for seismic risk results."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from seismic_risk.history import TrendSummary
from seismic_risk.models import CountryRiskResult


def _trend_cell(iso3: str, trends: TrendSummary) -> str:
    """Return a trend indicator string for the given country."""
    ct = trends.country_trends.get(iso3)
    if ct is None or ct.is_new:
        return "NEW"
    if ct.score_delta > 0.5:
        return f"+{ct.score_delta:.1f}"
    if ct.score_delta < -0.5:
        return f"{ct.score_delta:.1f}"
    return "~"


def export_markdown(
    results: list[CountryRiskResult],
    output_path: Path,
    *,
    trends: TrendSummary | None = None,
) -> Path:
    """Export risk results as Markdown with country summary and airport detail tables."""
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        "# Seismic Risk Report",
        f"Generated: {timestamp}",
        "",
    ]

    # -- Trend Summary section (only when history > 1 day) --
    if trends is not None and trends.history_days > 1:
        lines.extend([
            "## Trend Summary",
            "",
            f"Based on {trends.history_days} days of tracking history.",
            "",
        ])

        if trends.new_countries:
            names = [
                trends.country_trends[iso3].country
                for iso3 in trends.new_countries
            ]
            lines.append(f"**New entries**: {', '.join(names)}")

        if trends.gone_countries:
            names = [
                trends.country_trends[iso3].country
                for iso3 in trends.gone_countries
            ]
            lines.append(f"**Dropped off**: {', '.join(names)}")

        movers = sorted(
            [
                ct for ct in trends.country_trends.values()
                if not ct.is_gone and not ct.is_new
            ],
            key=lambda ct: abs(ct.score_delta),
            reverse=True,
        )[:5]
        if movers:
            lines.extend(["", "**Top score changes**:", ""])
            for ct in movers:
                arrow = "+" if ct.score_delta > 0 else ""
                lines.append(
                    f"- {ct.country} ({ct.iso_alpha3}):"
                    f" {arrow}{ct.score_delta:.1f}"
                )

        lines.append("")

    # -- Country Summary table --
    if trends is not None:
        lines.extend([
            "## Country Summary",
            "",
            "| Country | ISO | Region | Score | Trend | Avg Mag"
            " | Strongest | Quakes | Airports | Alert"
            " | Tsunami | Sig. Events |",
            "|:--------|:----|:-------|------:|:------|--------:"
            "|:----------|-------:|---------:|:------"
            "|:--------|------------:|",
        ])
    else:
        lines.extend([
            "## Country Summary",
            "",
            "| Country | ISO | Region | Score | Avg Mag | Strongest | Quakes"
            " | Airports | Alert | Tsunami | Sig. Events |",
            "|:--------|:----|:-------|------:|--------:|:----------|-------:"
            "|---------:|:------|:--------|------------:|",
        ])

    for r in results:
        strongest = r.strongest_earthquake
        strongest_str = (
            f"M{strongest.magnitude} ({strongest.date})" if strongest else "-"
        )
        if trends is not None:
            trend_str = _trend_cell(r.iso_alpha3, trends)
            lines.append(
                f"| {r.country} | {r.iso_alpha3} | {r.region}"
                f" | {r.seismic_hub_risk_score:.1f}"
                f" | {trend_str}"
                f" | {r.avg_magnitude:.1f} | {strongest_str}"
                f" | {r.earthquake_count} | {len(r.exposed_airports)}"
                f" | {r.highest_pager_alert or '-'}"
                f" | {'Yes' if r.tsunami_warning_issued else 'No'}"
                f" | {r.significant_events_count} |"
            )
        else:
            lines.append(
                f"| {r.country} | {r.iso_alpha3} | {r.region}"
                f" | {r.seismic_hub_risk_score:.1f}"
                f" | {r.avg_magnitude:.1f} | {strongest_str}"
                f" | {r.earthquake_count} | {len(r.exposed_airports)}"
                f" | {r.highest_pager_alert or '-'}"
                f" | {'Yes' if r.tsunami_warning_issued else 'No'}"
                f" | {r.significant_events_count} |"
            )

    # -- Airport Details table --
    # Check if any airport has ShakeMap PGA data
    has_pga = any(
        nq.pga_g is not None
        for r in results
        for ap in r.exposed_airports
        for nq in ap.nearby_quakes
    )

    if has_pga:
        lines.extend([
            "",
            "## Airport Details",
            "",
            "| Airport | IATA | Municipality | Country | Exposure"
            " | Max PGA (g) | Closest Quake (km) | Nearby Quakes |",
            "|:--------|:-----|:-------------|:--------|--------:"
            "|------------:|-------------------:|--------------:|",
        ])
    else:
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
            if has_pga:
                pga_vals = [nq.pga_g for nq in airport.nearby_quakes if nq.pga_g is not None]
                pga_str = f"{max(pga_vals):.4f}" if pga_vals else "-"
                lines.append(
                    f"| {airport.name} | {airport.iata_code}"
                    f" | {airport.municipality} | {r.country}"
                    f" | {airport.exposure_score:.1f}"
                    f" | {pga_str}"
                    f" | {airport.closest_quake_distance_km}"
                    f" | {len(airport.nearby_quakes)} |"
                )
            else:
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
