"""Data models for the seismic risk pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Earthquake:
    """A single earthquake event from USGS."""

    id: str
    magnitude: float
    latitude: float
    longitude: float
    depth_km: float
    time_ms: int
    place: str
    country_code: str = ""
    shakemap_available: bool = False


@dataclass(frozen=True)
class SignificantEvent:
    """Metadata for a significant earthquake from the USGS feed."""

    id: str
    alert: str | None
    felt: int
    tsunami: bool
    significance: int
    title: str


@dataclass(frozen=True)
class Airport:
    """An airport from OurAirports."""

    name: str
    iata_code: str
    latitude: float
    longitude: float
    municipality: str
    iso_country: str
    airport_type: str


@dataclass(frozen=True)
class NearbyQuake:
    """An earthquake near a specific airport — captures the pair relationship."""

    earthquake_id: str
    magnitude: float
    latitude: float
    longitude: float
    depth_km: float
    time_ms: int
    place: str
    distance_km: float
    exposure_contribution: float
    pga_g: float | None = None
    mmi: float | None = None


@dataclass
class ExposedAirport:
    """An airport within the exposure radius of at least one earthquake."""

    name: str
    iata_code: str
    latitude: float
    longitude: float
    municipality: str
    closest_quake_distance_km: float
    nearby_quakes: list[NearbyQuake] = field(default_factory=list)
    exposure_score: float = 0.0


@dataclass
class StrongestEarthquake:
    """Summary of the strongest earthquake for a country."""

    magnitude: float
    date: str
    depth_km: float
    latitude: float
    longitude: float


@dataclass
class CountryRiskResult:
    """Complete risk assessment result for a single country."""

    country: str
    iso_alpha2: str
    iso_alpha3: str
    capital: str
    population: int
    area_km2: float
    region: str
    subregion: str
    currencies: list[dict[str, str]] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    un_member: bool = False
    bordering_countries: list[str] = field(default_factory=list)
    earthquake_count: int = 0
    avg_magnitude: float = 0.0
    strongest_earthquake: StrongestEarthquake | None = None
    highest_pager_alert: str | None = None
    max_felt_reports: int = 0
    tsunami_warning_issued: bool = False
    significant_events_count: int = 0
    exposed_airports: list[ExposedAirport] = field(default_factory=list)
    earthquakes: list[Earthquake] = field(default_factory=list)
    seismic_hub_risk_score: float = 0.0
