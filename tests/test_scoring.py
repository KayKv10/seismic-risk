"""Tests for the scoring module."""

import pytest

from seismic_risk.models import Airport, Earthquake, ExposedAirport, SignificantEvent
from seismic_risk.scoring import (
    calculate_exposure_score,
    calculate_legacy_score,
    calculate_risk_score,
    compute_pager_context,
    compute_seismic_stats,
    find_exposed_airports,
    sum_airport_scores,
)


class TestFindExposedAirports:
    def test_airport_within_radius(self, sample_airports, sample_earthquakes):
        exposed = find_exposed_airports(
            sample_airports, sample_earthquakes, max_distance_km=400.0
        )
        assert len(exposed) > 0
        assert all(isinstance(a, ExposedAirport) for a in exposed)

    def test_airport_outside_radius(self, sample_airports, sample_earthquakes):
        exposed = find_exposed_airports(
            sample_airports, sample_earthquakes, max_distance_km=1.0
        )
        assert len(exposed) == 0

    def test_closest_distance_populated(self, sample_airports, sample_earthquakes):
        exposed = find_exposed_airports(
            sample_airports, sample_earthquakes, max_distance_km=400.0
        )
        for a in exposed:
            assert a.closest_quake_distance_km >= 0

    def test_empty_airports_returns_empty(self, sample_earthquakes):
        exposed = find_exposed_airports([], sample_earthquakes, max_distance_km=400.0)
        assert exposed == []

    def test_empty_earthquakes_returns_empty(self, sample_airports):
        exposed = find_exposed_airports(sample_airports, [], max_distance_km=400.0)
        assert exposed == []


class TestComputeSeismicStats:
    def test_average_magnitude(self, sample_earthquakes):
        avg_mag, _ = compute_seismic_stats(sample_earthquakes)
        expected = round((5.2 + 4.8 + 6.1) / 3, 2)
        assert avg_mag == expected

    def test_strongest_earthquake(self, sample_earthquakes):
        _, strongest = compute_seismic_stats(sample_earthquakes)
        assert strongest.magnitude == 6.1

    def test_strongest_depth(self, sample_earthquakes):
        _, strongest = compute_seismic_stats(sample_earthquakes)
        assert strongest.depth_km == 20.0

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            compute_seismic_stats([])


class TestComputePagerContext:
    def test_no_matching_significant(self, sample_earthquakes):
        highest, felt, tsunami, count = compute_pager_context(sample_earthquakes, {})
        assert highest is None
        assert felt == 0
        assert tsunami is False
        assert count == 0

    def test_matching_significant(self, sample_earthquakes):
        sig = {
            "us2025abc3": SignificantEvent(
                id="us2025abc3",
                alert="orange",
                felt=1500,
                tsunami=True,
                significance=800,
                title="M 6.1",
            )
        }
        highest, felt, tsunami, count = compute_pager_context(sample_earthquakes, sig)
        assert highest == "orange"
        assert felt == 1500
        assert tsunami is True
        assert count == 1

    def test_highest_alert_wins(self):
        quakes = [
            Earthquake(
                id="eq1",
                magnitude=5.0,
                latitude=0,
                longitude=0,
                depth_km=10,
                time_ms=1000,
                place="A",
                country_code="XX",
            ),
            Earthquake(
                id="eq2",
                magnitude=6.0,
                latitude=0,
                longitude=0,
                depth_km=10,
                time_ms=2000,
                place="B",
                country_code="XX",
            ),
        ]
        sig = {
            "eq1": SignificantEvent(
                id="eq1",
                alert="yellow",
                felt=100,
                tsunami=False,
                significance=400,
                title="A",
            ),
            "eq2": SignificantEvent(
                id="eq2",
                alert="red",
                felt=5000,
                tsunami=False,
                significance=900,
                title="B",
            ),
        }
        highest, felt, _, count = compute_pager_context(quakes, sig)
        assert highest == "red"
        assert felt == 5000
        assert count == 2


class TestCalculateExposureScore:
    def test_closer_quake_scores_higher(self):
        """A closer earthquake should produce a higher score."""
        airport = Airport(
            name="Test",
            iata_code="TST",
            latitude=35.0,
            longitude=140.0,
            municipality="Test City",
            iso_country="JP",
            airport_type="large_airport",
        )
        close_quake = Earthquake(
            id="close",
            magnitude=5.0,
            latitude=35.1,
            longitude=140.1,
            depth_km=10,
            time_ms=1000,
            place="Close",
            country_code="JP",
        )
        far_quake = Earthquake(
            id="far",
            magnitude=5.0,
            latitude=36.5,
            longitude=141.5,
            depth_km=10,
            time_ms=1000,
            place="Far",
            country_code="JP",
        )

        score_close = calculate_exposure_score([airport], [close_quake], max_distance_km=200)
        score_far = calculate_exposure_score([airport], [far_quake], max_distance_km=200)

        assert score_close > score_far

    def test_higher_magnitude_scores_higher(self):
        """A higher magnitude earthquake should produce a higher score."""
        airport = Airport(
            name="Test",
            iata_code="TST",
            latitude=35.0,
            longitude=140.0,
            municipality="Test City",
            iso_country="JP",
            airport_type="large_airport",
        )
        quake_m5 = Earthquake(
            id="m5",
            magnitude=5.0,
            latitude=35.1,
            longitude=140.1,
            depth_km=10,
            time_ms=1000,
            place="M5",
            country_code="JP",
        )
        quake_m6 = Earthquake(
            id="m6",
            magnitude=6.0,
            latitude=35.1,
            longitude=140.1,
            depth_km=10,
            time_ms=1000,
            place="M6",
            country_code="JP",
        )

        score_m5 = calculate_exposure_score([airport], [quake_m5], max_distance_km=200)
        score_m6 = calculate_exposure_score([airport], [quake_m6], max_distance_km=200)

        assert score_m6 > score_m5
        # M6 should be roughly 3.16x higher (10^0.5)
        assert score_m6 / score_m5 == pytest.approx(3.16, rel=0.1)

    def test_more_airports_scores_higher(self):
        """More airports exposed should produce a higher total score."""
        airports_1 = [
            Airport(
                name="Test1",
                iata_code="TS1",
                latitude=35.0,
                longitude=140.0,
                municipality="City1",
                iso_country="JP",
                airport_type="large_airport",
            )
        ]
        airports_2 = airports_1 + [
            Airport(
                name="Test2",
                iata_code="TS2",
                latitude=35.2,
                longitude=140.2,
                municipality="City2",
                iso_country="JP",
                airport_type="large_airport",
            )
        ]
        quakes = [
            Earthquake(
                id="eq1",
                magnitude=5.5,
                latitude=35.1,
                longitude=140.1,
                depth_km=10,
                time_ms=1000,
                place="Near",
                country_code="JP",
            )
        ]

        score_1 = calculate_exposure_score(airports_1, quakes, max_distance_km=200)
        score_2 = calculate_exposure_score(airports_2, quakes, max_distance_km=200)

        assert score_2 > score_1

    def test_no_quakes_in_range_returns_zero(self, sample_airports):
        """If no earthquakes are within range, score should be 0."""
        far_quake = Earthquake(
            id="far",
            magnitude=7.0,
            latitude=0,
            longitude=0,
            depth_km=10,
            time_ms=1000,
            place="Far away",
            country_code="XX",
        )
        score = calculate_exposure_score(sample_airports, [far_quake], max_distance_km=200)
        assert score == 0.0

    def test_returns_rounded_float(self, sample_airports, sample_earthquakes):
        """Score should be rounded to 2 decimal places."""
        score = calculate_exposure_score(
            sample_airports, sample_earthquakes, max_distance_km=400
        )
        assert score == round(score, 2)


class TestCalculateLegacyScore:
    def test_basic_formula(self):
        score = calculate_legacy_score(
            earthquake_count=10, avg_magnitude=5.0, exposed_airport_count=2
        )
        assert score == 25.0

    def test_zero_airports_raises(self):
        with pytest.raises(ValueError, match="zero"):
            calculate_legacy_score(10, 5.0, 0)

    def test_returns_rounded_float(self):
        score = calculate_legacy_score(7, 4.3, 3)
        assert score == pytest.approx(10.03, abs=0.01)


class TestCalculateRiskScoreDispatch:
    def test_exposure_method_default(self, sample_airports, sample_earthquakes):
        """Default method should use exposure scoring."""
        score = calculate_risk_score(
            airports=sample_airports,
            earthquakes=sample_earthquakes,
            max_distance_km=400,
        )
        expected = calculate_exposure_score(
            sample_airports, sample_earthquakes, max_distance_km=400
        )
        assert score == expected

    def test_legacy_method(self, sample_airports, sample_earthquakes):
        """Legacy method should use the old formula."""
        score = calculate_risk_score(
            airports=sample_airports,
            earthquakes=sample_earthquakes,
            max_distance_km=400,
            method="legacy",
            earthquake_count=3,
            avg_magnitude=5.37,
            exposed_airport_count=2,
        )
        expected = calculate_legacy_score(3, 5.37, 2)
        assert score == expected

    def test_unknown_method_raises(self, sample_airports, sample_earthquakes):
        with pytest.raises(ValueError, match="Unknown"):
            calculate_risk_score(
                airports=sample_airports,
                earthquakes=sample_earthquakes,
                method="invalid",  # type: ignore
            )

    def test_exposure_with_precomputed_airports(self, sample_airports, sample_earthquakes):
        """When exposed_airports is provided, should use sum_airport_scores."""
        exposed = find_exposed_airports(
            sample_airports, sample_earthquakes, max_distance_km=400
        )
        score = calculate_risk_score(
            airports=sample_airports,
            earthquakes=sample_earthquakes,
            max_distance_km=400,
            exposed_airports=exposed,
        )
        expected = sum_airport_scores(exposed)
        assert score == expected


class TestFindExposedAirportsEnriched:
    def test_nearby_quakes_populated(self, sample_airports, sample_earthquakes):
        """Each exposed airport should have nearby_quakes filled."""
        exposed = find_exposed_airports(
            sample_airports, sample_earthquakes, max_distance_km=400
        )
        for ap in exposed:
            assert len(ap.nearby_quakes) > 0

    def test_exposure_score_positive(self, sample_airports, sample_earthquakes):
        exposed = find_exposed_airports(
            sample_airports, sample_earthquakes, max_distance_km=400
        )
        for ap in exposed:
            assert ap.exposure_score > 0

    def test_nearby_quakes_sorted_by_distance(self, sample_airports, sample_earthquakes):
        exposed = find_exposed_airports(
            sample_airports, sample_earthquakes, max_distance_km=400
        )
        for ap in exposed:
            distances = [q.distance_km for q in ap.nearby_quakes]
            assert distances == sorted(distances)

    def test_exposure_score_equals_sum_of_contributions(
        self, sample_airports, sample_earthquakes
    ):
        exposed = find_exposed_airports(
            sample_airports, sample_earthquakes, max_distance_km=400
        )
        for ap in exposed:
            total = sum(q.exposure_contribution for q in ap.nearby_quakes)
            assert ap.exposure_score == pytest.approx(total, abs=0.02)

    def test_sum_airport_scores_matches_exposure_score(
        self, sample_airports, sample_earthquakes
    ):
        """sum_airport_scores should match calculate_exposure_score."""
        exposed = find_exposed_airports(
            sample_airports, sample_earthquakes, max_distance_km=400
        )
        summed = sum_airport_scores(exposed)
        direct = calculate_exposure_score(
            sample_airports, sample_earthquakes, max_distance_km=400
        )
        assert summed == pytest.approx(direct, abs=0.02)

    def test_nearby_quake_fields_populated(self, sample_airports, sample_earthquakes):
        exposed = find_exposed_airports(
            sample_airports, sample_earthquakes, max_distance_km=400
        )
        for ap in exposed:
            for nq in ap.nearby_quakes:
                assert nq.earthquake_id
                assert nq.magnitude > 0
                assert nq.distance_km >= 0
                assert nq.exposure_contribution > 0
