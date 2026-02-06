"""Historical snapshot storage and trend computation."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from seismic_risk.models import CountryRiskResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CountrySnapshot:
    """Compact daily metrics for one country."""

    iso_alpha3: str
    country: str
    score: float
    earthquake_count: int
    exposed_airport_count: int
    avg_magnitude: float


@dataclass(frozen=True)
class DailySnapshot:
    """One day's complete snapshot of pipeline results."""

    date: str  # ISO format: "YYYY-MM-DD"
    scoring_method: str
    countries: list[CountrySnapshot]


@dataclass(frozen=True)
class CountryTrend:
    """Computed trend for a single country over the history window."""

    iso_alpha3: str
    country: str
    scores: list[float]  # chronological, most recent last
    dates: list[str]  # matching dates for sparkline labels
    current_score: float
    previous_score: float | None  # None if first day
    score_delta: float  # current - previous (0.0 if no previous)
    trend_direction: str  # "up" | "down" | "stable" | "new"
    is_new: bool  # not in previous snapshot
    is_gone: bool  # in previous but not current
    days_tracked: int


@dataclass(frozen=True)
class TrendSummary:
    """Aggregate trends passed to exporters."""

    date: str
    history_days: int
    country_trends: dict[str, CountryTrend]  # keyed by iso_alpha3
    new_countries: list[str]  # iso_alpha3 codes
    gone_countries: list[str]


# ---------------------------------------------------------------------------
# Snapshot I/O
# ---------------------------------------------------------------------------

_DELTA_THRESHOLD = 0.5  # minimum absolute change to count as up/down


def save_snapshot(
    results: list[CountryRiskResult],
    history_dir: Path,
    scoring_method: str,
    snapshot_date: date | None = None,
) -> Path:
    """Save today's snapshot to *history_dir*/*date*.json.

    Idempotent: overwrites if a file for the same date already exists.
    """
    if snapshot_date is None:
        snapshot_date = datetime.now(tz=timezone.utc).date()

    history_dir.mkdir(parents=True, exist_ok=True)

    snapshot = DailySnapshot(
        date=snapshot_date.isoformat(),
        scoring_method=scoring_method,
        countries=[
            CountrySnapshot(
                iso_alpha3=r.iso_alpha3,
                country=r.country,
                score=round(r.seismic_hub_risk_score, 2),
                earthquake_count=r.earthquake_count,
                exposed_airport_count=len(r.exposed_airports),
                avg_magnitude=round(r.avg_magnitude, 2),
            )
            for r in results
        ],
    )

    path = history_dir / f"{snapshot_date.isoformat()}.json"
    path.write_text(json.dumps(asdict(snapshot), indent=2), encoding="utf-8")
    return path


def load_history(
    history_dir: Path,
    max_days: int = 90,
) -> list[DailySnapshot]:
    """Load snapshots from *history_dir*, sorted oldest-first.

    Returns at most *max_days* most-recent snapshots.
    Returns ``[]`` if the directory does not exist or contains no valid files.
    """
    if not history_dir.is_dir():
        return []

    files = sorted(history_dir.glob("*.json"))
    files = files[-max_days:]  # keep most recent

    snapshots: list[DailySnapshot] = []
    for f in files:
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
            countries = [
                CountrySnapshot(**c) for c in raw["countries"]
            ]
            snapshots.append(
                DailySnapshot(
                    date=raw["date"],
                    scoring_method=raw["scoring_method"],
                    countries=countries,
                )
            )
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Skipping invalid snapshot %s: %s", f.name, exc)
            continue

    return snapshots


# ---------------------------------------------------------------------------
# Trend computation
# ---------------------------------------------------------------------------


def compute_trends(
    history: list[DailySnapshot],
    current_results: list[CountryRiskResult],
    scoring_method: str,
) -> TrendSummary | None:
    """Compute trend data from historical snapshots and today's results.

    Returns ``None`` if *history* is empty (first run ever).
    """
    if not history:
        return None

    # Build per-country score trajectory from history
    # {iso_alpha3: [(date, score), ...]}
    trajectories: dict[str, list[tuple[str, float]]] = {}
    for snap in history:
        for cs in snap.countries:
            trajectories.setdefault(cs.iso_alpha3, []).append((snap.date, cs.score))

    # Previous snapshot = most recent in history
    previous_map: dict[str, CountrySnapshot] = {}
    previous_snap = history[-1]
    for cs in previous_snap.countries:
        previous_map[cs.iso_alpha3] = cs

    today = datetime.now(tz=timezone.utc).date().isoformat()
    current_map = {r.iso_alpha3: r for r in current_results}

    country_trends: dict[str, CountryTrend] = {}

    # Trends for countries in current results
    for r in current_results:
        iso3 = r.iso_alpha3
        current_score = round(r.seismic_hub_risk_score, 2)
        prev = previous_map.get(iso3)

        # Build score/date lists from trajectory + today
        traj = trajectories.get(iso3, [])
        dates = [t[0] for t in traj] + [today]
        scores = [t[1] for t in traj] + [current_score]

        previous_score = prev.score if prev else None
        delta = current_score - previous_score if previous_score is not None else 0.0

        if prev is None:
            direction = "new"
        elif delta > _DELTA_THRESHOLD:
            direction = "up"
        elif delta < -_DELTA_THRESHOLD:
            direction = "down"
        else:
            direction = "stable"

        country_trends[iso3] = CountryTrend(
            iso_alpha3=iso3,
            country=r.country,
            scores=scores,
            dates=dates,
            current_score=current_score,
            previous_score=previous_score,
            score_delta=round(delta, 2),
            trend_direction=direction,
            is_new=prev is None,
            is_gone=False,
            days_tracked=len(scores),
        )

    # Trends for countries that disappeared (in previous but not in current)
    gone_countries: list[str] = []
    for iso3, prev_cs in previous_map.items():
        if iso3 not in current_map:
            traj = trajectories.get(iso3, [])
            dates = [t[0] for t in traj]
            scores = [t[1] for t in traj]

            country_trends[iso3] = CountryTrend(
                iso_alpha3=iso3,
                country=prev_cs.country,
                scores=scores,
                dates=dates,
                current_score=0.0,
                previous_score=prev_cs.score,
                score_delta=round(-prev_cs.score, 2),
                trend_direction="gone",
                is_new=False,
                is_gone=True,
                days_tracked=len(scores),
            )
            gone_countries.append(iso3)

    new_countries = [
        iso3 for iso3, ct in country_trends.items()
        if ct.is_new
    ]

    return TrendSummary(
        date=today,
        history_days=len(history),
        country_trends=country_trends,
        new_countries=new_countries,
        gone_countries=gone_countries,
    )
