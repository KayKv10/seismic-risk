"""JSON exporter for seismic risk results."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from seismic_risk.models import CountryRiskResult


def export_json(
    results: list[CountryRiskResult],
    output_path: Path,
    indent: int = 2,
) -> Path:
    """Export risk results to a JSON file."""
    data = [asdict(r) for r in results]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
    return output_path
