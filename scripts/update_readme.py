#!/usr/bin/env python3
"""Inject latest results into README.md between marker comments.

Reads output/latest.json and builds a top-10 country table, then replaces
the content between <!-- LATEST_RESULTS_START --> and <!-- LATEST_RESULTS_END -->
markers in README.md.

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


def build_table(data: list[dict]) -> str:
    """Build a Markdown table from the top 10 countries by risk score."""
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"*Last updated: {timestamp}*",
        "",
        "| # | Country | ISO | Score | Quakes | Airports | Alert |",
        "|--:|:--------|:----|------:|-------:|---------:|:------|",
    ]

    sorted_data = sorted(
        data,
        key=lambda r: r.get("seismic_hub_risk_score", 0),
        reverse=True,
    )

    for i, r in enumerate(sorted_data[:10], 1):
        lines.append(
            f"| {i} | {r['country']} | {r['iso_alpha3']}"
            f" | {r['seismic_hub_risk_score']:.1f}"
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
