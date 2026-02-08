"""Pipeline orchestrator: fetch -> geocode -> filter -> score -> assemble."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import replace

from seismic_risk.config import SeismicRiskConfig
from seismic_risk.fetchers.airports import fetch_airports
from seismic_risk.fetchers.countries import fetch_country_metadata
from seismic_risk.fetchers.shakemap import ShakeMapGrid, fetch_shakemap_grids
from seismic_risk.fetchers.usgs import fetch_earthquakes, fetch_significant_earthquakes
from seismic_risk.geo import reverse_geocode_batch
from seismic_risk.http import create_session
from seismic_risk.models import CountryRiskResult
from seismic_risk.scoring import (
    calculate_risk_score,
    compute_pager_context,
    compute_seismic_stats,
    find_exposed_airports,
)

logger = logging.getLogger(__name__)


def _extract_country_metadata(cd: dict) -> dict:
    """Extract standardized country metadata from REST Countries response."""
    currencies = [
        {"code": code, "name": info.get("name", "")}
        for code, info in cd.get("currencies", {}).items()
    ]
    languages = sorted(cd.get("languages", {}).values())
    capitals = cd.get("capital", [])
    capital = capitals[0] if capitals else ""

    return {
        "country": cd.get("name", {}).get("common", ""),
        "iso_alpha3": cd.get("cca3", ""),
        "capital": capital,
        "population": cd.get("population", 0),
        "area_km2": cd.get("area", 0),
        "region": cd.get("region", ""),
        "subregion": cd.get("subregion", ""),
        "currencies": currencies,
        "languages": languages,
        "un_member": cd.get("unMember", False),
        "bordering_countries": cd.get("borders", []),
    }


def run_pipeline(config: SeismicRiskConfig) -> list[CountryRiskResult]:
    """Execute the full seismic risk assessment pipeline.

    Steps:
    1. Fetch earthquakes from USGS
    2. Reverse-geocode epicenters to country codes
    3. Count per country, filter by minimum threshold
    4. Fetch significant earthquakes feed
    5. Fetch airports for qualifying countries
    6. Fetch REST Countries metadata
    7. Compute exposure, stats, and score per country
    8. Sort by risk score descending
    """
    # Create shared HTTP session with retry for all fetchers
    session = create_session()

    # Step 1: Fetch earthquakes
    logger.info(
        "Fetching USGS M%.1f+ earthquakes (past %d days)...",
        config.min_magnitude,
        config.days_lookback,
    )
    earthquakes, event_types = fetch_earthquakes(
        min_magnitude=config.min_magnitude,
        days_lookback=config.days_lookback,
        timeout=config.request_timeout,
        session=session,
    )
    logger.info("Retrieved %d earthquakes", len(earthquakes))

    if not earthquakes:
        logger.warning("No earthquakes found.")
        return []

    # Step 2: Reverse-geocode epicenters
    logger.info("Reverse-geocoding %d epicenters...", len(earthquakes))
    coords = [(eq.latitude, eq.longitude) for eq in earthquakes]
    geo_results = reverse_geocode_batch(coords)
    earthquakes = [
        replace(eq, country_code=geo["cc"])
        for eq, geo in zip(earthquakes, geo_results, strict=True)
    ]

    # Step 3: Count per country, filter by minimum threshold
    counts = Counter(eq.country_code for eq in earthquakes)
    qualifying_countries = {
        cc for cc, n in counts.items() if n >= config.min_quakes_per_country
    }
    logger.info(
        "Countries with >=%d quakes: %s",
        config.min_quakes_per_country,
        sorted(qualifying_countries),
    )

    if not qualifying_countries:
        logger.warning("No qualifying countries.")
        return []

    # Step 4: Fetch significant earthquakes
    logger.info("Fetching USGS significant earthquakes...")
    significant_quakes = fetch_significant_earthquakes(
        timeout=config.request_timeout, session=session
    )
    logger.info("Significant earthquakes: %d", len(significant_quakes))

    # Step 4b: Fetch ShakeMap grids (only for "shakemap" scoring method)
    shakemap_grids: dict[str, ShakeMapGrid] = {}
    if config.scoring_method == "shakemap":
        eq_ids = {eq.id for eq in earthquakes}
        target_ids = set(significant_quakes.keys()) & eq_ids
        if target_ids:
            shakemap_grids = fetch_shakemap_grids(
                earthquake_ids=target_ids,
                event_types=event_types,
                session=session,
                timeout=config.request_timeout,
                use_cache=config.cache_enabled,
            )
            logger.info("ShakeMap grids loaded: %d", len(shakemap_grids))

    # Step 5: Fetch airports for qualifying countries
    logger.info("Fetching airports (type=%s)...", config.airport_type)
    all_airports = fetch_airports(
        airport_type=config.airport_type,
        country_codes=qualifying_countries,
        session=session,
        use_cache=config.cache_enabled,
    )

    airports_by_country: dict[str, list] = {}
    for ap in all_airports:
        airports_by_country.setdefault(ap.iso_country, []).append(ap)

    has_airports = set(airports_by_country.keys())
    logger.info("Qualifying countries with airports: %s", sorted(has_airports))

    # Step 6: Fetch REST Countries metadata
    logger.info("Fetching country metadata...")
    rest_data = fetch_country_metadata(
        has_airports, timeout=config.request_timeout, session=session,
        use_cache=config.cache_enabled,
    )

    # Step 7: Compute exposure and score for each country
    results: list[CountryRiskResult] = []
    for cc in sorted(has_airports):
        cd = rest_data.get(cc)
        if not cd:
            logger.warning("No metadata for %s, skipping", cc)
            continue

        cc_quakes = [eq for eq in earthquakes if eq.country_code == cc]
        cc_airports = airports_by_country[cc]

        exposed = find_exposed_airports(
            airports=cc_airports,
            earthquakes=cc_quakes,
            max_distance_km=config.max_airport_distance_km,
            shakemap_grids=shakemap_grids if config.scoring_method == "shakemap" else None,
        )
        if not exposed:
            continue

        avg_mag, strongest = compute_seismic_stats(cc_quakes)
        highest_alert, max_felt, has_tsunami, sig_count = compute_pager_context(
            cc_quakes, significant_quakes
        )
        risk_score = calculate_risk_score(
            airports=cc_airports,
            earthquakes=cc_quakes,
            max_distance_km=config.max_airport_distance_km,
            method=config.scoring_method,
            earthquake_count=len(cc_quakes),
            avg_magnitude=avg_mag,
            exposed_airport_count=len(exposed),
            exposed_airports=exposed,
        )

        meta = _extract_country_metadata(cd)

        results.append(
            CountryRiskResult(
                country=meta["country"],
                iso_alpha2=cc,
                iso_alpha3=meta["iso_alpha3"],
                capital=meta["capital"],
                population=meta["population"],
                area_km2=meta["area_km2"],
                region=meta["region"],
                subregion=meta["subregion"],
                currencies=meta["currencies"],
                languages=meta["languages"],
                un_member=meta["un_member"],
                bordering_countries=meta["bordering_countries"],
                earthquake_count=len(cc_quakes),
                avg_magnitude=avg_mag,
                strongest_earthquake=strongest,
                highest_pager_alert=highest_alert,
                max_felt_reports=max_felt,
                tsunami_warning_issued=has_tsunami,
                significant_events_count=sig_count,
                exposed_airports=exposed,
                earthquakes=cc_quakes,
                seismic_hub_risk_score=risk_score,
            )
        )

    # Step 8: Sort by risk score descending
    results.sort(key=lambda r: r.seismic_hub_risk_score, reverse=True)
    logger.info("Final qualifying countries: %d", len(results))

    return results
