"""Tests for geo.haversine."""

import pytest

from seismic_risk.geo import felt_radius_km, haversine


class TestHaversine:
    def test_zero_distance(self):
        assert haversine(35.6762, 139.6503, 35.6762, 139.6503) == 0.0

    def test_known_distance_tokyo_osaka(self):
        d = haversine(35.6762, 139.6503, 34.6937, 135.5023)
        assert 390 < d < 410

    def test_known_distance_new_york_london(self):
        d = haversine(40.7128, -74.0060, 51.5074, -0.1278)
        assert 5550 < d < 5590

    def test_antipodal_points(self):
        d = haversine(0, 0, 0, 180)
        assert 20010 < d < 20020

    def test_symmetry(self):
        d1 = haversine(35.6762, 139.6503, 34.6937, 135.5023)
        d2 = haversine(34.6937, 135.5023, 35.6762, 139.6503)
        assert d1 == pytest.approx(d2)

    def test_returns_float(self):
        result = haversine(0.0, 0.0, 1.0, 1.0)
        assert isinstance(result, float)

    def test_always_non_negative(self):
        assert haversine(-90, -180, 90, 180) >= 0


class TestFeltRadius:
    def test_returns_float(self):
        result = felt_radius_km(5.0, 10.0)
        assert isinstance(result, float)

    def test_always_positive(self):
        assert felt_radius_km(3.0, 100.0) >= 5.0
        assert felt_radius_km(2.0, 200.0) >= 5.0

    def test_minimum_radius(self):
        assert felt_radius_km(2.0, 300.0) == 5.0

    def test_larger_magnitude_larger_radius(self):
        r5 = felt_radius_km(5.0, 10.0)
        r6 = felt_radius_km(6.0, 10.0)
        r7 = felt_radius_km(7.0, 10.0)
        assert r7 > r6 > r5

    def test_deeper_quake_smaller_radius(self):
        r_shallow = felt_radius_km(6.0, 10.0)
        r_deep = felt_radius_km(6.0, 100.0)
        assert r_shallow > r_deep

    def test_fixture_m52_depth30(self):
        r = felt_radius_km(5.2, 30.0)
        assert 20 < r < 300

    def test_fixture_m48_depth45(self):
        """M4.8 at 45km is borderline — may return minimum felt radius."""
        r = felt_radius_km(4.8, 45.0)
        assert 5.0 <= r < 200

    def test_fixture_m61_depth20(self):
        r = felt_radius_km(6.1, 20.0)
        assert r > 50

    def test_zero_depth(self):
        r = felt_radius_km(5.0, 0.0)
        assert r > 5.0

    def test_negative_depth_treated_as_zero(self):
        r_neg = felt_radius_km(5.0, -5.0)
        r_zero = felt_radius_km(5.0, 0.0)
        assert r_neg == r_zero
