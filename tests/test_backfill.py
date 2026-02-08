"""Tests for the historical backfill date chunking logic."""

from __future__ import annotations

from datetime import date

from backfill import generate_month_ranges


class TestGenerateMonthRanges:
    def test_single_month(self) -> None:
        """Generate ranges for a single complete month."""
        months = generate_month_ranges(2024, 1, end_date=date(2024, 2, 1))
        assert len(months) == 1
        first, last, snap = months[0]
        assert first == date(2024, 1, 1)
        assert last == date(2024, 1, 31)
        assert snap == date(2024, 1, 31)

    def test_multiple_months(self) -> None:
        """Generate ranges spanning several months."""
        months = generate_month_ranges(2024, 10, end_date=date(2025, 2, 15))
        assert len(months) == 4  # Oct, Nov, Dec 2024, Jan 2025
        assert months[0][0] == date(2024, 10, 1)
        assert months[-1][0] == date(2025, 1, 1)
        assert months[-1][1] == date(2025, 1, 31)

    def test_excludes_current_month(self) -> None:
        """The current (incomplete) month is excluded."""
        months = generate_month_ranges(2025, 1, end_date=date(2025, 1, 15))
        assert len(months) == 0

    def test_february_leap_year(self) -> None:
        """February in a leap year has 29 days."""
        months = generate_month_ranges(2024, 2, end_date=date(2024, 3, 1))
        assert months[0][1] == date(2024, 2, 29)

    def test_february_non_leap_year(self) -> None:
        """February in a non-leap year has 28 days."""
        months = generate_month_ranges(2023, 2, end_date=date(2023, 3, 1))
        assert months[0][1] == date(2023, 2, 28)

    def test_year_boundary_crossing(self) -> None:
        """Ranges cross year boundary correctly."""
        months = generate_month_ranges(2023, 11, end_date=date(2024, 3, 1))
        assert len(months) == 4  # Nov 2023, Dec 2023, Jan 2024, Feb 2024
        assert months[1][0] == date(2023, 12, 1)
        assert months[2][0] == date(2024, 1, 1)

    def test_empty_range(self) -> None:
        """Returns empty list when start is at or after end."""
        months = generate_month_ranges(2025, 3, end_date=date(2025, 3, 1))
        assert months == []
