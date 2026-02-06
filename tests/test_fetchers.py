"""Tests for fetcher error paths and edge cases."""

from __future__ import annotations

import pytest
import responses
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError

from seismic_risk.fetchers.airports import fetch_airports
from seismic_risk.fetchers.countries import fetch_country_metadata
from seismic_risk.fetchers.usgs import fetch_earthquakes, fetch_significant_earthquakes


class TestFetchEarthquakes:
    @responses.activate
    def test_http_500_raises(self):
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            status=500,
        )
        with pytest.raises(HTTPError):
            fetch_earthquakes()

    @responses.activate
    def test_empty_features_returns_empty(self):
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            json={"type": "FeatureCollection", "features": []},
            status=200,
        )
        result = fetch_earthquakes()
        assert result == []

    @responses.activate
    def test_null_magnitude_filtered(self):
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "id": "test1",
                        "properties": {"mag": None, "time": 1700000000000, "place": "Test"},
                        "geometry": {"coordinates": [0, 0, 10]},
                    },
                    {
                        "id": "test2",
                        "properties": {"mag": 5.0, "time": 1700000000000, "place": "Test"},
                        "geometry": {"coordinates": [0, 0, 10]},
                    },
                ],
            },
            status=200,
        )
        result = fetch_earthquakes(min_magnitude=4.0)
        assert len(result) == 1
        assert result[0].id == "test2"

    @responses.activate
    def test_valid_response_returns_earthquakes(self):
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "id": "eq1",
                        "properties": {"mag": 6.0, "time": 1700000000000, "place": "Tokyo"},
                        "geometry": {"coordinates": [140.0, 35.0, 20.0]},
                    },
                ],
            },
            status=200,
        )
        result = fetch_earthquakes()
        assert len(result) == 1
        assert result[0].magnitude == 6.0
        assert result[0].latitude == 35.0
        assert result[0].longitude == 140.0

    @responses.activate
    def test_malformed_json_raises(self):
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            json={"unexpected": "format"},
            status=200,
        )
        with pytest.raises(KeyError):
            fetch_earthquakes()


class TestFetchSignificantEarthquakes:
    @responses.activate
    def test_http_500_returns_empty(self):
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson",
            status=500,
        )
        result = fetch_significant_earthquakes()
        assert result == {}

    @responses.activate
    def test_empty_features_returns_empty(self):
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson",
            json={"type": "FeatureCollection", "features": []},
            status=200,
        )
        result = fetch_significant_earthquakes()
        assert result == {}

    @responses.activate
    def test_valid_response_returns_events(self):
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson",
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "id": "sig1",
                        "properties": {
                            "alert": "orange",
                            "felt": 500,
                            "tsunami": 0,
                            "sig": 800,
                            "title": "M6.0 - Japan",
                        },
                        "geometry": {"coordinates": [140.0, 35.0, 20.0]},
                    },
                ],
            },
            status=200,
        )
        result = fetch_significant_earthquakes()
        assert "sig1" in result
        assert result["sig1"].alert == "orange"
        assert result["sig1"].felt == 500

    @responses.activate
    def test_network_error_returns_empty(self):
        responses.add(
            responses.GET,
            "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson",
            body=RequestsConnectionError("Connection refused"),
        )
        result = fetch_significant_earthquakes()
        assert result == {}


class TestFetchAirports:
    def test_valid_csv_returns_airports(self, sample_airports_csv_path):
        result = fetch_airports(
            airport_type="large_airport",
            country_codes={"JP"},
            url=str(sample_airports_csv_path),
            use_cache=False,
        )
        assert len(result) == 2
        iata_codes = {a.iata_code for a in result}
        assert "NRT" in iata_codes
        assert "HND" in iata_codes

    def test_empty_csv_returns_empty(self, tmp_path):
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text(
            "id,ident,type,name,latitude_deg,longitude_deg,"
            "elevation_ft,continent,iso_country,iso_region,"
            "municipality,scheduled_service,gps_code,iata_code,"
            "local_code,home_link,wikipedia_link,keywords\n"
        )
        result = fetch_airports(url=str(csv_path), use_cache=False)
        assert result == []

    def test_no_matching_type_returns_empty(self, sample_airports_csv_path):
        result = fetch_airports(
            airport_type="heliport",
            url=str(sample_airports_csv_path),
            use_cache=False,
        )
        assert result == []

    def test_country_filter_works(self, sample_airports_csv_path):
        result = fetch_airports(
            airport_type="large_airport",
            country_codes={"US"},
            url=str(sample_airports_csv_path),
            use_cache=False,
        )
        assert result == []


class TestFetchCountryMetadata:
    @responses.activate
    def test_http_404_omits_country(self):
        responses.add(
            responses.GET,
            "https://restcountries.com/v3.1/alpha/XX",
            status=404,
        )
        responses.add(
            responses.GET,
            "https://restcountries.com/v3.1/alpha/JP",
            json=[{"name": {"common": "Japan"}, "cca3": "JPN"}],
            status=200,
        )
        result = fetch_country_metadata({"XX", "JP"}, use_cache=False)
        assert "XX" not in result
        assert "JP" in result

    @responses.activate
    def test_all_fail_returns_empty(self):
        responses.add(
            responses.GET,
            "https://restcountries.com/v3.1/alpha/XX",
            status=500,
        )
        result = fetch_country_metadata({"XX"}, use_cache=False)
        assert result == {}

    @responses.activate
    def test_timeout_gracefully_skipped(self):
        responses.add(
            responses.GET,
            "https://restcountries.com/v3.1/alpha/JP",
            body=RequestsConnectionError("Timeout"),
        )
        result = fetch_country_metadata({"JP"}, use_cache=False)
        assert result == {}

    @responses.activate
    def test_valid_response_returns_metadata(self):
        responses.add(
            responses.GET,
            "https://restcountries.com/v3.1/alpha/JP",
            json=[{"name": {"common": "Japan"}, "cca3": "JPN", "population": 125800000}],
            status=200,
        )
        result = fetch_country_metadata({"JP"}, use_cache=False)
        assert "JP" in result
        assert result["JP"]["name"]["common"] == "Japan"

    def test_empty_country_codes_returns_empty(self):
        result = fetch_country_metadata(set(), use_cache=False)
        assert result == {}
