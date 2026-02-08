"""Tests for ShakeMap grid fetcher and PGA interpolator."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import responses
from requests.exceptions import ConnectionError as RequestsConnectionError

from seismic_risk.fetchers.shakemap import (
    ShakeMapGrid,
    _extract_grid_url,
    _parse_grid_xml,
    fetch_shakemap_grids,
    interpolate_pga,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_grid_xml() -> bytes:
    return (FIXTURES_DIR / "shakemap_grid_sample.xml").read_bytes()


@pytest.fixture
def sample_grid() -> ShakeMapGrid:
    """Pre-built 5x5 grid matching the sample XML fixture."""
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
        event_id="us2025test",
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


class TestParseGridXml:
    def test_valid_xml(self, sample_grid_xml: bytes) -> None:
        grid = _parse_grid_xml(sample_grid_xml, "us2025test")
        assert grid is not None
        assert grid.event_id == "us2025test"
        assert grid.nlon == 5
        assert grid.nlat == 5
        assert grid.lon_min == 139.0
        assert grid.lat_max == 36.0
        assert grid.lon_spacing == 0.25
        assert grid.pga.shape == (5, 5)
        assert grid.mmi.shape == (5, 5)
        # Center value: PGA=15.0 %g, MMI=7.0
        assert grid.pga[2, 2] == 15.0
        assert grid.mmi[2, 2] == 7.0
        # Corner value: PGA=2.0 %g, MMI=3.0
        assert grid.pga[0, 0] == 2.0
        assert grid.mmi[0, 0] == 3.0

    def test_invalid_xml_returns_none(self) -> None:
        result = _parse_grid_xml(b"not xml at all", "bad")
        assert result is None

    def test_missing_grid_spec_returns_none(self) -> None:
        xml = b'<?xml version="1.0"?><shakemap_grid></shakemap_grid>'
        result = _parse_grid_xml(xml, "bad")
        assert result is None

    def test_wrong_point_count_returns_none(self) -> None:
        xml = (
            b'<?xml version="1.0"?>'
            b"<shakemap_grid>"
            b'<grid_specification lon_min="0" lon_max="1" lat_min="0" lat_max="1"'
            b' nominal_lon_spacing="1" nominal_lat_spacing="1" nlon="2" nlat="2" />'
            b"<grid_data>\n"
            b"0.0 1.0 3.0 5.0 2.0 4.0 3.0 2.0 400\n"
            b"</grid_data>"
            b"</shakemap_grid>"
        )
        result = _parse_grid_xml(xml, "bad")
        assert result is None


class TestInterpolatePga:
    def test_exact_grid_point_center(self, sample_grid: ShakeMapGrid) -> None:
        result = interpolate_pga(sample_grid, lat=35.5, lon=139.5)
        assert result is not None
        pga, mmi = result
        assert pga == pytest.approx(15.0)
        assert mmi == pytest.approx(7.0)

    def test_exact_grid_point_corner(self, sample_grid: ShakeMapGrid) -> None:
        result = interpolate_pga(sample_grid, lat=36.0, lon=139.0)
        assert result is not None
        pga, mmi = result
        assert pga == pytest.approx(2.0)
        assert mmi == pytest.approx(3.0)

    def test_midpoint_between_cells(self, sample_grid: ShakeMapGrid) -> None:
        # Midpoint between (row=0, col=0) PGA=2.0 and (row=0, col=1) PGA=3.0
        # at lat=36.0, lon=139.125 → halfway between col 0 and col 1
        result = interpolate_pga(sample_grid, lat=36.0, lon=139.125)
        assert result is not None
        pga, mmi = result
        assert pga == pytest.approx(2.5)
        assert mmi == pytest.approx(3.25)

    def test_outside_bounds_lon(self, sample_grid: ShakeMapGrid) -> None:
        assert interpolate_pga(sample_grid, lat=35.5, lon=138.0) is None

    def test_outside_bounds_lat(self, sample_grid: ShakeMapGrid) -> None:
        assert interpolate_pga(sample_grid, lat=37.0, lon=139.5) is None

    def test_on_boundary(self, sample_grid: ShakeMapGrid) -> None:
        # Exact boundary should work (inclusive)
        result = interpolate_pga(sample_grid, lat=35.0, lon=140.0)
        assert result is not None
        pga, mmi = result
        assert pga == pytest.approx(2.0)
        assert mmi == pytest.approx(3.0)


class TestExtractGridUrl:
    def test_valid_detail(self) -> None:
        detail = {
            "properties": {
                "products": {
                    "shakemap": [
                        {
                            "contents": {
                                "download/grid.xml": {
                                    "url": "https://earthquake.usgs.gov/grid.xml"
                                }
                            }
                        }
                    ]
                }
            }
        }
        assert _extract_grid_url(detail) == "https://earthquake.usgs.gov/grid.xml"

    def test_no_shakemap_product(self) -> None:
        detail = {"properties": {"products": {}}}
        assert _extract_grid_url(detail) is None

    def test_no_grid_xml_in_contents(self) -> None:
        detail = {
            "properties": {
                "products": {
                    "shakemap": [{"contents": {"download/info.json": {}}}]
                }
            }
        }
        assert _extract_grid_url(detail) is None


class TestFetchShakemapGrids:
    @responses.activate
    def test_no_shakemap_events_returns_empty(self) -> None:
        result = fetch_shakemap_grids(
            earthquake_ids={"eq1"},
            event_types={"eq1": ",dyfi,origin,"},
            use_cache=False,
        )
        assert result == {}

    @responses.activate
    def test_event_detail_failure_skips(self) -> None:
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            status=500,
        )
        result = fetch_shakemap_grids(
            earthquake_ids={"eq1"},
            event_types={"eq1": ",shakemap,dyfi,"},
            use_cache=False,
        )
        assert result == {}

    @responses.activate
    def test_network_error_skips(self) -> None:
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            body=RequestsConnectionError("Connection refused"),
        )
        result = fetch_shakemap_grids(
            earthquake_ids={"eq1"},
            event_types={"eq1": ",shakemap,dyfi,"},
            use_cache=False,
        )
        assert result == {}

    @responses.activate
    def test_successful_fetch(self, sample_grid_xml: bytes) -> None:
        # Mock event detail
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            json={
                "properties": {
                    "products": {
                        "shakemap": [
                            {
                                "contents": {
                                    "download/grid.xml": {
                                        "url": "https://earthquake.usgs.gov/grid.xml"
                                    }
                                }
                            }
                        ]
                    }
                }
            },
            status=200,
        )
        # Mock grid download
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/grid.xml",
            body=sample_grid_xml,
            status=200,
        )
        result = fetch_shakemap_grids(
            earthquake_ids={"eq1"},
            event_types={"eq1": ",shakemap,dyfi,"},
            use_cache=False,
        )
        assert "eq1" in result
        assert result["eq1"].pga[2, 2] == 15.0

    @responses.activate
    def test_grid_download_failure_skips(self) -> None:
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            json={
                "properties": {
                    "products": {
                        "shakemap": [
                            {
                                "contents": {
                                    "download/grid.xml": {
                                        "url": "https://earthquake.usgs.gov/grid.xml"
                                    }
                                }
                            }
                        ]
                    }
                }
            },
            status=200,
        )
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/grid.xml",
            status=404,
        )
        result = fetch_shakemap_grids(
            earthquake_ids={"eq1"},
            event_types={"eq1": ",shakemap,dyfi,"},
            use_cache=False,
        )
        assert result == {}
