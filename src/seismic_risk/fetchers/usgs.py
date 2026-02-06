"""USGS earthquake data fetchers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests

from seismic_risk.models import Earthquake, SignificantEvent


def fetch_earthquakes(
    min_magnitude: float = 4.0,
    days_lookback: int = 30,
    timeout: int = 60,
) -> list[Earthquake]:
    """Fetch recent earthquakes from the USGS FDSN Event Web Service."""
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days_lookback)

    params: dict[str, str | float] = {
        "format": "geojson",
        "minmagnitude": min_magnitude,
        "starttime": start_date.strftime("%Y-%m-%d"),
        "endtime": end_date.strftime("%Y-%m-%d"),
        "orderby": "time",
    }
    resp = requests.get(
        "https://earthquake.usgs.gov/fdsnws/event/1/query",
        params=params,
        timeout=timeout,
    )
    resp.raise_for_status()

    features = resp.json()["features"]
    return [
        Earthquake(
            id=feat["id"],
            magnitude=feat["properties"]["mag"],
            latitude=feat["geometry"]["coordinates"][1],
            longitude=feat["geometry"]["coordinates"][0],
            depth_km=feat["geometry"]["coordinates"][2],
            time_ms=feat["properties"]["time"],
            place=feat["properties"].get("place", ""),
        )
        for feat in features
        if feat["properties"]["mag"] is not None
    ]


def fetch_significant_earthquakes(
    timeout: int = 30,
) -> dict[str, SignificantEvent]:
    """Fetch USGS significant earthquakes feed (past 30 days).

    Returns empty dict on HTTP errors (non-fatal).
    """
    resp = requests.get(
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson",
        timeout=timeout,
    )
    if resp.status_code != 200:
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
