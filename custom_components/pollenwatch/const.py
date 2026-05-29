"""Constants for the PollenWatch integration.

Intentionally free of ``homeassistant`` imports so importing the package does
not pull in Home Assistant — this keeps the source layer under ``sources/``
testable in isolation (the package ``__init__`` imports only this module).
"""

from __future__ import annotations

from typing import Final

from .sources.base import ALLERGENS

DOMAIN: Final = "pollenwatch"

# Platforms set up per config entry. Kept as plain strings to avoid importing
# homeassistant.const here; __init__ maps them onto the Platform enum.
PLATFORMS: Final[list[str]] = ["sensor", "binary_sensor"]

# Device holding the cross-source analytics entities (consensus, divergence).
ANALYTICS_DEVICE_NAME: Final = "PollenWatch Analytics"

# Attribution text required by the data providers. See README.
ATTRIBUTION_CAMS: Final = (
    "Generated using Copernicus Atmosphere Monitoring Service information. "
    "Pollen data via Open-Meteo.com."
)

# Open-Meteo source identity (used for the device).
SOURCE_OPEN_METEO: Final = "open_meteo"
SOURCE_OPEN_METEO_NAME: Final = "Open-Meteo (CAMS)"

# Per-source device presentation, keyed by source slug. The device NAME slugs to
# the entity-ID prefix (sensor.pollenwatch_<source>_<allergen>); these strings
# are load-bearing for existing entities and must stay stable.
SOURCE_DEVICE_NAMES: Final[dict[str, str]] = {
    SOURCE_OPEN_METEO: "PollenWatch Open-Meteo",
    "polleninformation": "PollenWatch Polleninformation",
    "dwd": "PollenWatch DWD",
    "meteoswiss": "PollenWatch MeteoSwiss",
    "epin": "PollenWatch ePIN",
}
SOURCE_DEVICE_MODELS: Final[dict[str, str]] = {
    SOURCE_OPEN_METEO: "CAMS via Open-Meteo",
    "polleninformation": "polleninformation.at",
    "dwd": "DWD Pollenflug-Gefahrenindex",
    "meteoswiss": "MeteoSwiss automatic pollen network",
    "epin": "ePIN Bayern (automatic stations)",
}
SOURCE_CONFIG_URLS: Final[dict[str, str]] = {
    SOURCE_OPEN_METEO: "https://open-meteo.com/",
    "polleninformation": "https://www.polleninformation.at/",
    "dwd": "https://www.dwd.de/pollenflug",
    "meteoswiss": "https://www.meteoswiss.admin.ch/services-and-publications/service/open-data.html",
    "epin": "https://www.pollenflug.bayern.de/",
}
SOURCE_ATTRIBUTIONS: Final[dict[str, str]] = {
    SOURCE_OPEN_METEO: ATTRIBUTION_CAMS,
    "polleninformation": "© Polleninformation Austria",
    "dwd": "© Deutscher Wetterdienst (DWD)",
    # MeteoSwiss open-data attribution (their requested form).
    "meteoswiss": "Source: MeteoSwiss",
    # ePIN data may be used freely in any medium; we cite the data owner (LGL).
    "epin": "Source: ePIN, Bayerisches Landesamt für Gesundheit und Lebensmittelsicherheit (LGL)",
}

# Config-entry / options keys. Location uses homeassistant.const
# CONF_LATITUDE / CONF_LONGITUDE; these are PollenWatch-specific.
CONF_ALLERGENS: Final = "allergens"
CONF_UPDATE_INTERVAL: Final = "update_interval"  # minutes

# Personal sensitivity multipliers (per species), applied to raw values to give
# a personal_score. Stored in options under CONF_SENSITIVITY as {species: float}.
CONF_SENSITIVITY: Final = "sensitivity"
DEFAULT_SENSITIVITY: Final = 1.0
MIN_SENSITIVITY: Final = 0.0
MAX_SENSITIVITY: Final = 2.0

# Multi-source enablement (config-entry version 2). Stored in options under
# CONF_SOURCES as {source_key: {enabled: bool, api_key?: str}}.
CONF_SOURCES: Final = "sources"
CONF_ENABLED: Final = "enabled"
CONF_API_KEY: Final = "api_key"  # local copy to keep const free of HA imports
CONF_COUNTRY: Final = "country"
CONF_REGION: Final = "region"  # DWD partregion_id
CONF_STATION: Final = "station"  # MeteoSwiss / ePIN resolved nearest-station code

# Second source (added in milestone 3a; disabled until a key is supplied).
SOURCE_POLLENINFORMATION: Final = "polleninformation"
SOURCE_POLLENINFORMATION_NAME: Final = "Polleninformation"

# Third source (added in the DWD milestone; Germany only, keyless, off by default).
SOURCE_DWD: Final = "dwd"

# Station-picker sources (v1.1 milestone; keyless, grains/m³, off by default).
# Both auto-pick the nearest measuring station to the configured location.
SOURCE_METEOSWISS: Final = "meteoswiss"  # Switzerland; MeteoSwiss OGD pollen
SOURCE_EPIN: Final = "epin"  # Bavaria; ePIN (LGL)

# polleninformation publishes a daily index (cadence ~8–24 h), so polling it
# hourly would waste a free public API. Use a fixed, slower interval.
PI_UPDATE_INTERVAL_MIN: Final = 6 * 60
# DWD updates once daily (~11:00) — poll slowly.
DWD_UPDATE_INTERVAL_MIN: Final = 12 * 60
# MeteoSwiss re-publishes hourly but each poll re-downloads the year's recent
# CSV; ePIN is 3-hourly. Poll both every 3 h — fresh enough, easy on free feeds.
METEOSWISS_UPDATE_INTERVAL_MIN: Final = 3 * 60
EPIN_UPDATE_INTERVAL_MIN: Final = 3 * 60

# DWD partregion_id -> display name (captured from the s31fg.json feed; factual,
# stable — bundled so the config flow needs no network call). id -1 is the
# Brandenburg+Berlin region, which has no sub-region (not a no-data marker).
DWD_PARTREGIONS: Final[dict[int, str]] = {
    -1: "Brandenburg und Berlin",
    11: "Schleswig-Holstein und Hamburg – Inseln und Marschen",
    12: "Schleswig-Holstein und Hamburg – Geest",
    31: "Niedersachsen und Bremen – Westl. Niedersachsen/Bremen",
    32: "Niedersachsen und Bremen – Östl. Niedersachsen",
    41: "Nordrhein-Westfalen – Rhein.-Westfäl. Tiefland",
    42: "Nordrhein-Westfalen – Ostwestfalen",
    43: "Nordrhein-Westfalen – Mittelgebirge NRW",
    61: "Sachsen-Anhalt – Tiefland",
    62: "Sachsen-Anhalt – Harz",
    71: "Thüringen – Tiefland",
    72: "Thüringen – Mittelgebirge",
    81: "Sachsen – Tiefland",
    82: "Sachsen – Mittelgebirge",
    91: "Hessen – Nordhessen und Mittelgebirge",
    92: "Hessen – Rhein-Main",
    101: "Rheinland-Pfalz und Saarland – Rhein, Pfalz, Nahe und Mosel",
    102: "Rheinland-Pfalz und Saarland – Mittelgebirge",
    103: "Rheinland-Pfalz und Saarland – Saarland",
    111: "Baden-Württemberg – Oberrhein und unteres Neckartal",
    112: "Baden-Württemberg – Hohenlohe/mittlerer Neckar/Oberschwaben",
    113: "Baden-Württemberg – Mittelgebirge",
    121: "Bayern – Allgäu/Oberbayern/Bayerischer Wald",
    122: "Bayern – Donauniederungen",
    123: "Bayern – Bayern nördlich der Donau",
    124: "Bayern – Mainfranken",
}


def new_sources_config() -> dict[str, dict[str, object]]:
    """Default per-source enablement for a new or migrated entry.

    Open-Meteo is always on (keyless, primary); polleninformation is off until
    the user enables it and supplies an API key + country.
    """
    return {
        SOURCE_OPEN_METEO: {CONF_ENABLED: True},
        SOURCE_POLLENINFORMATION: {
            CONF_ENABLED: False,
            CONF_API_KEY: "",
            CONF_COUNTRY: "",
        },
        SOURCE_DWD: {CONF_ENABLED: False, CONF_REGION: ""},
        SOURCE_METEOSWISS: {CONF_ENABLED: False, CONF_STATION: ""},
        SOURCE_EPIN: {CONF_ENABLED: False, CONF_STATION: ""},
    }

# Defaults and guardrails.
DEFAULT_ALLERGENS: Final[list[str]] = list(ALLERGENS)
DEFAULT_UPDATE_INTERVAL_MIN: Final = 60
# A free, keyless public API — never poll faster than hourly (see kickoff probe).
MIN_UPDATE_INTERVAL_MIN: Final = 60
MAX_UPDATE_INTERVAL_MIN: Final = 24 * 60

# Open-Meteo fetch window. Milestone 3b's recent_percentile baselines today
# against the trailing ~92 days, so we request the full backfill (probe-confirmed
# available). forecast_days=5 gives a best-effort 5th day; we expose 4 daily peaks.
# (Re-fetching 92 past days hourly is wasteful — see REVIEW_QUEUE.)
OPEN_METEO_PAST_DAYS: Final = 92
OPEN_METEO_FORECAST_DAYS: Final = 5
FORECAST_DAYS: Final = 4

# Human-readable allergen names (UI translations override these; used as a
# fallback and for entity naming).
ALLERGEN_NAMES: Final[dict[str, str]] = {
    "alder": "Alder",
    "birch": "Birch",
    "grass": "Grass",
    "mugwort": "Mugwort",
    "olive": "Olive",
    "ragweed": "Ragweed",
}

# Extra-state-attribute keys exposed by sensors.
ATTR_FORECAST: Final = "forecast"
ATTR_REQUESTED_LAT: Final = "requested_latitude"
ATTR_REQUESTED_LON: Final = "requested_longitude"
ATTR_SNAPPED_LAT: Final = "snapped_latitude"
ATTR_SNAPPED_LON: Final = "snapped_longitude"
ATTR_GRID_SHIFT_KM: Final = "grid_shift_km"
ATTR_LAST_UPDATED: Final = "source_last_updated"
ATTR_MULTIPLIER: Final = "multiplier"
