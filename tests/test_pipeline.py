"""Integration tests for the pipeline."""

from __future__ import annotations

from unittest.mock import patch

import responses

from seismic_risk.config import SeismicRiskConfig
from seismic_risk.pipeline import run_pipeline


class TestRunPipeline:
    @responses.activate
    def test_full_pipeline_with_fixtures(
        self,
        sample_usgs_response,
        sample_significant_response,
        sample_airports_csv_path,
        sample_countries,
        tmp_path,
    ):
        """Full pipeline run with mocked HTTP and fixture data."""
        # Mock USGS earthquake API
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            json=sample_usgs_response,
            status=200,
        )

        # Mock USGS significant feed
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson",
            json=sample_significant_response,
            status=200,
        )

        # Mock REST Countries for each country in the fixture
        for cc, data in sample_countries.items():
            responses.add(
                responses.GET,
                f"https://restcountries.com/v3.1/alpha/{cc}",
                json=[data],
                status=200,
            )

        # Mock reverse_geocoder: 3 JP + 2 CL (matches fixture order)
        mock_geo = [
            {"cc": "JP"},
            {"cc": "JP"},
            {"cc": "JP"},
            {"cc": "CL"},
            {"cc": "CL"},
        ]

        with (
            patch("seismic_risk.geo.rg.search", return_value=mock_geo),
            patch(
                "seismic_risk.fetchers.airports.OURAIRPORTS_CSV_URL",
                str(sample_airports_csv_path),
            ),
        ):
            config = SeismicRiskConfig(
                min_magnitude=4.0,
                days_lookback=30,
                min_quakes_per_country=3,
                max_airport_distance_km=400.0,
                output_file=tmp_path / "test_output.json",
            )
            results = run_pipeline(config)

        # JP should qualify (3 quakes), CL should not (only 2)
        assert len(results) >= 1
        country_names = [r.country for r in results]
        assert "Japan" in country_names

        for r in results:
            assert r.earthquake_count >= 3
            assert r.seismic_hub_risk_score > 0
            assert len(r.exposed_airports) > 0
            assert r.iso_alpha2 != ""
            assert r.iso_alpha3 != ""
            # Enriched data: earthquakes list and per-airport scoring
            assert len(r.earthquakes) >= 3
            for ap in r.exposed_airports:
                assert len(ap.nearby_quakes) > 0
                assert ap.exposure_score > 0
                for nq in ap.nearby_quakes:
                    assert nq.earthquake_id
                    assert nq.distance_km >= 0

    @responses.activate
    def test_empty_response_returns_empty(self, tmp_path):
        """Pipeline returns empty list when no earthquakes found."""
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            json={"type": "FeatureCollection", "features": []},
            status=200,
        )
        config = SeismicRiskConfig(output_file=tmp_path / "empty.json")
        results = run_pipeline(config)
        assert results == []

    @responses.activate
    def test_no_qualifying_countries(self, tmp_path):
        """Pipeline returns empty when no country meets the quake threshold."""
        # Only 1 earthquake per country — below default threshold of 3
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "id": "test1",
                        "properties": {
                            "mag": 5.0,
                            "place": "Test",
                            "time": 1700000000000,
                        },
                        "geometry": {
                            "type": "Point",
                            "coordinates": [141.5, 38.3, 30.0],
                        },
                    }
                ],
            },
            status=200,
        )

        mock_geo = [{"cc": "JP"}]
        with patch("seismic_risk.geo.rg.search", return_value=mock_geo):
            config = SeismicRiskConfig(
                min_quakes_per_country=3,
                output_file=tmp_path / "empty.json",
            )
            results = run_pipeline(config)

        assert results == []
