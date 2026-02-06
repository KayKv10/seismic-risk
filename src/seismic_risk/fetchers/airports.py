"""OurAirports data fetcher."""

from __future__ import annotations

import io
import logging

import pandas as pd
from requests import Session

from seismic_risk.cache import AIRPORTS_TTL, cache_get, cache_put
from seismic_risk.http import create_session
from seismic_risk.models import Airport

logger = logging.getLogger(__name__)

OURAIRPORTS_CSV_URL = (
    "https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/airports.csv"
)

_CACHE_KEY = "airports.csv"


def _download_csv(
    url: str, session: Session, timeout: int, use_cache: bool,
) -> pd.DataFrame:
    """Download CSV via session (retry-enabled) or read local path.

    For HTTP URLs, checks the disk cache first (24h TTL).
    """
    if url.startswith(("http://", "https://")):
        if use_cache:
            cached = cache_get(_CACHE_KEY, AIRPORTS_TTL)
            if cached is not None:
                logger.info("Using cached airports data")
                return pd.read_csv(io.BytesIO(cached))

        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()

        if use_cache:
            cache_put(_CACHE_KEY, resp.content)

        return pd.read_csv(io.BytesIO(resp.content))

    # Local file path (used in tests)
    return pd.read_csv(url)


def fetch_airports(
    airport_type: str = "large_airport",
    country_codes: set[str] | None = None,
    url: str | None = None,
    timeout: int = 60,
    session: Session | None = None,
    use_cache: bool = True,
) -> list[Airport]:
    """Download OurAirports CSV and return airports matching the given criteria."""
    if url is None:
        url = OURAIRPORTS_CSV_URL
    if session is None:
        session = create_session()

    df = _download_csv(url, session, timeout, use_cache)
    filtered = df[df["type"] == airport_type].copy()

    if country_codes is not None:
        filtered = filtered[filtered["iso_country"].isin(country_codes)]

    airports: list[Airport] = []
    for _, row in filtered.iterrows():
        iata = (
            str(row["iata_code"])
            if pd.notna(row["iata_code"]) and row["iata_code"] != ""
            else "N/A"
        )
        municipality = str(row["municipality"]) if pd.notna(row["municipality"]) else ""
        airports.append(
            Airport(
                name=str(row["name"]),
                iata_code=iata,
                latitude=float(row["latitude_deg"]),
                longitude=float(row["longitude_deg"]),
                municipality=municipality,
                iso_country=str(row["iso_country"]),
                airport_type=airport_type,
            )
        )
    return airports
