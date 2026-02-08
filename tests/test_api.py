"""Tests for the FastAPI wrapper."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
import responses
from fastapi.testclient import TestClient

from seismic_risk.api import app


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """TestClient with lifespan entered so app.state is initialised."""
    with TestClient(app) as c:
        yield c


def _mock_pipeline_deps(
    usgs: dict,
    significant: dict,
    airports_path: str,
    countries: dict,
) -> None:
    """Register mocked HTTP responses for a full pipeline run."""
    responses.add(
        responses.GET,
        "https://earthquake.usgs.gov/fdsnws/event/1/query",
        json=usgs,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/"
        "significant_month.geojson",
        json=significant,
        status=200,
    )
    for cc, data in countries.items():
        responses.add(
            responses.GET,
            f"https://restcountries.com/v3.1/alpha/{cc}",
            json=[data],
            status=200,
        )


class TestHealthEndpoint:
    def test_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "uptime_seconds" in data
        assert "run_count" in data


class TestRiskEndpoint:
    @responses.activate
    def test_json_format_default(
        self,
        client: TestClient,
        sample_usgs_response: dict,
        sample_significant_response: dict,
        sample_airports_csv_path: Path,
        sample_countries: dict,
    ) -> None:
        """GET /risk returns JSON array by default."""
        _mock_pipeline_deps(
            sample_usgs_response,
            sample_significant_response,
            str(sample_airports_csv_path),
            sample_countries,
        )
        mock_geo = [{"cc": "JP"}] * 3 + [{"cc": "CL"}] * 2
        with (
            patch("seismic_risk.geo.rg.search", return_value=mock_geo),
            patch(
                "seismic_risk.fetchers.airports.OURAIRPORTS_CSV_URL",
                str(sample_airports_csv_path),
            ),
        ):
            resp = client.get(
                "/risk",
                params={"min_magnitude": 4.0, "days": 30, "min_quakes": 3, "distance": 400.0},
            )

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["country"] == "Japan"

    @responses.activate
    def test_html_format(
        self,
        client: TestClient,
        sample_usgs_response: dict,
        sample_significant_response: dict,
        sample_airports_csv_path: Path,
        sample_countries: dict,
    ) -> None:
        """GET /risk?format=html returns HTML content."""
        _mock_pipeline_deps(
            sample_usgs_response,
            sample_significant_response,
            str(sample_airports_csv_path),
            sample_countries,
        )
        mock_geo = [{"cc": "JP"}] * 3 + [{"cc": "CL"}] * 2
        with (
            patch("seismic_risk.geo.rg.search", return_value=mock_geo),
            patch(
                "seismic_risk.fetchers.airports.OURAIRPORTS_CSV_URL",
                str(sample_airports_csv_path),
            ),
        ):
            resp = client.get(
                "/risk",
                params={
                    "format": "html",
                    "min_magnitude": 4.0,
                    "days": 30,
                    "min_quakes": 3,
                    "distance": 400.0,
                },
            )

        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "<!DOCTYPE html>" in resp.text

    @responses.activate
    def test_csv_format(
        self,
        client: TestClient,
        sample_usgs_response: dict,
        sample_significant_response: dict,
        sample_airports_csv_path: Path,
        sample_countries: dict,
    ) -> None:
        """GET /risk?format=csv returns CSV content."""
        _mock_pipeline_deps(
            sample_usgs_response,
            sample_significant_response,
            str(sample_airports_csv_path),
            sample_countries,
        )
        mock_geo = [{"cc": "JP"}] * 3 + [{"cc": "CL"}] * 2
        with (
            patch("seismic_risk.geo.rg.search", return_value=mock_geo),
            patch(
                "seismic_risk.fetchers.airports.OURAIRPORTS_CSV_URL",
                str(sample_airports_csv_path),
            ),
        ):
            resp = client.get(
                "/risk",
                params={
                    "format": "csv",
                    "min_magnitude": 4.0,
                    "days": 30,
                    "min_quakes": 3,
                    "distance": 400.0,
                },
            )

        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "country" in resp.text

    @responses.activate
    def test_empty_results_returns_200(self, client: TestClient) -> None:
        """Pipeline with no earthquakes returns empty JSON array."""
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            json={"type": "FeatureCollection", "features": []},
            status=200,
        )
        resp = client.get("/risk")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_invalid_format_returns_422(self, client: TestClient) -> None:
        """Invalid format param triggers FastAPI validation."""
        resp = client.get("/risk", params={"format": "invalid"})
        assert resp.status_code == 422

    def test_invalid_magnitude_returns_422(self, client: TestClient) -> None:
        """Out-of-range magnitude triggers validation."""
        resp = client.get("/risk", params={"min_magnitude": 15.0})
        assert resp.status_code == 422

    @responses.activate
    def test_pipeline_error_returns_502(self, client: TestClient) -> None:
        """Network error during pipeline returns 502."""
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            body=ConnectionError("Simulated network failure"),
        )
        resp = client.get("/risk")
        assert resp.status_code == 502
        assert "detail" in resp.json()
