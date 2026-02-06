"""REST Countries API fetcher."""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

REST_COUNTRIES_BASE = "https://restcountries.com/v3.1/alpha"


def fetch_country_metadata(
    country_codes: set[str],
    timeout: int = 10,
    base_url: str = REST_COUNTRIES_BASE,
) -> dict[str, dict]:
    """Fetch metadata for each country code from the REST Countries API.

    Countries that fail to fetch are silently omitted.
    """
    result: dict[str, dict] = {}
    for cc in sorted(country_codes):
        try:
            resp = requests.get(f"{base_url}/{cc}", timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                result[cc] = data[0] if isinstance(data, list) else data
        except Exception:
            logger.warning("Failed to fetch country metadata for %s", cc, exc_info=True)
    return result
