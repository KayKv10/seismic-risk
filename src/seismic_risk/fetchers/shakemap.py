"""USGS ShakeMap grid fetcher and PGA interpolator."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import numpy as np
from requests import Session

from seismic_risk.cache import cache_get, cache_put
from seismic_risk.http import create_session

logger = logging.getLogger(__name__)

SHAKEMAP_GRID_TTL = 86400  # 24 hours

_NS = {"sm": "http://earthquake.usgs.gov/eqcenter/shakemap"}


@dataclass
class ShakeMapGrid:
    """Parsed ShakeMap grid for bilinear interpolation."""

    event_id: str
    lon_min: float
    lat_min: float
    lon_max: float
    lat_max: float
    lon_spacing: float
    lat_spacing: float
    nlon: int
    nlat: int
    pga: np.ndarray  # shape (nlat, nlon), values in %g
    mmi: np.ndarray  # shape (nlat, nlon)


def interpolate_pga(
    grid: ShakeMapGrid, lat: float, lon: float,
) -> tuple[float, float] | None:
    """Bilinear interpolation of PGA and MMI at (lat, lon).

    Returns (pga_%g, mmi) or None if the point is outside the grid bounds.
    """
    if lon < grid.lon_min or lon > grid.lon_max:
        return None
    if lat < grid.lat_min or lat > grid.lat_max:
        return None

    # Column index (fractional) — left to right
    col = (lon - grid.lon_min) / grid.lon_spacing
    # Row index (fractional) — row 0 is lat_max, row nlat-1 is lat_min
    row = (grid.lat_max - lat) / grid.lat_spacing

    # Clamp to valid range
    col = max(0.0, min(col, grid.nlon - 1))
    row = max(0.0, min(row, grid.nlat - 1))

    # Integer indices for surrounding corners
    c0 = int(col)
    r0 = int(row)
    c1 = min(c0 + 1, grid.nlon - 1)
    r1 = min(r0 + 1, grid.nlat - 1)

    # Fractional offsets
    dc = col - c0
    dr = row - r0

    # Bilinear interpolation for PGA
    pga = (
        grid.pga[r0, c0] * (1 - dc) * (1 - dr)
        + grid.pga[r0, c1] * dc * (1 - dr)
        + grid.pga[r1, c0] * (1 - dc) * dr
        + grid.pga[r1, c1] * dc * dr
    )

    # Bilinear interpolation for MMI
    mmi = (
        grid.mmi[r0, c0] * (1 - dc) * (1 - dr)
        + grid.mmi[r0, c1] * dc * (1 - dr)
        + grid.mmi[r1, c0] * (1 - dc) * dr
        + grid.mmi[r1, c1] * dc * dr
    )

    return float(pga), float(mmi)


def _fetch_event_detail(
    event_id: str, session: Session, timeout: int,
) -> dict | None:
    """Fetch USGS event detail JSON, or None on failure."""
    url = (
        f"https://earthquake.usgs.gov/fdsnws/event/1/query"
        f"?eventid={event_id}&format=geojson"
    )
    try:
        resp = session.get(url, timeout=timeout)
        if resp.status_code != 200:
            logger.warning("Event detail %s returned %d", event_id, resp.status_code)
            return None
        return resp.json()  # type: ignore[no-any-return]
    except Exception:
        logger.warning("Failed to fetch event detail %s", event_id, exc_info=True)
        return None


def _extract_grid_url(detail: dict) -> str | None:
    """Extract grid.xml download URL from event detail JSON."""
    try:
        products = detail["properties"]["products"]
        shakemap = products["shakemap"][0]
        contents = shakemap["contents"]
        return contents["download/grid.xml"]["url"]  # type: ignore[no-any-return]
    except (KeyError, IndexError, TypeError):
        return None


def _parse_grid_xml(xml_bytes: bytes, event_id: str) -> ShakeMapGrid | None:
    """Parse ShakeMap grid.xml into a ShakeMapGrid.

    Grid columns: LON, LAT, MMI, PGA(%g), PGV, PSA03, PSA10, PSA30, SVEL.
    Rows are ordered from (lon_min, lat_max) to (lon_max, lat_min).
    """
    try:
        root = ET.fromstring(xml_bytes)

        # Find grid_specification (with or without namespace)
        spec = root.find("sm:grid_specification", _NS)
        if spec is None:
            spec = root.find("grid_specification")
        if spec is None:
            logger.warning("No grid_specification in %s", event_id)
            return None

        lon_min = float(spec.attrib["lon_min"])
        lon_max = float(spec.attrib["lon_max"])
        lat_min = float(spec.attrib["lat_min"])
        lat_max = float(spec.attrib["lat_max"])
        lon_spacing = float(spec.attrib["nominal_lon_spacing"])
        lat_spacing = float(spec.attrib["nominal_lat_spacing"])
        nlon = int(spec.attrib["nlon"])
        nlat = int(spec.attrib["nlat"])

        # Find grid_data text
        grid_data_el = root.find("sm:grid_data", _NS)
        if grid_data_el is None:
            grid_data_el = root.find("grid_data")
        if grid_data_el is None or grid_data_el.text is None:
            logger.warning("No grid_data in %s", event_id)
            return None

        lines = grid_data_el.text.strip().split("\n")
        pga_flat: list[float] = []
        mmi_flat: list[float] = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) < 4:
                continue
            mmi_flat.append(float(parts[2]))  # MMI at index 2
            pga_flat.append(float(parts[3]))  # PGA at index 3

        expected = nlon * nlat
        if len(pga_flat) != expected:
            logger.warning(
                "Grid %s: expected %d points, got %d",
                event_id, expected, len(pga_flat),
            )
            return None

        pga = np.array(pga_flat, dtype=np.float64).reshape(nlat, nlon)
        mmi = np.array(mmi_flat, dtype=np.float64).reshape(nlat, nlon)

        return ShakeMapGrid(
            event_id=event_id,
            lon_min=lon_min,
            lat_min=lat_min,
            lon_max=lon_max,
            lat_max=lat_max,
            lon_spacing=lon_spacing,
            lat_spacing=lat_spacing,
            nlon=nlon,
            nlat=nlat,
            pga=pga,
            mmi=mmi,
        )
    except (ET.ParseError, ValueError, KeyError) as exc:
        logger.warning("Failed to parse grid.xml for %s: %s", event_id, exc)
        return None


def fetch_shakemap_grids(
    earthquake_ids: set[str],
    event_types: dict[str, str],
    session: Session | None = None,
    timeout: int = 60,
    use_cache: bool = True,
) -> dict[str, ShakeMapGrid]:
    """Fetch ShakeMap grids for earthquakes that have ShakeMap data.

    Only fetches for events whose types string contains ``shakemap``.
    Returns ``{event_id: ShakeMapGrid}`` for successfully fetched grids.
    """
    if session is None:
        session = create_session()

    # Filter to events with ShakeMap availability
    target_ids = {
        eid for eid in earthquake_ids
        if "shakemap" in event_types.get(eid, "").split(",")
    }

    if not target_ids:
        return {}

    logger.info("Fetching ShakeMap grids for %d events", len(target_ids))
    grids: dict[str, ShakeMapGrid] = {}

    for eid in sorted(target_ids):  # sorted for deterministic order
        cache_key = f"shakemap_{eid}.xml"

        # Try cache first
        xml_bytes: bytes | None = None
        if use_cache:
            xml_bytes = cache_get(cache_key, SHAKEMAP_GRID_TTL)

        if xml_bytes is None:
            # Fetch event detail → grid URL → grid data
            detail = _fetch_event_detail(eid, session, timeout)
            if detail is None:
                continue

            grid_url = _extract_grid_url(detail)
            if grid_url is None:
                logger.info("No grid.xml URL for %s", eid)
                continue

            try:
                resp = session.get(grid_url, timeout=timeout)
                if resp.status_code != 200:
                    logger.warning("Grid download %s returned %d", eid, resp.status_code)
                    continue
                xml_bytes = resp.content
            except Exception:
                logger.warning("Failed to download grid for %s", eid, exc_info=True)
                continue

            if use_cache:
                cache_put(cache_key, xml_bytes)

        grid = _parse_grid_xml(xml_bytes, eid)
        if grid is not None:
            grids[eid] = grid

    logger.info("Successfully loaded %d ShakeMap grids", len(grids))
    return grids
