# seismic-risk

[![CI](https://github.com/KayKv10/seismic-risk/actions/workflows/ci.yml/badge.svg)](https://github.com/KayKv10/seismic-risk/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/seismic-risk)](https://pypi.org/project/seismic-risk/)
[![Python versions](https://img.shields.io/pypi/pyversions/seismic-risk)](https://pypi.org/project/seismic-risk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Real-time seismic risk scoring for global aviation infrastructure. Cross-references live USGS earthquake data with airport databases and country metadata to identify airports exposed to seismic hazards.

## Quick Start

### Install from PyPI

```bash
pip install seismic-risk
```

### Install from source

```bash
git clone https://github.com/KayKv10/seismic-risk.git
cd seismic-risk
pip install -e ".[dev]"
```

### Usage

```bash
# Run with defaults (M5.0+, 30 days, 200km radius)
seismic-risk run

# Custom parameters
seismic-risk run \
  --min-magnitude 4.0 \
  --days 14 \
  --distance 300 \
  -o results.json

# Export interactive HTML map
seismic-risk run --format html -o dashboard.html

# Export CSV for spreadsheets
seismic-risk run --format csv -o results.csv

# Verbose output
seismic-risk run -v

# Show version
seismic-risk --version
```

## Latest Results

*Updated daily by [GitHub Actions](https://github.com/KayKv10/seismic-risk/actions/workflows/daily-report.yml). View the [interactive map](https://kaykv10.github.io/seismic-risk/latest.html).*

<!-- LATEST_RESULTS_START -->
*Last updated: 2026-02-07 20:12 UTC*

| # | Country | ISO | Score | Trend | Quakes | Airports | Alert |
|--:|:--------|:----|------:|:------|-------:|---------:|:------|
| 1 | Philippines | PHL | 76.4 |  | 16 | 5 | - |
| 2 | Indonesia | IDN | 47.2 |  | 18 | 7 | green |
| 3 | Japan | JPN | 45.5 |  | 15 | 9 | - |
| 4 | Russia | RUS | 26.2 |  | 22 | 1 | - |
| 5 | Tonga | TON | 25.4 |  | 19 | 1 | - |
| 6 | Papua New Guinea | PNG | 9.3 |  | 5 | 1 | - |
| 7 | New Zealand | NZL | 1.9 |  | 3 | 1 | - |
<!-- LATEST_RESULTS_END -->

## How It Works

### Data Sources

| Source | Data | URL |
|--------|------|-----|
| USGS FDSN | Earthquake events | earthquake.usgs.gov |
| USGS Feeds | Significant earthquakes (PAGER alerts) | earthquake.usgs.gov |
| OurAirports | Airport locations & metadata | github.com/davidmegginson/ourairports-data |
| REST Countries | Country metadata | restcountries.com |

### Pipeline Steps

1. Fetch M5.0+ earthquakes from USGS (past 30 days)
2. Reverse-geocode epicenters to country codes
3. Filter countries with >= 3 qualifying earthquakes
4. Fetch significant earthquake metadata (PAGER alerts)
5. Download airport data, filter to large airports in qualifying countries
6. Fetch country metadata (population, region, currencies)
7. Compute Haversine distances between airports and earthquakes
8. Filter airports within 200km exposure radius
9. Calculate Seismic Hub Risk Score per country
10. Sort and export results

### Risk Score Formula (Default: Distance-Weighted Exposure)

The default scoring method sums the "threat" from each earthquake to each airport:

```
exposure = sum( 10^(0.5 * magnitude) / (distance_km + 1) )
```

This weights by:
- **Inverse distance**: closer earthquakes contribute more
- **Exponential magnitude**: a M6 quake contributes ~3.16x more than a M5 at the same distance

The country score is the total exposure across all airports.

**Legacy scoring** (use `--scorer legacy`):
```
score = (earthquake_count x avg_magnitude) / exposed_airport_count
```

> **Note**: Both are heuristic metrics for portfolio/educational purposes. They do not incorporate ground motion modeling, soil conditions, or structural vulnerability. See the project plan for discussion of limitations.

## Configuration

All parameters can be set via CLI flags or environment variables:

| Parameter | CLI Flag | Env Variable | Default |
|-----------|----------|-------------|---------|
| Min magnitude | `--min-magnitude` | `SEISMIC_RISK_MIN_MAGNITUDE` | 5.0 |
| Lookback days | `--days` | `SEISMIC_RISK_DAYS_LOOKBACK` | 30 |
| Min quakes/country | `--min-quakes` | `SEISMIC_RISK_MIN_QUAKES_PER_COUNTRY` | 3 |
| Exposure radius (km) | `--distance` | `SEISMIC_RISK_MAX_AIRPORT_DISTANCE_KM` | 200.0 |
| Airport type | `--airport-type` | `SEISMIC_RISK_AIRPORT_TYPE` | large_airport |
| Scoring method | `--scorer` | `SEISMIC_RISK_SCORING_METHOD` | exposure |
| Output format | `--format` | `SEISMIC_RISK_OUTPUT_FORMAT` | json |

## Output Formats

| Format | Extension | Use Case |
|--------|-----------|----------|
| `json` | `.json` | API consumers, programmatic access |
| `geojson` | `.geojson` | Import into QGIS, Mapbox, kepler.gl |
| `html` | `.html` | Standalone interactive map (Leaflet.js) |
| `csv` | `.csv` | Spreadsheets, Excel, data analysis |
| `markdown` | `.md` | GitHub-friendly summary tables |

### Interactive HTML Map

```bash
seismic-risk run --format html -o dashboard.html
open dashboard.html  # Opens in browser
```

### GeoJSON for GIS Tools

```bash
seismic-risk run --format geojson -o risk_map.geojson
# Import into QGIS: Layer > Add Layer > Add Vector Layer
```

### Jupyter Notebook

For interactive exploration with folium, install Jupyter dependencies:

```bash
pip install -e ".[jupyter]"
jupyter notebook examples/notebook_demo.ipynb
```

## Project Structure

```
src/seismic_risk/
├── cli.py           # Typer CLI interface
├── config.py        # Pydantic settings
├── models.py        # Data models (dataclasses)
├── geo.py           # Haversine distance, reverse geocoding, felt radius
├── scoring.py       # Risk score calculation, airport exposure
├── pipeline.py      # Pipeline orchestrator
├── fetchers/        # Data fetchers (USGS, airports, countries)
├── data/            # Static data (airport movements)
└── exporters/       # Output formatters (JSON, GeoJSON, HTML, CSV, Markdown)

examples/
└── notebook_demo.ipynb  # Jupyter notebook with folium visualization
```

## Docker

```bash
# Build the image
docker build -t seismic-risk .

# Run with default settings
docker run seismic-risk

# Export HTML dashboard to host
docker run -v $(pwd)/output:/app/output seismic-risk run --format html -o /app/output/dashboard.html
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=seismic_risk

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## License

MIT
