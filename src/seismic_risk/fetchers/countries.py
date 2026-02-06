"""REST Countries API fetcher."""

from __future__ import annotations

import json
import logging

from requests import Session

from seismic_risk.cache import COUNTRIES_TTL, cache_get, cache_put
from seismic_risk.http import create_session

logger = logging.getLogger(__name__)

REST_COUNTRIES_BASE = "https://restcountries.com/v3.1/alpha"


def fetch_country_metadata(
    country_codes: set[str],
    timeout: int = 10,
    base_url: str = REST_COUNTRIES_BASE,
    session: Session | None = None,
    use_cache: bool = True,
) -> dict[str, dict]:
    """Fetch metadata for each country code from the REST Countries API.

    Countries that fail to fetch are silently omitted.
    Uses a shared session for connection pooling across sequential requests.
    Caches individual country responses on disk (7-day TTL).
    """
    if session is None:
        session = create_session()

    result: dict[str, dict] = {}
    for cc in sorted(country_codes):
        cache_key = f"country_{cc}.json"

        # Check cache first
        if use_cache:
            cached = cache_get(cache_key, COUNTRIES_TTL)
            if cached is not None:
                logger.debug("Cache hit for country %s", cc)
                result[cc] = json.loads(cached)
                continue

        try:
            resp = session.get(f"{base_url}/{cc}", timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                country_data = data[0] if isinstance(data, list) else data
                result[cc] = country_data

                if use_cache:
                    cache_put(cache_key, json.dumps(country_data).encode())
        except Exception:
            logger.warning("Failed to fetch country metadata for %s", cc, exc_info=True)

    return result
