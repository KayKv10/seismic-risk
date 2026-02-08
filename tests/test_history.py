"""Tests for the history snapshot and trend computation module."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from seismic_risk.history import (
    AirportSnapshot,
    CountrySnapshot,
    DailySnapshot,
    compute_trends,
    load_history,
    save_snapshot,
)
from seismic_risk.models import CountryRiskResult, ExposedAirport, NearbyQuake

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_snapshot(history_dir: Path, snap: DailySnapshot) -> Path:
    """Write a DailySnapshot to disk as JSON."""
    from dataclasses import asdict

    path = history_dir / f"{snap.date}.json"
    path.write_text(json.dumps(asdict(snap), indent=2), encoding="utf-8")
    return path


def _make_result(
    iso3: str = "JPN",
    country: str = "Japan",
    score: float = 42.85,
    eq_count: int = 3,
    avg_mag: float = 5.37,
    airport_count: int = 2,
) -> CountryRiskResult:
    """Build a minimal CountryRiskResult for testing."""
    return CountryRiskResult(
        country=country,
        iso_alpha2=iso3[:2],
        iso_alpha3=iso3,
        capital="",
        population=0,
        area_km2=0.0,
        region="",
        subregion="",
        earthquake_count=eq_count,
        avg_magnitude=avg_mag,
        seismic_hub_risk_score=score,
        exposed_airports=[
            ExposedAirport(
                name=f"Airport {i}",
                iata_code=f"AP{i}",
                latitude=0.0,
                longitude=0.0,
                municipality="",
                closest_quake_distance_km=50.0,
            )
            for i in range(airport_count)
        ],
    )


# ---------------------------------------------------------------------------
# Snapshot persistence tests
# ---------------------------------------------------------------------------


class TestSaveSnapshot:
    def test_creates_file(self, tmp_path: Path) -> None:
        results = [_make_result()]
        path = save_snapshot(results, tmp_path, "exposure", snapshot_date=date(2026, 2, 6))

        assert path == tmp_path / "2026-02-06.json"
        assert path.exists()

        data = json.loads(path.read_text())
        assert data["date"] == "2026-02-06"
        assert data["scoring_method"] == "exposure"
        assert len(data["countries"]) == 1
        assert data["countries"][0]["iso_alpha3"] == "JPN"

    def test_idempotent_overwrite(self, tmp_path: Path) -> None:
        d = date(2026, 2, 6)
        save_snapshot([_make_result(score=10.0)], tmp_path, "exposure", snapshot_date=d)
        save_snapshot([_make_result(score=20.0)], tmp_path, "exposure", snapshot_date=d)

        data = json.loads((tmp_path / "2026-02-06.json").read_text())
        assert data["countries"][0]["score"] == 20.0

    def test_custom_date(self, tmp_path: Path) -> None:
        path = save_snapshot(
            [_make_result()], tmp_path, "exposure", snapshot_date=date(2026, 1, 15)
        )
        assert path.name == "2026-01-15.json"

    def test_creates_directory(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested"
        save_snapshot([_make_result()], nested, "exposure", snapshot_date=date(2026, 2, 6))

        assert nested.is_dir()
        assert (nested / "2026-02-06.json").exists()

    def test_snapshot_schema(self, tmp_path: Path) -> None:
        results = [_make_result(score=42.85, eq_count=3, avg_mag=5.37, airport_count=2)]
        save_snapshot(results, tmp_path, "exposure", snapshot_date=date(2026, 2, 6))

        data = json.loads((tmp_path / "2026-02-06.json").read_text())
        c = data["countries"][0]
        assert c["score"] == 42.85
        assert c["earthquake_count"] == 3
        assert c["exposed_airport_count"] == 2
        assert c["avg_magnitude"] == 5.37


# ---------------------------------------------------------------------------
# History loading tests
# ---------------------------------------------------------------------------


class TestLoadHistory:
    def test_empty_dir(self, tmp_path: Path) -> None:
        assert load_history(tmp_path) == []

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        assert load_history(tmp_path / "does_not_exist") == []

    def test_single_snapshot(self, tmp_path: Path) -> None:
        snap = DailySnapshot(
            date="2026-02-06",
            scoring_method="exposure",
            countries=[CountrySnapshot("JPN", "Japan", 42.85, 3, 2, 5.37)],
        )
        _write_snapshot(tmp_path, snap)

        result = load_history(tmp_path)
        assert len(result) == 1
        assert result[0].date == "2026-02-06"
        assert result[0].countries[0].iso_alpha3 == "JPN"

    def test_chronological_order(self, tmp_path: Path) -> None:
        for d in ["2026-02-04", "2026-02-06", "2026-02-05"]:
            snap = DailySnapshot(
                date=d,
                scoring_method="exposure",
                countries=[CountrySnapshot("JPN", "Japan", 40.0, 3, 2, 5.0)],
            )
            _write_snapshot(tmp_path, snap)

        result = load_history(tmp_path)
        dates = [s.date for s in result]
        assert dates == ["2026-02-04", "2026-02-05", "2026-02-06"]

    def test_max_days_cap(self, tmp_path: Path) -> None:
        for i in range(5):
            snap = DailySnapshot(
                date=f"2026-02-0{i + 1}",
                scoring_method="exposure",
                countries=[CountrySnapshot("JPN", "Japan", float(i), 1, 1, 5.0)],
            )
            _write_snapshot(tmp_path, snap)

        result = load_history(tmp_path, max_days=3)
        assert len(result) == 3
        assert result[0].date == "2026-02-03"

    def test_skips_invalid_json(self, tmp_path: Path) -> None:
        # Write a valid snapshot
        snap = DailySnapshot(
            date="2026-02-06",
            scoring_method="exposure",
            countries=[CountrySnapshot("JPN", "Japan", 42.0, 3, 2, 5.0)],
        )
        _write_snapshot(tmp_path, snap)

        # Write an invalid file
        (tmp_path / "2026-02-05.json").write_text("not valid json")

        result = load_history(tmp_path)
        assert len(result) == 1
        assert result[0].date == "2026-02-06"


# ---------------------------------------------------------------------------
# Trend computation tests
# ---------------------------------------------------------------------------


class TestComputeTrends:
    def test_no_history_returns_none(self) -> None:
        results = [_make_result()]
        assert compute_trends([], results, "exposure") is None

    def test_score_increased(self, tmp_path: Path) -> None:
        history = [
            DailySnapshot(
                date="2026-02-05",
                scoring_method="exposure",
                countries=[CountrySnapshot("JPN", "Japan", 30.0, 3, 2, 5.0)],
            ),
        ]
        results = [_make_result(score=42.85)]

        trends = compute_trends(history, results, "exposure")
        assert trends is not None
        ct = trends.country_trends["JPN"]
        assert ct.trend_direction == "up"
        assert ct.score_delta == 12.85
        assert ct.previous_score == 30.0

    def test_score_decreased(self) -> None:
        history = [
            DailySnapshot(
                date="2026-02-05",
                scoring_method="exposure",
                countries=[CountrySnapshot("JPN", "Japan", 50.0, 3, 2, 5.0)],
            ),
        ]
        results = [_make_result(score=42.85)]

        trends = compute_trends(history, results, "exposure")
        assert trends is not None
        ct = trends.country_trends["JPN"]
        assert ct.trend_direction == "down"
        assert ct.score_delta == -7.15

    def test_score_stable(self) -> None:
        history = [
            DailySnapshot(
                date="2026-02-05",
                scoring_method="exposure",
                countries=[CountrySnapshot("JPN", "Japan", 42.85, 3, 2, 5.0)],
            ),
        ]
        results = [_make_result(score=42.85)]

        trends = compute_trends(history, results, "exposure")
        assert trends is not None
        ct = trends.country_trends["JPN"]
        assert ct.trend_direction == "stable"
        assert ct.score_delta == 0.0

    def test_new_country(self) -> None:
        history = [
            DailySnapshot(
                date="2026-02-05",
                scoring_method="exposure",
                countries=[CountrySnapshot("PHL", "Philippines", 91.0, 18, 5, 5.3)],
            ),
        ]
        results = [_make_result(iso3="JPN", country="Japan", score=42.85)]

        trends = compute_trends(history, results, "exposure")
        assert trends is not None
        ct = trends.country_trends["JPN"]
        assert ct.is_new is True
        assert ct.trend_direction == "new"
        assert "JPN" in trends.new_countries

    def test_gone_country(self) -> None:
        history = [
            DailySnapshot(
                date="2026-02-05",
                scoring_method="exposure",
                countries=[
                    CountrySnapshot("JPN", "Japan", 42.85, 3, 2, 5.0),
                    CountrySnapshot("PHL", "Philippines", 91.0, 18, 5, 5.3),
                ],
            ),
        ]
        # Only Japan in current results — Philippines gone
        results = [_make_result(iso3="JPN", score=42.85)]

        trends = compute_trends(history, results, "exposure")
        assert trends is not None
        assert "PHL" in trends.gone_countries
        ct = trends.country_trends["PHL"]
        assert ct.is_gone is True
        assert ct.trend_direction == "gone"
        assert ct.current_score == 0.0

    def test_gap_days(self) -> None:
        """'Previous' is the last available snapshot, even with gaps."""
        history = [
            DailySnapshot(
                date="2026-02-01",
                scoring_method="exposure",
                countries=[CountrySnapshot("JPN", "Japan", 30.0, 3, 2, 5.0)],
            ),
            DailySnapshot(
                date="2026-02-03",
                scoring_method="exposure",
                countries=[CountrySnapshot("JPN", "Japan", 35.0, 3, 2, 5.0)],
            ),
            # Feb 02, 04, 05 missing — that's fine
        ]
        results = [_make_result(score=42.85)]

        trends = compute_trends(history, results, "exposure")
        assert trends is not None
        ct = trends.country_trends["JPN"]
        # Previous should be from Feb 03 (most recent), not Feb 01
        assert ct.previous_score == 35.0
        assert ct.score_delta == 7.85

    def test_sparkline_data(self) -> None:
        history = [
            DailySnapshot(
                date=f"2026-02-0{i}",
                scoring_method="exposure",
                countries=[CountrySnapshot("JPN", "Japan", float(10 * i), 3, 2, 5.0)],
            )
            for i in range(1, 6)
        ]
        results = [_make_result(score=60.0)]

        trends = compute_trends(history, results, "exposure")
        assert trends is not None
        ct = trends.country_trends["JPN"]
        # 5 history entries + 1 current = 6 data points
        assert len(ct.scores) == 6
        assert len(ct.dates) == 6
        assert ct.scores[:5] == [10.0, 20.0, 30.0, 40.0, 50.0]
        assert ct.scores[-1] == 60.0

    def test_history_days_count(self) -> None:
        history = [
            DailySnapshot(
                date=f"2026-02-0{i}",
                scoring_method="exposure",
                countries=[CountrySnapshot("JPN", "Japan", 40.0, 3, 2, 5.0)],
            )
            for i in range(1, 4)
        ]
        results = [_make_result()]

        trends = compute_trends(history, results, "exposure")
        assert trends is not None
        assert trends.history_days == 3

    def test_multiple_countries(self) -> None:
        history = [
            DailySnapshot(
                date="2026-02-05",
                scoring_method="exposure",
                countries=[
                    CountrySnapshot("JPN", "Japan", 42.0, 3, 2, 5.0),
                    CountrySnapshot("PHL", "Philippines", 90.0, 18, 5, 5.3),
                ],
            ),
        ]
        results = [
            _make_result(iso3="JPN", country="Japan", score=45.0),
            _make_result(iso3="PHL", country="Philippines", score=85.0),
        ]

        trends = compute_trends(history, results, "exposure")
        assert trends is not None
        assert "JPN" in trends.country_trends
        assert "PHL" in trends.country_trends
        assert trends.country_trends["JPN"].trend_direction == "up"
        assert trends.country_trends["PHL"].trend_direction == "down"


# ---------------------------------------------------------------------------
# Helpers for airport-level tests
# ---------------------------------------------------------------------------


def _make_result_with_airports(
    iso3: str = "JPN",
    country: str = "Japan",
    score: float = 42.85,
    eq_count: int = 3,
    avg_mag: float = 5.37,
    airports: list[ExposedAirport] | None = None,
) -> CountryRiskResult:
    """Build a CountryRiskResult with realistic airport + NearbyQuake data."""
    if airports is None:
        airports = [
            ExposedAirport(
                name="Narita International Airport",
                iata_code="NRT",
                latitude=35.76,
                longitude=140.39,
                municipality="Narita",
                closest_quake_distance_km=18.2,
                nearby_quakes=[
                    NearbyQuake(
                        earthquake_id="eq1",
                        magnitude=6.1,
                        latitude=35.7,
                        longitude=140.2,
                        depth_km=20.0,
                        time_ms=1700200000000,
                        place="Near Tokyo",
                        distance_km=18.2,
                        exposure_contribution=58.42,
                    ),
                ],
                exposure_score=58.42,
            ),
            ExposedAirport(
                name="Haneda Airport",
                iata_code="HND",
                latitude=35.55,
                longitude=139.78,
                municipality="Tokyo",
                closest_quake_distance_km=45.0,
                nearby_quakes=[
                    NearbyQuake(
                        earthquake_id="eq1",
                        magnitude=6.1,
                        latitude=35.7,
                        longitude=140.2,
                        depth_km=20.0,
                        time_ms=1700200000000,
                        place="Near Tokyo",
                        distance_km=45.0,
                        exposure_contribution=24.10,
                    ),
                ],
                exposure_score=24.10,
            ),
        ]
    return CountryRiskResult(
        country=country,
        iso_alpha2=iso3[:2],
        iso_alpha3=iso3,
        capital="",
        population=0,
        area_km2=0.0,
        region="",
        subregion="",
        earthquake_count=eq_count,
        avg_magnitude=avg_mag,
        seismic_hub_risk_score=score,
        exposed_airports=airports,
    )


# ---------------------------------------------------------------------------
# Airport snapshot persistence tests
# ---------------------------------------------------------------------------


class TestAirportSnapshot:
    def test_snapshot_includes_airport_data(self, tmp_path: Path) -> None:
        results = [_make_result_with_airports()]
        save_snapshot(results, tmp_path, "exposure", snapshot_date=date(2026, 2, 6))

        data = json.loads((tmp_path / "2026-02-06.json").read_text())
        c = data["countries"][0]
        assert "airports" in c
        assert len(c["airports"]) == 2
        nrt = c["airports"][0]
        assert nrt["iata_code"] == "NRT"
        assert nrt["name"] == "Narita International Airport"
        assert nrt["exposure_score"] == 58.42
        assert nrt["nearby_quake_count"] == 1
        assert nrt["closest_quake_km"] == 18.2
        assert nrt["max_pga_g"] is None

    def test_snapshot_airport_pga_captured(self, tmp_path: Path) -> None:
        airports = [
            ExposedAirport(
                name="Test Airport",
                iata_code="TST",
                latitude=35.0,
                longitude=140.0,
                municipality="Test",
                closest_quake_distance_km=10.0,
                nearby_quakes=[
                    NearbyQuake(
                        earthquake_id="eq1",
                        magnitude=6.0,
                        latitude=35.1,
                        longitude=140.1,
                        depth_km=10.0,
                        time_ms=1700200000000,
                        place="Near Test",
                        distance_km=10.0,
                        exposure_contribution=50.0,
                        pga_g=0.0523,
                        mmi=5.2,
                    ),
                    NearbyQuake(
                        earthquake_id="eq2",
                        magnitude=5.5,
                        latitude=35.2,
                        longitude=140.2,
                        depth_km=15.0,
                        time_ms=1700300000000,
                        place="Near Test 2",
                        distance_km=20.0,
                        exposure_contribution=25.0,
                        pga_g=0.0312,
                        mmi=4.1,
                    ),
                ],
                exposure_score=75.0,
            ),
        ]
        results = [_make_result_with_airports(airports=airports)]
        save_snapshot(results, tmp_path, "shakemap", snapshot_date=date(2026, 2, 6))

        data = json.loads((tmp_path / "2026-02-06.json").read_text())
        ap = data["countries"][0]["airports"][0]
        assert ap["max_pga_g"] == 0.0523  # max of 0.0523 and 0.0312

    def test_snapshot_airport_no_pga(self, tmp_path: Path) -> None:
        results = [_make_result_with_airports()]
        save_snapshot(results, tmp_path, "heuristic", snapshot_date=date(2026, 2, 6))

        data = json.loads((tmp_path / "2026-02-06.json").read_text())
        ap = data["countries"][0]["airports"][0]
        assert ap["max_pga_g"] is None

    def test_snapshot_schema_backward_fields(self, tmp_path: Path) -> None:
        results = [_make_result_with_airports()]
        save_snapshot(results, tmp_path, "exposure", snapshot_date=date(2026, 2, 6))

        data = json.loads((tmp_path / "2026-02-06.json").read_text())
        c = data["countries"][0]
        # Original fields still present
        assert "iso_alpha3" in c
        assert "score" in c
        assert "earthquake_count" in c
        assert "exposed_airport_count" in c
        assert "avg_magnitude" in c
        # New field present
        assert "airports" in c


# ---------------------------------------------------------------------------
# Load history backward compatibility tests
# ---------------------------------------------------------------------------


class TestLoadHistoryBackwardCompat:
    def test_load_old_format_snapshot(self, tmp_path: Path) -> None:
        """Old snapshots without 'airports' key should load with airports=[]."""
        old_data = {
            "date": "2026-02-05",
            "scoring_method": "heuristic",
            "countries": [
                {
                    "iso_alpha3": "JPN",
                    "country": "Japan",
                    "score": 42.85,
                    "earthquake_count": 3,
                    "exposed_airport_count": 2,
                    "avg_magnitude": 5.37,
                }
            ],
        }
        (tmp_path / "2026-02-05.json").write_text(json.dumps(old_data))

        result = load_history(tmp_path)
        assert len(result) == 1
        assert result[0].countries[0].airports == []

    def test_load_new_format_snapshot(self, tmp_path: Path) -> None:
        """New snapshots with 'airports' key should deserialize AirportSnapshot objects."""
        new_data = {
            "date": "2026-02-06",
            "scoring_method": "shakemap",
            "countries": [
                {
                    "iso_alpha3": "JPN",
                    "country": "Japan",
                    "score": 42.85,
                    "earthquake_count": 3,
                    "exposed_airport_count": 2,
                    "avg_magnitude": 5.37,
                    "airports": [
                        {
                            "iata_code": "NRT",
                            "name": "Narita",
                            "exposure_score": 58.42,
                            "nearby_quake_count": 1,
                            "closest_quake_km": 18.2,
                            "max_pga_g": 0.0523,
                        }
                    ],
                }
            ],
        }
        (tmp_path / "2026-02-06.json").write_text(json.dumps(new_data))

        result = load_history(tmp_path)
        assert len(result) == 1
        ap = result[0].countries[0].airports[0]
        assert isinstance(ap, AirportSnapshot)
        assert ap.iata_code == "NRT"
        assert ap.exposure_score == 58.42
        assert ap.max_pga_g == 0.0523

    def test_load_mixed_format_history(self, tmp_path: Path) -> None:
        """Mixed old/new format files should both load correctly."""
        old_data = {
            "date": "2026-02-05",
            "scoring_method": "heuristic",
            "countries": [
                {
                    "iso_alpha3": "JPN",
                    "country": "Japan",
                    "score": 40.0,
                    "earthquake_count": 3,
                    "exposed_airport_count": 2,
                    "avg_magnitude": 5.0,
                }
            ],
        }
        new_data = {
            "date": "2026-02-06",
            "scoring_method": "shakemap",
            "countries": [
                {
                    "iso_alpha3": "JPN",
                    "country": "Japan",
                    "score": 42.85,
                    "earthquake_count": 3,
                    "exposed_airport_count": 2,
                    "avg_magnitude": 5.37,
                    "airports": [
                        {
                            "iata_code": "NRT",
                            "name": "Narita",
                            "exposure_score": 58.42,
                            "nearby_quake_count": 1,
                            "closest_quake_km": 18.2,
                            "max_pga_g": None,
                        }
                    ],
                }
            ],
        }
        (tmp_path / "2026-02-05.json").write_text(json.dumps(old_data))
        (tmp_path / "2026-02-06.json").write_text(json.dumps(new_data))

        result = load_history(tmp_path)
        assert len(result) == 2
        assert result[0].countries[0].airports == []
        assert len(result[1].countries[0].airports) == 1


# ---------------------------------------------------------------------------
# Airport trend computation tests
# ---------------------------------------------------------------------------


def _snapshot_with_airports(
    snap_date: str,
    iso3: str = "JPN",
    country: str = "Japan",
    score: float = 42.85,
    airports: list[AirportSnapshot] | None = None,
) -> DailySnapshot:
    """Build a DailySnapshot with airport data for trend tests."""
    if airports is None:
        airports = [
            AirportSnapshot("NRT", "Narita", 58.42, 1, 18.2),
            AirportSnapshot("HND", "Haneda", 24.10, 1, 45.0),
        ]
    return DailySnapshot(
        date=snap_date,
        scoring_method="exposure",
        countries=[
            CountrySnapshot(
                iso_alpha3=iso3,
                country=country,
                score=score,
                earthquake_count=3,
                exposed_airport_count=len(airports),
                avg_magnitude=5.37,
                airports=airports,
            ),
        ],
    )


class TestAirportTrends:
    def test_airport_trend_score_increased(self) -> None:
        history = [
            _snapshot_with_airports(
                "2026-02-05",
                airports=[AirportSnapshot("NRT", "Narita", 30.0, 1, 18.2)],
            ),
        ]
        results = [_make_result_with_airports(
            airports=[
                ExposedAirport(
                    name="Narita", iata_code="NRT", latitude=35.76, longitude=140.39,
                    municipality="Narita", closest_quake_distance_km=18.2,
                    exposure_score=50.0,
                ),
            ],
        )]

        trends = compute_trends(history, results, "exposure")
        assert trends is not None
        at = trends.airport_trends["NRT"]
        assert at.trend_direction == "up"
        assert at.score_delta == 20.0
        assert at.previous_score == 30.0

    def test_airport_trend_score_decreased(self) -> None:
        history = [
            _snapshot_with_airports(
                "2026-02-05",
                airports=[AirportSnapshot("NRT", "Narita", 50.0, 1, 18.2)],
            ),
        ]
        results = [_make_result_with_airports(
            airports=[
                ExposedAirport(
                    name="Narita", iata_code="NRT", latitude=35.76, longitude=140.39,
                    municipality="Narita", closest_quake_distance_km=18.2,
                    exposure_score=20.0,
                ),
            ],
        )]

        trends = compute_trends(history, results, "exposure")
        assert trends is not None
        at = trends.airport_trends["NRT"]
        assert at.trend_direction == "down"
        assert at.score_delta == -30.0

    def test_airport_trend_stable(self) -> None:
        history = [
            _snapshot_with_airports(
                "2026-02-05",
                airports=[AirportSnapshot("NRT", "Narita", 50.0, 1, 18.2)],
            ),
        ]
        results = [_make_result_with_airports(
            airports=[
                ExposedAirport(
                    name="Narita", iata_code="NRT", latitude=35.76, longitude=140.39,
                    municipality="Narita", closest_quake_distance_km=18.2,
                    exposure_score=50.0,
                ),
            ],
        )]

        trends = compute_trends(history, results, "exposure")
        assert trends is not None
        at = trends.airport_trends["NRT"]
        assert at.trend_direction == "stable"
        assert at.score_delta == 0.0

    def test_airport_trend_new_airport(self) -> None:
        history = [
            _snapshot_with_airports(
                "2026-02-05",
                airports=[AirportSnapshot("HND", "Haneda", 24.0, 1, 45.0)],
            ),
        ]
        results = [_make_result_with_airports(
            airports=[
                ExposedAirport(
                    name="Narita", iata_code="NRT", latitude=35.76, longitude=140.39,
                    municipality="Narita", closest_quake_distance_km=18.2,
                    exposure_score=58.42,
                ),
            ],
        )]

        trends = compute_trends(history, results, "exposure")
        assert trends is not None
        at = trends.airport_trends["NRT"]
        assert at.is_new is True
        assert at.trend_direction == "new"

    def test_airport_trend_gone_airport(self) -> None:
        history = [
            _snapshot_with_airports(
                "2026-02-05",
                airports=[
                    AirportSnapshot("NRT", "Narita", 58.42, 1, 18.2),
                    AirportSnapshot("HND", "Haneda", 24.10, 1, 45.0),
                ],
            ),
        ]
        # Only NRT in current results — HND gone
        results = [_make_result_with_airports(
            airports=[
                ExposedAirport(
                    name="Narita", iata_code="NRT", latitude=35.76, longitude=140.39,
                    municipality="Narita", closest_quake_distance_km=18.2,
                    exposure_score=58.42,
                ),
            ],
        )]

        trends = compute_trends(history, results, "exposure")
        assert trends is not None
        at = trends.airport_trends["HND"]
        assert at.is_gone is True
        assert at.trend_direction == "gone"
        assert at.current_score == 0.0

    def test_airport_trend_from_old_format_history(self) -> None:
        """Old snapshots (no airport data) → all current airports show as 'new'."""
        history = [
            DailySnapshot(
                date="2026-02-05",
                scoring_method="heuristic",
                countries=[CountrySnapshot("JPN", "Japan", 40.0, 3, 2, 5.0)],
            ),
        ]
        results = [_make_result_with_airports()]

        trends = compute_trends(history, results, "exposure")
        assert trends is not None
        assert "NRT" in trends.airport_trends
        assert "HND" in trends.airport_trends
        assert trends.airport_trends["NRT"].is_new is True
        assert trends.airport_trends["HND"].is_new is True
        assert trends.airport_trends["NRT"].days_tracked == 1

    def test_airport_trend_sparkline_data(self) -> None:
        history = [
            _snapshot_with_airports(
                f"2026-02-0{i}",
                airports=[AirportSnapshot("NRT", "Narita", float(10 * i), 1, 18.2)],
            )
            for i in range(1, 4)
        ]
        results = [_make_result_with_airports(
            airports=[
                ExposedAirport(
                    name="Narita", iata_code="NRT", latitude=35.76, longitude=140.39,
                    municipality="Narita", closest_quake_distance_km=18.2,
                    exposure_score=40.0,
                ),
            ],
        )]

        trends = compute_trends(history, results, "exposure")
        assert trends is not None
        at = trends.airport_trends["NRT"]
        # 3 history entries + 1 current = 4 data points
        assert len(at.scores) == 4
        assert len(at.dates) == 4
        assert at.scores[:3] == [10.0, 20.0, 30.0]
        assert at.scores[-1] == 40.0

    def test_compute_trends_returns_airport_trends(self) -> None:
        history = [_snapshot_with_airports("2026-02-05")]
        results = [_make_result_with_airports()]

        trends = compute_trends(history, results, "exposure")
        assert trends is not None
        assert isinstance(trends.airport_trends, dict)
        assert "NRT" in trends.airport_trends
        assert "HND" in trends.airport_trends
        assert trends.airport_trends["NRT"].country_iso3 == "JPN"
