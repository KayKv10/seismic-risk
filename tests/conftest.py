"""Shared fixtures for seismic_risk tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from seismic_risk.config import SeismicRiskConfig
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
