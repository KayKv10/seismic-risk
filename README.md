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
uv sync --all-extras   # or: pip install -e ".[dev,api]"
```

### CLI Usage

```bash
# Run with defaults (M5.0+, 30 days, 200km radius)
seismic-risk run

# Custom parameters
seismic-risk run \
  --min-magnitude 4.0 \
  --days 14 \
  --distance 300 \
  -o results.json

# Export interactive HTML map with trend sparklines
seismic-risk run --format html --history-dir output/history -o dashboard.html

# Export CSV for spreadsheets
seismic-risk run --format csv -o results.csv

# Verbose output
seismic-risk run -v
```

### REST API

Install with the `api` extra, then start the server:

```bash
pip install "seismic-risk[api]"
uvicorn seismic_risk.api:app --reload
```

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Server status, uptime, version, run count |
| `GET /risk` | Run pipeline (JSON by default) |
| `GET /risk?format=html` | Interactive Leaflet map |
| `GET /risk?format=csv` | CSV export |
| `GET /docs` | OpenAPI interactive docs |

```bash
# Fetch current risk scores
curl "http://localhost:8000/risk"

# Custom parameters
curl "http://localhost:8000/risk?min_magnitude=4.0&days=14&format=csv"
```

## Latest Results

*Updated daily by [GitHub Actions](https://github.com/KayKv10/seismic-risk/actions/workflows/daily-report.yml). View the [interactive map](https://kaykv10.github.io/seismic-risk/latest.html).*

<!-- LATEST_RESULTS_START -->
*Last updated: 2026-02-21 06:32 UTC*

| # | Country | ISO | Score | Trend | Quakes | Airports | Alert |
|--:|:--------|:----|------:|:------|-------:|---------:|:------|
| 1 | Philippines | PHL | 15.1 | -1.2 | 18 | 5 | - |
| 2 | Japan | JPN | 8.2 | +2.3 | 10 | 8 | - |
| 3 | Tonga | TON | 7.0 | ~ | 18 | 1 | - |
| 4 | Indonesia | IDN | 6.0 | ~ | 16 | 4 | - |
| 5 | Russia | RUS | 3.8 | ~ | 19 | 1 | - |
| 6 | Papua New Guinea | PNG | 0.8 | ~ | 5 | 1 | - |
| 7 | Chile | CHL | 0.2 | ~ | 9 | 1 | green |
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

### Risk Score Formula

The tool supports three scoring methods (`--scorer`):

**ShakeMap (default)** — Uses real USGS ShakeMap ground-motion data when available. Downloads ShakeMap grid.xml files for significant earthquakes and performs bilinear interpolation of Peak Ground Acceleration (PGA) at each airport's coordinates. Falls back to a GMPE-calibrated heuristic (Atkinson & Wald 2007 IPE) for earthquakes without ShakeMap data.

**Heuristic** (`--scorer heuristic`) — Distance-weighted exposure without ShakeMap:
```
exposure = sum( 10^(0.5 * magnitude) / (distance_km + 1) )
```

**Legacy** (`--scorer legacy`) — Simple ratio:
```
score = (earthquake_count x avg_magnitude) / exposed_airport_count
```

The country score is the sum of all airport exposure scores. Higher scores indicate more seismically exposed aviation infrastructure.

## Configuration

All parameters can be set via CLI flags or environment variables:

| Parameter | CLI Flag | Env Variable | Default |
|-----------|----------|-------------|---------|
| Min magnitude | `--min-magnitude` | `SEISMIC_RISK_MIN_MAGNITUDE` | 5.0 |
| Lookback days | `--days` | `SEISMIC_RISK_DAYS_LOOKBACK` | 30 |
| Min quakes/country | `--min-quakes` | `SEISMIC_RISK_MIN_QUAKES_PER_COUNTRY` | 3 |
| Exposure radius (km) | `--distance` | `SEISMIC_RISK_MAX_AIRPORT_DISTANCE_KM` | 200.0 |
| Airport type | `--airport-type` | `SEISMIC_RISK_AIRPORT_TYPE` | large_airport |
| Scoring method | `--scorer` | `SEISMIC_RISK_SCORING_METHOD` | shakemap |
| Output format | `--format` | `SEISMIC_RISK_OUTPUT_FORMAT` | json |
| History dir | `--history-dir` | — | *(disabled)* |
| Disable cache | `--no-cache` | `SEISMIC_RISK_CACHE_ENABLED` | false |

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

## Trend Tracking

The `output/history/` directory contains monthly snapshots back to January 2020 and daily snapshots going forward, updated automatically by the [daily report workflow](https://github.com/KayKv10/seismic-risk/actions/workflows/daily-report.yml). The HTML map shows SVG sparkline charts for each country's risk score history, and per-airport exposure sparklines in airport popups.

```bash
# Run with trend sparklines
seismic-risk run --format html --history-dir output/history -o dashboard.html
```

### Historical Backfill

The history was bootstrapped by querying the USGS FDSN API month-by-month from January 2020 to the present:

```bash
uv run python scripts/backfill.py --history-dir output/history
```

**Caveats:**
- **Historical snapshots (2020–present) use heuristic scoring only.** ShakeMap ground-motion data is only available for the most recent 30 days via the USGS significant-earthquakes feed, so PGA-based scoring cannot be applied retroactively. Daily snapshots from February 2026 onward use the default ShakeMap scorer.
- **Airport data reflects current OurAirports state**, not historical operational dates. Large airports are mostly stable post-2015, but early snapshots may include airports that were not yet operational.
- **Monthly vs daily granularity.** Historical snapshots are one per month (dated to the last day of each month). Live snapshots are one per day. The sparkline charts display both seamlessly.

## Project Structure

```
src/seismic_risk/
├── api.py           # FastAPI REST API (optional [api] extra)
├── cli.py           # Typer CLI interface
├── config.py        # Pydantic settings & type definitions
├── models.py        # Data models (frozen dataclasses)
├── pipeline.py      # Pipeline orchestrator
├── geo.py           # Haversine distance, reverse geocoding, felt radius
├── scoring.py       # Risk score calculation, airport exposure
├── history.py       # Daily snapshot storage, per-airport exposure tracking & trends
├── http.py          # Shared requests.Session with retry/backoff
├── cache.py         # File-based disk cache with TTL
├── fetchers/        # Data fetchers (USGS, ShakeMap, airports, countries)
├── data/            # Static data (airport movements)
└── exporters/       # Output formatters (JSON, GeoJSON, HTML, CSV, Markdown)

scripts/
├── backfill.py         # Historical backfill (2020–present)
└── update_readme.py    # Auto-update Latest Results table

examples/
└── notebook_demo.ipynb # Jupyter notebook with folium visualization
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
# Install all dependencies
uv sync --all-extras

# Run tests (235 tests)
uv run pytest

# Lint & type check
uv run ruff check src/ tests/
uv run mypy src/

# Run with coverage
uv run pytest --cov=seismic_risk
```

## License

MIT
