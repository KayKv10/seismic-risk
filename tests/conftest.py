"""Shared fixtures for seismic_risk tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from seismic_risk.config import SeismicRiskConfig
from seismic_risk.fetchers.shakemap import ShakeMapGrid
from seismic_risk.history import CountryTrend, TrendSummary
from seismic_risk.models import (
    Airport,
    CountryRiskResult,
    Earthquake,
    ExposedAirport,
    NearbyQuake,
    StrongestEarthquake,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def sample_usgs_response() -> dict:
    return json.loads((FIXTURES_DIR / "usgs_sample.json").read_text())


@pytest.fixture
def sample_significant_response() -> dict:
    return json.loads((FIXTURES_DIR / "significant_sample.json").read_text())


@pytest.fixture
def sample_airports_csv_path() -> Path:
    return FIXTURES_DIR / "airports_sample.csv"


@pytest.fixture
def sample_countries() -> dict:
    return json.loads((FIXTURES_DIR / "countries_sample.json").read_text())


@pytest.fixture
def sample_earthquakes() -> list[Earthquake]:
    """Pre-built Earthquake objects for unit tests."""
    return [
        Earthquake(
            id="us2025abc1",
            magnitude=5.2,
            latitude=38.3,
            longitude=141.5,
            depth_km=30.0,
            time_ms=1700000000000,
            place="Near coast of Japan",
            country_code="JP",
        ),
        Earthquake(
            id="us2025abc2",
            magnitude=4.8,
            latitude=36.1,
            longitude=139.8,
            depth_km=45.0,
            time_ms=1700100000000,
            place="Central Japan",
            country_code="JP",
        ),
        Earthquake(
            id="us2025abc3",
            magnitude=6.1,
            latitude=35.7,
            longitude=140.2,
            depth_km=20.0,
            time_ms=1700200000000,
            place="Near Tokyo",
            country_code="JP",
        ),
    ]


@pytest.fixture
def sample_airports() -> list[Airport]:
    """Pre-built Airport objects for unit tests."""
    return [
        Airport(
            name="Narita International Airport",
            iata_code="NRT",
            latitude=35.7647,
            longitude=140.3864,
            municipality="Narita",
            iso_country="JP",
            airport_type="large_airport",
        ),
        Airport(
            name="Tokyo Haneda International Airport",
            iata_code="HND",
            latitude=35.5533,
            longitude=139.7811,
            municipality="Tokyo",
            iso_country="JP",
            airport_type="large_airport",
        ),
    ]


@pytest.fixture
def default_config(tmp_path: Path) -> SeismicRiskConfig:
    """Config with defaults, writing to tmp_path."""
    return SeismicRiskConfig(output_file=tmp_path / "output.json")


@pytest.fixture
def sample_results() -> list[CountryRiskResult]:
    """Pre-built CountryRiskResult for exporter tests."""
    return [
        CountryRiskResult(
            country="Japan",
            iso_alpha2="JP",
            iso_alpha3="JPN",
            capital="Tokyo",
            population=125800000,
            area_km2=377975.0,
            region="Asia",
            subregion="Eastern Asia",
            currencies=[{"code": "JPY", "name": "Japanese yen"}],
            languages=["Japanese"],
            un_member=True,
            bordering_countries=[],
            earthquake_count=3,
            avg_magnitude=5.37,
            strongest_earthquake=StrongestEarthquake(
                magnitude=6.1,
                date="2026-01-28",
                depth_km=20.0,
                latitude=35.7,
                longitude=140.2,
            ),
            highest_pager_alert="orange",
            max_felt_reports=1500,
            tsunami_warning_issued=False,
            significant_events_count=1,
            exposed_airports=[
                ExposedAirport(
                    name="Narita International Airport",
                    iata_code="NRT",
                    latitude=35.7647,
                    longitude=140.3864,
                    municipality="Narita",
                    closest_quake_distance_km=45,
                    nearby_quakes=[
                        NearbyQuake(
                            earthquake_id="us2025abc3",
                            magnitude=6.1,
                            latitude=35.7,
                            longitude=140.2,
                            depth_km=20.0,
                            time_ms=1700200000000,
                            place="Near Tokyo",
                            distance_km=18.2,
                            exposure_contribution=58.42,
                        ),
                        NearbyQuake(
                            earthquake_id="us2025abc2",
                            magnitude=4.8,
                            latitude=36.1,
                            longitude=139.8,
                            depth_km=45.0,
                            time_ms=1700100000000,
                            place="Central Japan",
                            distance_km=65.3,
                            exposure_contribution=3.78,
                        ),
                    ],
                    exposure_score=62.2,
                ),
                ExposedAirport(
                    name="Tokyo Haneda International Airport",
                    iata_code="HND",
                    latitude=35.5533,
                    longitude=139.7811,
                    municipality="Tokyo",
                    closest_quake_distance_km=52,
                    nearby_quakes=[
                        NearbyQuake(
                            earthquake_id="us2025abc2",
                            magnitude=4.8,
                            latitude=36.1,
                            longitude=139.8,
                            depth_km=45.0,
                            time_ms=1700100000000,
                            place="Central Japan",
                            distance_km=61.0,
                            exposure_contribution=4.05,
                        ),
                        NearbyQuake(
                            earthquake_id="us2025abc3",
                            magnitude=6.1,
                            latitude=35.7,
                            longitude=140.2,
                            depth_km=20.0,
                            time_ms=1700200000000,
                            place="Near Tokyo",
                            distance_km=42.0,
                            exposure_contribution=26.07,
                        ),
                    ],
                    exposure_score=30.12,
                ),
            ],
            earthquakes=[
                Earthquake(
                    id="us2025abc1",
                    magnitude=5.2,
                    latitude=38.3,
                    longitude=141.5,
                    depth_km=30.0,
                    time_ms=1700000000000,
                    place="Near coast of Japan",
                    country_code="JP",
                ),
                Earthquake(
                    id="us2025abc2",
                    magnitude=4.8,
                    latitude=36.1,
                    longitude=139.8,
                    depth_km=45.0,
                    time_ms=1700100000000,
                    place="Central Japan",
                    country_code="JP",
                ),
                Earthquake(
                    id="us2025abc3",
                    magnitude=6.1,
                    latitude=35.7,
                    longitude=140.2,
                    depth_km=20.0,
                    time_ms=1700200000000,
                    place="Near Tokyo",
                    country_code="JP",
                ),
            ],
            seismic_hub_risk_score=42.85,
        ),
    ]


@pytest.fixture
def sample_trends() -> TrendSummary:
    """Pre-built TrendSummary for trend-aware exporter tests."""
    return TrendSummary(
        date="2026-02-06",
        history_days=7,
        country_trends={
            "JPN": CountryTrend(
                iso_alpha3="JPN",
                country="Japan",
                scores=[38.2, 40.1, 42.85],
                dates=["2026-02-04", "2026-02-05", "2026-02-06"],
                current_score=42.85,
                previous_score=40.1,
                score_delta=2.75,
                trend_direction="up",
                is_new=False,
                is_gone=False,
                days_tracked=3,
            ),
        },
        new_countries=[],
        gone_countries=[],
    )


@pytest.fixture
def sample_shakemap_grid() -> ShakeMapGrid:
    """5x5 ShakeMap grid covering 139–140E, 35–36N (Tokyo area)."""
    pga = np.array(
        [
            [2.0, 3.0, 4.0, 3.0, 2.0],
            [3.0, 5.0, 8.0, 5.0, 3.0],
            [4.0, 8.0, 15.0, 8.0, 4.0],
            [3.0, 5.0, 8.0, 5.0, 3.0],
            [2.0, 3.0, 4.0, 3.0, 2.0],
        ],
        dtype=np.float64,
    )
    mmi = np.array(
        [
            [3.0, 3.5, 4.0, 3.5, 3.0],
            [3.5, 4.5, 5.5, 4.5, 3.5],
            [4.0, 5.5, 7.0, 5.5, 4.0],
            [3.5, 4.5, 5.5, 4.5, 3.5],
            [3.0, 3.5, 4.0, 3.5, 3.0],
        ],
        dtype=np.float64,
    )
    return ShakeMapGrid(
        event_id="us2025abc3",
        lon_min=139.0,
        lat_min=35.0,
        lon_max=140.0,
        lat_max=36.0,
        lon_spacing=0.25,
        lat_spacing=0.25,
        nlon=5,
        nlat=5,
        pga=pga,
        mmi=mmi,
    )
