"""USGS earthquake data fetchers."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from requests import Session

from seismic_risk.http import create_session
from seismic_risk.models import Earthquake, SignificantEvent

logger = logging.getLogger(__name__)


def fetch_earthquakes(
    min_magnitude: float = 4.0,
    days_lookback: int = 30,
    timeout: int = 60,
    session: Session | None = None,
) -> tuple[list[Earthquake], dict[str, str]]:
    """Fetch recent earthquakes from the USGS FDSN Event Web Service.

    Returns:
        (earthquakes, event_types): List of earthquakes and a mapping of
        event_id -> properties.types string (for ShakeMap availability checks).
    """
    if session is None:
        session = create_session()

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days_lookback)

    params: dict[str, str | float] = {
        "format": "geojson",
        "minmagnitude": min_magnitude,
        "starttime": start_date.strftime("%Y-%m-%d"),
        "endtime": end_date.strftime("%Y-%m-%d"),
        "orderby": "time",
    }
    resp = session.get(
        "https://earthquake.usgs.gov/fdsnws/event/1/query",
        params=params,
        timeout=timeout,
    )
    resp.raise_for_status()

    features = resp.json()["features"]
    earthquakes: list[Earthquake] = []
    event_types: dict[str, str] = {}
    for feat in features:
        if feat["properties"]["mag"] is None:
            continue
        types_str = feat["properties"].get("types", "")
        event_types[feat["id"]] = types_str
        earthquakes.append(
            Earthquake(
                id=feat["id"],
                magnitude=feat["properties"]["mag"],
                latitude=feat["geometry"]["coordinates"][1],
                longitude=feat["geometry"]["coordinates"][0],
                depth_km=feat["geometry"]["coordinates"][2],
                time_ms=feat["properties"]["time"],
                place=feat["properties"].get("place", ""),
                shakemap_available="shakemap" in types_str.split(","),
            )
        )
    return earthquakes, event_types


def fetch_significant_earthquakes(
    timeout: int = 30,
    session: Session | None = None,
) -> dict[str, SignificantEvent]:
    """Fetch USGS significant earthquakes feed (past 30 days).

    Returns empty dict on HTTP errors or network failures (non-fatal).
    """
    if session is None:
        session = create_session()

    try:
        resp = session.get(
            "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson",
            timeout=timeout,
        )
        if resp.status_code != 200:
            return {}
    except Exception:
        logger.warning("Failed to fetch significant earthquakes", exc_info=True)
        return {}

    result: dict[str, SignificantEvent] = {}
    for feat in resp.json().get("features", []):
        props = feat["properties"]
        result[feat["id"]] = SignificantEvent(
            id=feat["id"],
            alert=props.get("alert"),
            felt=props.get("felt") or 0,
            tsunami=bool(props.get("tsunami", 0)),
            significance=props.get("sig", 0),
            title=props.get("title", ""),
        )
    return result
