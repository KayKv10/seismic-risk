"""OurAirports data fetcher."""

from __future__ import annotations

import pandas as pd

from seismic_risk.models import Airport

OURAIRPORTS_CSV_URL = (
    "https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/airports.csv"
)


def fetch_airports(
    airport_type: str = "large_airport",
    country_codes: set[str] | None = None,
    url: str = OURAIRPORTS_CSV_URL,
) -> list[Airport]:
    """Download OurAirports CSV and return airports matching the given criteria."""
    df = pd.read_csv(url)
    filtered = df[df["type"] == airport_type].copy()

    if country_codes is not None:
        filtered = filtered[filtered["iso_country"].isin(country_codes)]

    airports: list[Airport] = []
    for _, row in filtered.iterrows():
        iata = (
            str(row["iata_code"])
            if pd.notna(row["iata_code"]) and row["iata_code"] != ""
            else "N/A"
        )
        municipality = str(row["municipality"]) if pd.notna(row["municipality"]) else ""
        airports.append(
            Airport(
                name=str(row["name"]),
                iata_code=iata,
                latitude=float(row["latitude_deg"]),
                longitude=float(row["longitude_deg"]),
                municipality=municipality,
                iso_country=str(row["iso_country"]),
                airport_type=airport_type,
            )
        )
    return airports
