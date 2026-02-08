#!/usr/bin/env python3
"""Historical backfill: generate monthly snapshots from 2020 to present.

Queries the USGS FDSN API month-by-month and saves a snapshot per month
to the specified history directory.  Uses ``heuristic`` scoring because
ShakeMap data is only available for the most recent 30 days via the USGS
significant-earthquakes feed.

Usage::

    uv run python scripts/backfill.py --history-dir output/history

DISCLAIMER
----------
Airport list reflects current OurAirports state, not historical operational
dates.  Large airports are mostly stable post-2015, but results for
2020-2022 may include airports that were not yet operational.

Historical snapshots use *heuristic* scoring only.  PAGER alert levels may
be inaccurate for past months.
"""

from __future__ import annotations

import calendar
import logging
import time
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress

from seismic_risk.config import SeismicRiskConfig
from seismic_risk.history import save_snapshot
from seismic_risk.pipeline import run_pipeline

app = typer.Typer(help="Historical backfill for seismic risk snapshots.")
console = Console()
logger = logging.getLogger("seismic_risk.backfill")


def generate_month_ranges(
    start_year: int,
    start_month: int,
    end_date: date | None = None,
) -> list[tuple[date, date, date]]:
    """Generate ``(first_day, last_day, snapshot_date)`` for each month.

    Returns months from *(start_year, start_month)* up to but **not
    including** the month containing *end_date* (defaults to today).
    The *snapshot_date* equals *last_day* for each month.
    """
    if end_date is None:
        end_date = date.today()

    months: list[tuple[date, date, date]] = []
    year, month = start_year, start_month

    while True:
        first_day = date(year, month, 1)
        if first_day >= date(end_date.year, end_date.month, 1):
            break

        _, last_day_num = calendar.monthrange(year, month)
        last_day = date(year, month, last_day_num)
        months.append((first_day, last_day, last_day))

        if month == 12:
            year += 1
            month = 1
        else:
            month += 1

    return months


@app.command()
def backfill(
    history_dir: Annotated[
        Path, typer.Option("--history-dir", help="Directory for snapshot history."),
    ],
    start_year: Annotated[
        int, typer.Option("--start-year", help="First year to backfill."),
    ] = 2020,
    start_month: Annotated[
        int, typer.Option("--start-month", help="First month to backfill (1-12)."),
    ] = 1,
    min_magnitude: Annotated[
        float, typer.Option("--min-magnitude", help="Minimum earthquake magnitude."),
    ] = 5.0,
    delay: Annotated[
        float, typer.Option("--delay", help="Seconds between API requests."),
    ] = 1.0,
    min_quakes: Annotated[
        int, typer.Option("--min-quakes", help="Minimum quakes per country to qualify."),
    ] = 3,
    max_distance: Annotated[
        float, typer.Option("--max-distance", help="Max airport exposure distance (km)."),
    ] = 200.0,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable debug logging."),
    ] = False,
) -> None:
    """Generate monthly snapshots from historical USGS data."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    console.print("[bold yellow]DISCLAIMER[/bold yellow]")
    console.print(
        "Historical snapshots use 'heuristic' scoring only.\n"
        "ShakeMap-based scoring is unavailable for historical periods.\n"
        "Airport list reflects current OurAirports state, not historical\n"
        "operational dates.\n"
    )

    months = generate_month_ranges(start_year, start_month)
    if not months:
        console.print("[yellow]No complete months to backfill.[/yellow]")
        raise typer.Exit()

    console.print(
        f"Backfilling [bold]{len(months)}[/bold] months: "
        f"{months[0][0].isoformat()} to {months[-1][1].isoformat()}\n"
    )

    succeeded = 0
    failed = 0

    with Progress(console=console) as progress:
        task = progress.add_task("Backfilling...", total=len(months))

        for first_day, last_day, snapshot_date in months:
            label = f"{first_day.year}-{first_day.month:02d}"
            progress.update(task, description=f"Processing {label}...")

            config = SeismicRiskConfig(
                min_magnitude=min_magnitude,
                days_lookback=30,
                min_quakes_per_country=min_quakes,
                max_airport_distance_km=max_distance,
                scoring_method="heuristic",
                cache_enabled=True,
                starttime=first_day.isoformat(),
                endtime=last_day.isoformat(),
            )

            try:
                results = run_pipeline(config)
                save_snapshot(
                    results,
                    history_dir=history_dir,
                    scoring_method="heuristic",
                    snapshot_date=snapshot_date,
                )
                succeeded += 1
                logger.info(
                    "%s: %d countries, %d exposed airports",
                    label,
                    len(results),
                    sum(len(r.exposed_airports) for r in results),
                )
            except Exception:
                logger.exception("Failed to process %s", label)
                failed += 1

            progress.advance(task)
            time.sleep(delay)

    console.print(f"\n[green]Done![/green] {succeeded} succeeded, {failed} failed.")
    console.print(f"Snapshots saved to {history_dir}")


if __name__ == "__main__":
    app()
