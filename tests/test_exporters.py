"""Tests for the export modules."""

from __future__ import annotations

import copy
import json
from dataclasses import replace

from seismic_risk.exporters.csv_export import export_csv
from seismic_risk.exporters.geojson_export import export_geojson
from seismic_risk.exporters.html_export import export_html
from seismic_risk.exporters.json_export import export_json
from seismic_risk.exporters.markdown_export import export_markdown


class TestJSONExport:
    def test_exports_list_of_dicts(self, sample_results, tmp_path):
        output = tmp_path / "test.json"
        export_json(sample_results, output)

        with open(output) as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["country"] == "Japan"

    def test_returns_output_path(self, sample_results, tmp_path):
        output = tmp_path / "test.json"
        result = export_json(sample_results, output)
        assert result == output


class TestGeoJSONExport:
    def test_exports_feature_collection(self, sample_results, tmp_path):
        output = tmp_path / "test.geojson"
        export_geojson(sample_results, output)

        with open(output) as f:
            data = json.load(f)

        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) > 0

    def test_contains_metadata(self, sample_results, tmp_path):
        output = tmp_path / "test.geojson"
        export_geojson(sample_results, output)

        with open(output) as f:
            data = json.load(f)

        assert "metadata" in data
        assert data["metadata"]["source"] == "seismic-risk"
        assert data["metadata"]["country_count"] == 1
        assert data["metadata"]["airport_count"] == 2

    def test_airport_features_have_required_properties(self, sample_results, tmp_path):
        output = tmp_path / "test.geojson"
        export_geojson(sample_results, output)

        with open(output) as f:
            data = json.load(f)

        airports = [
            f for f in data["features"] if f["properties"]["feature_type"] == "airport"
        ]
        assert len(airports) == 2

        for ap in airports:
            assert "name" in ap["properties"]
            assert "iata_code" in ap["properties"]
            assert "country_risk_score" in ap["properties"]
            assert "pager_alert" in ap["properties"]
            assert ap["geometry"]["type"] == "Point"
            assert len(ap["geometry"]["coordinates"]) == 2

    def test_earthquake_features_have_required_properties(self, sample_results, tmp_path):
        output = tmp_path / "test.geojson"
        export_geojson(sample_results, output)

        with open(output) as f:
            data = json.load(f)

        quakes = [
            f for f in data["features"] if f["properties"]["feature_type"] == "earthquake"
        ]
        assert len(quakes) == 3

        # Find the M6.1 earthquake
        strongest = [q for q in quakes if q["properties"]["magnitude"] == 6.1]
        assert len(strongest) == 1
        eq = strongest[0]
        assert eq["properties"]["depth_km"] == 20.0
        assert eq["properties"]["earthquake_id"] == "us2025abc3"
        assert eq["properties"]["place"] == "Near Tokyo"
        assert eq["properties"]["country"] == "Japan"

    def test_coordinates_are_lon_lat_order(self, sample_results, tmp_path):
        """GeoJSON uses [longitude, latitude] order."""
        output = tmp_path / "test.geojson"
        export_geojson(sample_results, output)

        with open(output) as f:
            data = json.load(f)

        for feature in data["features"]:
            geom = feature["geometry"]
            if geom["type"] == "Point":
                lon, lat = geom["coordinates"]
                assert -180 <= lon <= 180, "Longitude out of range"
                assert -90 <= lat <= 90, "Latitude out of range"
            elif geom["type"] == "LineString":
                for lon, lat in geom["coordinates"]:
                    assert -180 <= lon <= 180, "Longitude out of range"
                    assert -90 <= lat <= 90, "Latitude out of range"

    def test_returns_output_path(self, sample_results, tmp_path):
        output = tmp_path / "test.geojson"
        result = export_geojson(sample_results, output)
        assert result == output

    def test_empty_results_creates_empty_collection(self, tmp_path):
        output = tmp_path / "empty.geojson"
        export_geojson([], output)

        with open(output) as f:
            data = json.load(f)

        assert data["type"] == "FeatureCollection"
        assert data["features"] == []

    def test_connection_features_present(self, sample_results, tmp_path):
        output = tmp_path / "test.geojson"
        export_geojson(sample_results, output)

        with open(output) as f:
            data = json.load(f)

        connections = [
            f for f in data["features"] if f["properties"]["feature_type"] == "connection"
        ]
        assert len(connections) > 0
        for conn in connections:
            assert conn["geometry"]["type"] == "LineString"
            assert len(conn["geometry"]["coordinates"]) == 2
            assert "airport_iata" in conn["properties"]
            assert "earthquake_id" in conn["properties"]
            assert "distance_km" in conn["properties"]

    def test_airport_has_exposure_score_property(self, sample_results, tmp_path):
        output = tmp_path / "test.geojson"
        export_geojson(sample_results, output)

        with open(output) as f:
            data = json.load(f)

        airports = [
            f for f in data["features"] if f["properties"]["feature_type"] == "airport"
        ]
        for ap in airports:
            assert "exposure_score" in ap["properties"]
            assert ap["properties"]["exposure_score"] > 0
            assert "nearby_quake_count" in ap["properties"]

    def test_metadata_earthquake_count_matches(self, sample_results, tmp_path):
        output = tmp_path / "test.geojson"
        export_geojson(sample_results, output)

        with open(output) as f:
            data = json.load(f)

        quakes = [
            f for f in data["features"] if f["properties"]["feature_type"] == "earthquake"
        ]
        assert data["metadata"]["earthquake_count"] == len(quakes)

    def test_earthquake_features_have_felt_radius(self, sample_results, tmp_path):
        output = tmp_path / "test.geojson"
        export_geojson(sample_results, output)

        with open(output) as f:
            data = json.load(f)

        quakes = [
            f for f in data["features"]
            if f["properties"]["feature_type"] == "earthquake"
        ]
        for q in quakes:
            assert "felt_radius_km" in q["properties"]
            assert q["properties"]["felt_radius_km"] >= 5.0
            assert isinstance(q["properties"]["felt_radius_km"], float)

        # M6.1 should have larger felt radius than M4.8
        m61 = [q for q in quakes if q["properties"]["magnitude"] == 6.1][0]
        m48 = [q for q in quakes if q["properties"]["magnitude"] == 4.8][0]
        assert m61["properties"]["felt_radius_km"] > m48["properties"]["felt_radius_km"]


class TestHTMLExport:
    def test_exports_valid_html(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "<!DOCTYPE html>" in content
        assert "<html" in content
        assert "</html>" in content

    def test_includes_leaflet_resources(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "leaflet" in content.lower()
        assert "L.map" in content
        assert "L.geoJSON" in content

    def test_embeds_geojson_data(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "FeatureCollection" in content
        assert sample_results[0].country in content
        assert "Narita International Airport" in content

    def test_includes_summary_sidebar(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "Seismic Risk Assessment" in content
        assert "country-count" in content
        assert "airport-count" in content

    def test_includes_legend(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "Airport Exposure" in content
        assert "Airport Size" in content
        assert "legend" in content.lower()

    def test_embeds_connection_features(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "connection" in content
        assert "LineString" in content

    def test_returns_output_path(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        result = export_html(sample_results, output)
        assert result == output

    def test_layer_controls_present(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "L.control.layers" in content
        assert "'Airports'" in content
        assert "'Quakes near airports'" in content
        assert "'All quakes in region'" in content
        assert "'Connections'" in content

    def test_airport_features_have_movements_property(self, sample_results, tmp_path):
        from seismic_risk.exporters.html_export import _build_geojson_data

        data = _build_geojson_data(sample_results)
        airport_features = [
            f for f in data["features"]
            if f["properties"]["feature_type"] == "airport"
        ]
        for af in airport_features:
            assert "aircraft_movements_k" in af["properties"]
            assert af["properties"]["aircraft_movements_k"] > 0

    def test_top_airports_sidebar(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "top-airports-list" in content
        assert "Top 5 Most Exposed" in content

    def test_airport_uses_diamond_markers(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "L.divIcon" in content
        assert "airportSVG" in content

    def test_earthquakes_off_by_default(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "airportLayer.addTo(map)" in content
        assert "nearbyQuakeLayer.addTo(map)" not in content
        assert "allQuakeLayer.addTo(map)" not in content

    def test_quake_layers_are_mutually_exclusive(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "overlayadd" in content
        assert "nearbyQuakeLayer" in content
        assert "allQuakeLayer" in content

    def test_connected_quake_ids_built(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "connectedQuakeIds" in content
        assert "nearbyQuakes" in content

    def test_click_to_highlight_js_present(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "selectAirport" in content
        assert "clearSelection" in content
        assert "selectedAirport" in content
        assert "highlightedConnections" in content

    def test_airport_click_handler_wired(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "layer.on('click'" in content

    def test_map_click_clears_selection(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "map.on('click'" in content
        assert "clearSelection()" in content

    def test_highlight_css_present(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "airport-selected" in content

    def test_includes_movements_in_legend(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "movements/yr" in content

    def test_earthquake_features_have_felt_radius(self, sample_results, tmp_path):
        from seismic_risk.exporters.html_export import _build_geojson_data

        data = _build_geojson_data(sample_results)
        quakes = [
            f for f in data["features"]
            if f["properties"]["feature_type"] == "earthquake"
        ]
        for q in quakes:
            assert "felt_radius_km" in q["properties"]
            assert q["properties"]["felt_radius_km"] >= 5.0

    def test_uses_circle_not_circlemarker(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "L.circle(latlng" in content
        assert "L.circleMarker(latlng" not in content

    def test_earthquake_popup_shows_felt_radius(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "Felt radius" in content

    def test_earthquake_legend_section(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "Earthquake Shaking" in content
        assert "MMI V" in content

    def test_script_tag_injection_escaped(self, sample_results, tmp_path):
        """Ensure </script> in place names cannot break out of the script tag."""
        malicious_results = copy.deepcopy(sample_results)
        bad_quake = replace(
            malicious_results[0].earthquakes[0],
            place='Test</script><img src=x>',
        )
        malicious_results[0].earthquakes[0] = bad_quake
        output = tmp_path / "test.html"
        export_html(malicious_results, output)

        content = output.read_text()
        # The raw </script> must not appear inside the GeoJSON data block
        script_start = content.index("var data = ")
        script_end = content.index("// Categorize features")
        data_block = content[script_start:script_end]
        assert "</script>" not in data_block
        assert r"<\/script>" in data_block

    def test_overlayremove_clears_highlighted_quakes(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "overlayremove" in content
        assert "highlightedQuakes = []" in content

    def test_trend_data_embedded_when_provided(self, sample_results, sample_trends, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output, trends=sample_trends)

        content = output.read_text()
        assert "var trendData =" in content
        assert '"history_days": 7' in content
        assert '"JPN"' in content

    def test_trend_data_null_without_trends(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "var trendData = null;" in content

    def test_sparkline_js_function_present(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert "function buildSparkline" in content
        assert "polyline" in content

    def test_trend_section_hidden_by_default(self, sample_results, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output)

        content = output.read_text()
        assert 'id="trend-section"' in content
        assert 'style="display:none;"' in content

    def test_trend_xss_safe(self, sample_results, sample_trends, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output, trends=sample_trends)

        content = output.read_text()
        trend_start = content.index("var trendData =")
        trend_end = content.index(";", trend_start)
        trend_block = content[trend_start:trend_end]
        assert "</script>" not in trend_block

    def test_trend_data_includes_airports(self, sample_results, sample_trends, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output, trends=sample_trends)

        content = output.read_text()
        assert '"airports"' in content
        assert '"NRT"' in content

    def test_airport_sparkline_in_popup(self, sample_results, sample_trends, tmp_path):
        output = tmp_path / "test.html"
        export_html(sample_results, output, trends=sample_trends)

        content = output.read_text()
        assert "trendData.airports" in content
        assert "Exposure trend" in content

    def test_trend_data_airports_empty_without_airport_trends(
        self, sample_results, tmp_path
    ):
        from seismic_risk.history import CountryTrend, TrendSummary

        trends_no_airports = TrendSummary(
            date="2026-02-06",
            history_days=3,
            history_start="2026-02-04",
            country_trends={
                "JPN": CountryTrend(
                    iso_alpha3="JPN",
                    country="Japan",
                    scores=[42.85],
                    dates=["2026-02-06"],
                    current_score=42.85,
                    previous_score=None,
                    score_delta=0.0,
                    trend_direction="new",
                    is_new=True,
                    is_gone=False,
                    days_tracked=1,
                ),
            },
            airport_trends={},
            new_countries=["JPN"],
            gone_countries=[],
        )
        output = tmp_path / "test.html"
        export_html(sample_results, output, trends=trends_no_airports)

        content = output.read_text()
        assert '"airports": {}' in content


class TestAirportMovementsData:
    def test_movements_data_structure(self):
        from seismic_risk.data.airport_movements import (
            AIRPORT_MOVEMENTS,
            DEFAULT_MOVEMENTS,
        )

        assert isinstance(AIRPORT_MOVEMENTS, dict)
        assert len(AIRPORT_MOVEMENTS) >= 100
        for code, mvmts in AIRPORT_MOVEMENTS.items():
            assert len(code) == 3, f"Invalid IATA code: {code}"
            assert isinstance(mvmts, (int, float))
            assert mvmts > 0
        assert DEFAULT_MOVEMENTS > 0

    def test_known_airports_have_movements(self):
        from seismic_risk.data.airport_movements import AIRPORT_MOVEMENTS

        # NRT and HND are in the test fixtures
        assert "NRT" in AIRPORT_MOVEMENTS
        assert "HND" in AIRPORT_MOVEMENTS

    def test_cargo_hubs_present(self):
        from seismic_risk.data.airport_movements import AIRPORT_MOVEMENTS

        for code in ("MEM", "SDF", "ANC", "CVG"):
            assert code in AIRPORT_MOVEMENTS, f"Cargo hub {code} missing"


class TestCSVExport:
    def test_exports_csv_file(self, sample_results, tmp_path):
        import csv

        output = tmp_path / "test.csv"
        export_csv(sample_results, output)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2

    def test_returns_output_path(self, sample_results, tmp_path):
        output = tmp_path / "test.csv"
        result = export_csv(sample_results, output)
        assert result == output

    def test_correct_column_count(self, sample_results, tmp_path):
        import csv

        output = tmp_path / "test.csv"
        export_csv(sample_results, output)

        with open(output) as f:
            reader = csv.reader(f)
            header = next(reader)
            assert len(header) == 24
            for row in reader:
                assert len(row) == 24

    def test_header_names(self, sample_results, tmp_path):
        import csv

        output = tmp_path / "test.csv"
        export_csv(sample_results, output)

        with open(output) as f:
            reader = csv.reader(f)
            header = next(reader)

        assert header == [
            "country", "iso_alpha3", "iso_alpha2", "region", "capital",
            "population", "risk_score", "earthquake_count", "avg_magnitude",
            "pager_alert", "tsunami_warning", "significant_events",
            "airport_name", "iata_code", "municipality", "latitude",
            "longitude", "closest_quake_km", "exposure_score",
            "nearby_quake_count", "strongest_quake_mag", "strongest_quake_date",
            "max_pga_g", "max_mmi",
        ]

    def test_correct_row_count(self, sample_results, tmp_path):
        import csv

        output = tmp_path / "test.csv"
        export_csv(sample_results, output)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2  # NRT + HND

    def test_country_data_denormalized(self, sample_results, tmp_path):
        import csv

        output = tmp_path / "test.csv"
        export_csv(sample_results, output)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        for row in rows:
            assert row["country"] == "Japan"
            assert row["iso_alpha3"] == "JPN"
            assert row["iso_alpha2"] == "JP"
            assert row["region"] == "Asia"
            assert row["capital"] == "Tokyo"
            assert row["population"] == "125800000"

    def test_seismic_context_fields(self, sample_results, tmp_path):
        import csv

        output = tmp_path / "test.csv"
        export_csv(sample_results, output)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        for row in rows:
            assert row["earthquake_count"] == "3"
            assert row["avg_magnitude"] == "5.37"
            assert row["tsunami_warning"] == "False"
            assert row["significant_events"] == "1"

    def test_airport_data_present(self, sample_results, tmp_path):
        import csv

        output = tmp_path / "test.csv"
        export_csv(sample_results, output)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        iata_codes = {row["iata_code"] for row in rows}
        assert "NRT" in iata_codes
        assert "HND" in iata_codes

    def test_empty_results_creates_header_only(self, tmp_path):
        import csv

        output = tmp_path / "empty.csv"
        export_csv([], output)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 0


class TestMarkdownExport:
    def test_exports_markdown_file(self, sample_results, tmp_path):
        output = tmp_path / "test.md"
        export_markdown(sample_results, output)

        content = output.read_text()
        assert content.startswith("# Seismic Risk Report")

    def test_returns_output_path(self, sample_results, tmp_path):
        output = tmp_path / "test.md"
        result = export_markdown(sample_results, output)
        assert result == output

    def test_contains_country_summary_table(self, sample_results, tmp_path):
        output = tmp_path / "test.md"
        export_markdown(sample_results, output)

        content = output.read_text()
        assert "## Country Summary" in content
        assert "| Japan |" in content
        assert "| Region |" in content
        assert "| Avg Mag |" in content

    def test_contains_airport_details_table(self, sample_results, tmp_path):
        output = tmp_path / "test.md"
        export_markdown(sample_results, output)

        content = output.read_text()
        assert "## Airport Details" in content
        assert "| Municipality |" in content
        assert "Narita" in content
        assert "NRT" in content
        assert "HND" in content

    def test_country_summary_has_strongest_quake(self, sample_results, tmp_path):
        output = tmp_path / "test.md"
        export_markdown(sample_results, output)

        content = output.read_text()
        assert "| Strongest |" in content
        assert "M6.1" in content
        assert "2026-01-28" in content

    def test_country_summary_has_tsunami_column(self, sample_results, tmp_path):
        output = tmp_path / "test.md"
        export_markdown(sample_results, output)

        content = output.read_text()
        assert "| Tsunami |" in content
        assert "| No |" in content or "No" in content

    def test_contains_generation_timestamp(self, sample_results, tmp_path):
        output = tmp_path / "test.md"
        export_markdown(sample_results, output)

        content = output.read_text()
        assert "Generated:" in content
        assert "UTC" in content

    def test_table_has_pipe_delimiters(self, sample_results, tmp_path):
        output = tmp_path / "test.md"
        export_markdown(sample_results, output)

        content = output.read_text()
        lines = content.split("\n")
        table_lines = [line for line in lines if line.startswith("|")]
        assert len(table_lines) >= 6  # 2 headers + 2 separators + at least 2 data rows

    def test_empty_results(self, tmp_path):
        output = tmp_path / "empty.md"
        export_markdown([], output)

        content = output.read_text()
        assert "## Country Summary" in content
        assert "## Airport Details" in content

    def test_with_trends_has_summary_section(self, sample_results, sample_trends, tmp_path):
        output = tmp_path / "test.md"
        export_markdown(sample_results, output, trends=sample_trends)

        content = output.read_text()
        assert "## Trend Summary" in content
        assert "7 snapshots" in content

    def test_with_trends_has_trend_column(self, sample_results, sample_trends, tmp_path):
        output = tmp_path / "test.md"
        export_markdown(sample_results, output, trends=sample_trends)

        content = output.read_text()
        assert "| Trend |" in content
        assert "+2.8" in content or "+2.75" in content

    def test_without_trends_no_trend_column(self, sample_results, tmp_path):
        output = tmp_path / "test.md"
        export_markdown(sample_results, output)

        content = output.read_text()
        assert "| Trend |" not in content
        assert "## Trend Summary" not in content

    def test_new_country_indicator(self, sample_results, tmp_path):
        from seismic_risk.history import CountryTrend, TrendSummary

        trends_with_new = TrendSummary(
            date="2026-02-06",
            history_days=3,
            history_start="2026-02-04",
            country_trends={
                "JPN": CountryTrend(
                    iso_alpha3="JPN",
                    country="Japan",
                    scores=[42.85],
                    dates=["2026-02-06"],
                    current_score=42.85,
                    previous_score=None,
                    score_delta=0.0,
                    trend_direction="new",
                    is_new=True,
                    is_gone=False,
                    days_tracked=1,
                ),
            },
            airport_trends={},
            new_countries=["JPN"],
            gone_countries=[],
        )
        output = tmp_path / "test.md"
        export_markdown(sample_results, output, trends=trends_with_new)

        content = output.read_text()
        assert "NEW" in content
        assert "**New entries**: Japan" in content

    def test_gone_country_listed(self, sample_results, tmp_path):
        from seismic_risk.history import CountryTrend, TrendSummary

        trends_with_gone = TrendSummary(
            date="2026-02-06",
            history_days=3,
            history_start="2026-02-04",
            country_trends={
                "JPN": CountryTrend(
                    iso_alpha3="JPN",
                    country="Japan",
                    scores=[38.0, 40.0, 42.85],
                    dates=["2026-02-04", "2026-02-05", "2026-02-06"],
                    current_score=42.85,
                    previous_score=40.0,
                    score_delta=2.85,
                    trend_direction="up",
                    is_new=False,
                    is_gone=False,
                    days_tracked=3,
                ),
                "PHL": CountryTrend(
                    iso_alpha3="PHL",
                    country="Philippines",
                    scores=[91.0, 85.0],
                    dates=["2026-02-04", "2026-02-05"],
                    current_score=0.0,
                    previous_score=85.0,
                    score_delta=-85.0,
                    trend_direction="gone",
                    is_new=False,
                    is_gone=True,
                    days_tracked=2,
                ),
            },
            airport_trends={},
            new_countries=[],
            gone_countries=["PHL"],
        )
        output = tmp_path / "test.md"
        export_markdown(sample_results, output, trends=trends_with_gone)

        content = output.read_text()
        assert "**Dropped off**: Philippines" in content

    def test_markdown_airport_trend_column_present(
        self, sample_results, sample_trends, tmp_path
    ):
        output = tmp_path / "test.md"
        export_markdown(sample_results, output, trends=sample_trends)

        content = output.read_text()
        assert "| Trend" in content
        # Airport details section should have trend values
        assert "## Airport Details" in content

    def test_markdown_airport_trend_column_absent(self, sample_results, tmp_path):
        output = tmp_path / "test.md"
        export_markdown(sample_results, output)

        content = output.read_text()
        # Airport Details should exist but without Trend column
        assert "## Airport Details" in content
        # Extract just the airport details section
        details_start = content.index("## Airport Details")
        details_section = content[details_start:]
        # The first header line should not have "Trend" between "Exposure" and "Closest"
        header_line = details_section.split("\n")[2]  # first non-empty line after ##
        assert "| Trend" not in header_line

    def test_markdown_airport_movers_in_summary(
        self, sample_results, sample_trends, tmp_path
    ):
        output = tmp_path / "test.md"
        export_markdown(sample_results, output, trends=sample_trends)

        content = output.read_text()
        assert "**Top airport exposure changes**:" in content
        assert "NRT" in content


class TestPGAExporterIntegration:
    """Tests for PGA/MMI display in exporters when ShakeMap data is present."""

    def _make_results_with_pga(self, sample_results):
        """Create results with PGA/MMI data on one nearby quake."""
        results = copy.deepcopy(sample_results)
        # Replace first nearby quake on NRT with one that has pga_g/mmi
        nrt = results[0].exposed_airports[0]
        nrt.nearby_quakes[0] = replace(
            nrt.nearby_quakes[0],
            pga_g=0.0523,
            mmi=5.2,
        )
        return results

    def test_geojson_connection_has_pga(self, sample_results, tmp_path):
        results = self._make_results_with_pga(sample_results)
        output = tmp_path / "test.geojson"
        export_geojson(results, output)

        with open(output) as f:
            data = json.load(f)

        connections = [
            f for f in data["features"]
            if f["properties"]["feature_type"] == "connection"
        ]
        pga_conns = [c for c in connections if c["properties"]["pga_g"] is not None]
        assert len(pga_conns) >= 1
        assert pga_conns[0]["properties"]["pga_g"] == 0.0523
        assert pga_conns[0]["properties"]["mmi"] == 5.2

    def test_html_contains_shakemap_pga(self, sample_results, tmp_path):
        results = self._make_results_with_pga(sample_results)
        output = tmp_path / "test.html"
        export_html(results, output)

        content = output.read_text()
        assert "ShakeMap PGA" in content
        assert "max_pga_g" in content

    def test_csv_has_pga_columns(self, sample_results, tmp_path):
        import csv

        results = self._make_results_with_pga(sample_results)
        output = tmp_path / "test.csv"
        export_csv(results, output)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert "max_pga_g" in rows[0]
        assert "max_mmi" in rows[0]
        # NRT has PGA data (first row, highest exposure)
        pga_row = next(r for r in rows if r["iata_code"] == "NRT")
        assert pga_row["max_pga_g"] == "0.0523"
        assert pga_row["max_mmi"] == "5.2"
        # HND has no PGA data
        hnd_row = next(r for r in rows if r["iata_code"] == "HND")
        assert hnd_row["max_pga_g"] == ""

    def test_markdown_has_pga_column_when_present(self, sample_results, tmp_path):
        results = self._make_results_with_pga(sample_results)
        output = tmp_path / "test.md"
        export_markdown(results, output)

        content = output.read_text()
        assert "| Max PGA (g) |" in content
        assert "0.0523" in content

    def test_markdown_no_pga_column_without_data(self, sample_results, tmp_path):
        output = tmp_path / "test.md"
        export_markdown(sample_results, output)

        content = output.read_text()
        assert "| Max PGA (g) |" not in content
