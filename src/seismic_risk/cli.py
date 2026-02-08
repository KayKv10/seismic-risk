"""CLI interface using Typer."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from seismic_risk import __version__
from seismic_risk.config import OutputFormat, ScoringMethod, SeismicRiskConfig
from seismic_risk.exporters import (
    export_csv,
    export_geojson,
    export_html,
    export_json,
    export_markdown,
)
from seismic_risk.models import CountryRiskResult
from seismic_risk.pipeline import run_pipeline

Exporter = Callable[[list[CountryRiskResult], Path], Path]

EXPORTERS: dict[str, Exporter] = {
    "json": export_json,
    "geojson": export_geojson,
    "html": export_html,
    "csv": export_csv,
    "markdown": export_markdown,
}

app = typer.Typer(
    name="seismic-risk",
    help="Real-time seismic risk scoring for global aviation infrastructure.",
    add_completion=False,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"seismic-risk {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-V",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """Seismic Risk — Real-time seismic risk scoring for aviation infrastructure."""


@app.command()
def run(
    min_magnitude: Annotated[
        float,
        typer.Option("--min-magnitude", "-m", help="Minimum earthquake magnitude."),
    ] = 5.0,
    days: Annotated[
        int,
        typer.Option("--days", "-d", help="Number of days to look back."),
    ] = 30,
    distance: Annotated[
        float,
        typer.Option("--distance", help="Max airport exposure distance in km."),
    ] = 200.0,
    min_quakes: Annotated[
        int,
        typer.Option("--min-quakes", help="Minimum quakes per country to qualify."),
    ] = 3,
    airport_type: Annotated[
        str,
        typer.Option("--airport-type", help="Airport type filter."),
    ] = "large_airport",
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output file path."),
    ] = Path("seismic_risk_output.json"),
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format: json, geojson, html, csv, markdown."),
    ] = "json",
    scorer: Annotated[
        ScoringMethod,
        typer.Option(
            "--scorer",
            help="Scoring method: 'shakemap' (PGA-based hybrid), 'heuristic', or 'legacy'.",
        ),
    ] = "shakemap",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logging."),
    ] = False,
    no_cache: Annotated[
        bool,
        typer.Option("--no-cache", help="Disable disk caching for airports/country data."),
    ] = False,
    history_dir: Annotated[
        Path | None,
        typer.Option("--history-dir", help="Directory for daily snapshot history."),
    ] = None,
) -> None:
    """Run the seismic risk assessment pipeline."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=[logging.StreamHandler()],
    )

    config = SeismicRiskConfig(
        min_magnitude=min_magnitude,
        days_lookback=days,
        min_quakes_per_country=min_quakes,
        max_airport_distance_km=distance,
        airport_type=airport_type,
        output_file=output,
        output_format=output_format,
        scoring_method=scorer,
        cache_enabled=not no_cache,
        history_dir=history_dir,
    )

    try:
        results = run_pipeline(config)
    except Exception as exc:
        console.print(f"[red]Pipeline failed:[/red] {exc}")
        raise typer.Exit(code=1) from None

    if not results:
        console.print("[yellow]No countries qualified for risk assessment.[/yellow]")
        raise typer.Exit()

    trends = None
    if config.history_dir is not None:
        from datetime import datetime, timezone

        from seismic_risk.history import compute_trends, load_history, save_snapshot

        history = load_history(config.history_dir)
        today_str = datetime.now(tz=timezone.utc).date().isoformat()
        prior_history = [s for s in history if s.date != today_str]
        trends = compute_trends(prior_history, results, config.scoring_method)
        save_snapshot(results, config.history_dir, config.scoring_method)

    if trends is not None and config.output_format in ("html", "markdown"):
        if config.output_format == "html":
            export_html(results, config.output_file, trends=trends)
        else:
            export_markdown(results, config.output_file, trends=trends)
    else:
        exporter = EXPORTERS[config.output_format]
        exporter(results, config.output_file)

    console.print()
    table = Table(title="Seismic Risk Assessment Results")
    table.add_column("Country", style="bold")
    table.add_column("ISO", style="dim")
    table.add_column("Score", justify="right", style="red")
    table.add_column("Quakes", justify="right")
    table.add_column("Airports", justify="right")
    table.add_column("Alert")

    for r in results:
        alert_display = {
            "red": "[red]red[/red]",
            "orange": "[dark_orange]orange[/dark_orange]",
            "yellow": "[yellow]yellow[/yellow]",
            "green": "[green]green[/green]",
        }.get(r.highest_pager_alert or "", r.highest_pager_alert or "-")

        table.add_row(
            r.country,
            r.iso_alpha3,
            str(r.seismic_hub_risk_score),
            str(r.earthquake_count),
            str(len(r.exposed_airports)),
            alert_display,
        )

    console.print(table)
    console.print(
        f"\n{config.output_format.upper()} written to [bold]{config.output_file}[/bold]"
    )
    console.print(f"Total countries: {len(results)}")
    console.print(
        f"Total exposed airports: {sum(len(r.exposed_airports) for r in results)}"
    )
