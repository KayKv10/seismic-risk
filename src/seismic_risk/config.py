"""Configuration model for the seismic risk pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings

ScoringMethod = Literal["exposure", "legacy"]
OutputFormat = Literal["json", "geojson", "html", "csv", "markdown"]


class SeismicRiskConfig(BaseSettings):
    """All configurable parameters for the seismic risk pipeline.

    Values can be set via constructor arguments, environment variables
    prefixed with SEISMIC_RISK_, or defaults.
    """

    model_config = {"env_prefix": "SEISMIC_RISK_"}

    min_magnitude: float = Field(
        default=5.0, ge=0.0, le=10.0, description="Minimum earthquake magnitude."
    )
    days_lookback: int = Field(
        default=30, ge=1, le=365, description="Number of days to look back."
    )
    request_timeout: int = Field(
        default=60, ge=5, le=300, description="HTTP request timeout in seconds."
    )
    min_quakes_per_country: int = Field(
        default=3, ge=1, description="Minimum earthquake count for a country to qualify."
    )
    max_airport_distance_km: float = Field(
        default=200.0, gt=0.0, description="Max distance (km) for airport exposure."
    )
    airport_type: str = Field(
        default="large_airport", description="OurAirports type filter."
    )
    output_file: Path = Field(
        default=Path("seismic_risk_output.json"), description="Output file path."
    )
    output_format: OutputFormat = Field(
        default="json", description="Output format: json, geojson, html, csv, or markdown."
    )
    scoring_method: ScoringMethod = Field(
        default="exposure",
        description="Scoring method: 'exposure' (distance-weighted) or 'legacy'.",
    )
    cache_enabled: bool = Field(
        default=True, description="Enable disk caching for airports and country data."
    )
    history_dir: Path | None = Field(
        default=None,
        description="Directory for daily snapshot history. Enables trend tracking when set.",
    )
