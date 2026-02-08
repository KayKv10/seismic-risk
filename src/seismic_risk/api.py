"""FastAPI wrapper for the seismic risk pipeline."""

from __future__ import annotations

import logging
import tempfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, Response

from seismic_risk import __version__
from seismic_risk.config import OutputFormat, ScoringMethod, SeismicRiskConfig
from seismic_risk.exporters import (
    export_csv,
    export_geojson,
    export_html,
    export_markdown,
)
from seismic_risk.models import CountryRiskResult
from seismic_risk.pipeline import run_pipeline

logger = logging.getLogger(__name__)

_CONTENT_TYPES: dict[str, str] = {
    "json": "application/json",
    "geojson": "application/geo+json",
    "html": "text/html; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
    "markdown": "text/markdown; charset=utf-8",
}

_SUFFIX: dict[str, str] = {
    "geojson": ".geojson",
    "html": ".html",
    "csv": ".csv",
    "markdown": ".md",
}

_EXPORTERS: dict[str, Any] = {
    "geojson": export_geojson,
    "html": export_html,
    "csv": export_csv,
    "markdown": export_markdown,
}


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Store startup state for the /health endpoint."""
    application.state.start_time = datetime.now(tz=timezone.utc)
    application.state.last_run = None
    application.state.run_count = 0
    yield


app = FastAPI(
    title="Seismic Risk API",
    description="Real-time seismic risk scoring for global aviation infrastructure.",
    version=__version__,
    lifespan=lifespan,
)


def _run_and_export(
    results: list[CountryRiskResult],
    fmt: OutputFormat,
) -> Response:
    """Serialize pipeline results into the requested format."""
    if fmt == "json":
        return JSONResponse(content=[asdict(r) for r in results])

    exporter = _EXPORTERS[fmt]
    suffix = _SUFFIX[fmt]

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        exporter(results, tmp_path)
        content = tmp_path.read_text(encoding="utf-8")
    finally:
        tmp_path.unlink(missing_ok=True)

    return Response(content=content, media_type=_CONTENT_TYPES[fmt])


@app.get("/health")
def health() -> dict[str, Any]:
    """Server health check with uptime, version, and run count."""
    now = datetime.now(tz=timezone.utc)
    return {
        "status": "ok",
        "version": __version__,
        "uptime_seconds": round((now - app.state.start_time).total_seconds(), 1),
        "last_run": app.state.last_run.isoformat() if app.state.last_run else None,
        "run_count": app.state.run_count,
    }


@app.get("/risk")
def get_risk(
    format: Annotated[
        OutputFormat, Query(description="Output format."),
    ] = "json",
    min_magnitude: Annotated[
        float, Query(ge=0.0, le=10.0, description="Minimum earthquake magnitude."),
    ] = 5.0,
    days: Annotated[
        int, Query(ge=1, le=365, description="Number of days to look back."),
    ] = 30,
    distance: Annotated[
        float, Query(gt=0.0, description="Max airport exposure distance in km."),
    ] = 200.0,
    min_quakes: Annotated[
        int, Query(ge=1, description="Minimum quakes per country to qualify."),
    ] = 3,
    airport_type: Annotated[
        str, Query(description="Airport type filter."),
    ] = "large_airport",
    scorer: Annotated[
        ScoringMethod, Query(description="Scoring method."),
    ] = "shakemap",
    no_cache: Annotated[
        bool, Query(description="Disable disk caching."),
    ] = False,
) -> Response:
    """Run the seismic risk pipeline and return results.

    Query parameters mirror the CLI options.  The ``format`` param controls
    the response content type (json, geojson, html, csv, markdown).
    """
    config = SeismicRiskConfig(
        min_magnitude=min_magnitude,
        days_lookback=days,
        min_quakes_per_country=min_quakes,
        max_airport_distance_km=distance,
        airport_type=airport_type,
        scoring_method=scorer,
        cache_enabled=not no_cache,
    )

    try:
        results = run_pipeline(config)
    except Exception as exc:
        logger.exception("Pipeline failed")
        return JSONResponse(
            status_code=502,
            content={"detail": f"Upstream pipeline error: {exc}"},
        )

    app.state.last_run = datetime.now(tz=timezone.utc)
    app.state.run_count += 1

    return _run_and_export(results, format)
