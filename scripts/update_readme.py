#!/usr/bin/env python3
"""Inject latest results into README.md between marker comments.

Reads output/latest.json and builds a top-10 country table, then replaces
the content between <!-- LATEST_RESULTS_START --> and <!-- LATEST_RESULTS_END -->
markers in README.md.

If output/history/ contains at least 2 snapshots, a "Trend" column is added
showing score deltas vs the previous day.

This script is standalone — it uses only stdlib and does not import seismic_risk.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

START_MARKER = "<!-- LATEST_RESULTS_START -->"
END_MARKER = "<!-- LATEST_RESULTS_END -->"

ROOT = Path(__file__).resolve().parent.parent
README_PATH = ROOT / "README.md"
JSON_PATH = ROOT / "output" / "latest.json"
HISTORY_DIR = ROOT / "output" / "history"

_DELTA_THRESHOLD = 0.5


def _load_previous_scores() -> dict[str, float] | None:
    """Load score map from the second-most-recent snapshot.

    Returns None if fewer than 2 snapshots exist.
    """
    if not HISTORY_DIR.is_dir():
        return None
    files = sorted(HISTORY_DIR.glob("*.json"))
    if len(files) < 2:
        return None
    with open(files[-2], encoding="utf-8") as f:
        snapshot = json.load(f)
    return {c["iso_alpha3"]: c["score"] for c in snapshot["countries"]}


def _trend_indicator(iso3: str, score: float, previous: dict[str, float] | None) -> str:
    """Return a trend string for a single country."""
    if previous is None:
        return ""
    if iso3 not in previous:
        return "NEW"
    delta = score - previous[iso3]
    if delta > _DELTA_THRESHOLD:
        return f"+{delta:.1f}"
    if delta < -_DELTA_THRESHOLD:
        return f"{delta:.1f}"
    return "~"


def build_table(data: list[dict]) -> str:
    """Build a Markdown table from the top 10 countries by risk score."""
    previous = _load_previous_scores()
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"*Last updated: {timestamp}*",
        "",
        "| # | Country | ISO | Score | Trend | Quakes | Airports | Alert |",
        "|--:|:--------|:----|------:|:------|-------:|---------:|:------|",
    ]

    sorted_data = sorted(
        data,
        key=lambda r: r.get("seismic_hub_risk_score", 0),
        reverse=True,
    )

    for i, r in enumerate(sorted_data[:10], 1):
        score = r["seismic_hub_risk_score"]
        trend = _trend_indicator(r["iso_alpha3"], score, previous)
        lines.append(
            f"| {i} | {r['country']} | {r['iso_alpha3']}"
            f" | {score:.1f}"
            f" | {trend}"
            f" | {r['earthquake_count']}"
            f" | {len(r.get('exposed_airports', []))}"
            f" | {r.get('highest_pager_alert') or '-'} |"
        )

    return "\n".join(lines)


def main() -> None:
    if not JSON_PATH.exists():
        print(f"No results file at {JSON_PATH}, skipping README update.")
        sys.exit(0)

    readme_text = README_PATH.read_text(encoding="utf-8")

    if START_MARKER not in readme_text or END_MARKER not in readme_text:
        print("README markers not found, skipping injection.")
        sys.exit(0)

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    table = build_table(data)

    start_idx = readme_text.index(START_MARKER) + len(START_MARKER)
    end_idx = readme_text.index(END_MARKER)

    updated = readme_text[:start_idx] + "\n" + table + "\n" + readme_text[end_idx:]
    README_PATH.write_text(updated, encoding="utf-8")
    print(f"README updated with {len(data)} countries.")


if __name__ == "__main__":
    main()
