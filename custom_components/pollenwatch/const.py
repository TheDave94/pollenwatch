"""Constants for the PollenWatch integration.

Intentionally free of ``homeassistant`` imports so importing the package does
not pull in Home Assistant — this keeps the source layer under ``sources/``
testable in isolation (the package ``__init__`` imports only this module).
"""

from __future__ import annotations

from typing import Final

from .sources.base import ALLERGENS

DOMAIN: Final = "pollenwatch"

# Platforms set up per config entry. Kept as a plain string to avoid importing
# homeassistant.const here; __init__ maps it onto the Platform enum.
PLATFORMS: Final[list[str]] = ["sensor"]

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
}
SOURCE_DEVICE_MODELS: Final[dict[str, str]] = {
    SOURCE_OPEN_METEO: "CAMS via Open-Meteo",
}
SOURCE_CONFIG_URLS: Final[dict[str, str]] = {
    SOURCE_OPEN_METEO: "https://open-meteo.com/",
}
SOURCE_ATTRIBUTIONS: Final[dict[str, str]] = {
    SOURCE_OPEN_METEO: ATTRIBUTION_CAMS,
}

# Config-entry / options keys. Location uses homeassistant.const
# CONF_LATITUDE / CONF_LONGITUDE; these are PollenWatch-specific.
CONF_ALLERGENS: Final = "allergens"
CONF_UPDATE_INTERVAL: Final = "update_interval"  # minutes

# Defaults and guardrails.
DEFAULT_ALLERGENS: Final[list[str]] = list(ALLERGENS)
DEFAULT_UPDATE_INTERVAL_MIN: Final = 60
# A free, keyless public API — never poll faster than hourly (see kickoff probe).
MIN_UPDATE_INTERVAL_MIN: Final = 60
MAX_UPDATE_INTERVAL_MIN: Final = 24 * 60

# Open-Meteo fetch window. Milestone 2 needs no history (the recent-percentile
# feature lands in milestone 3), so we request no past days and keep payloads
# small. forecast_days=5 gives a best-effort 5th day; we expose 4 daily peaks.
OPEN_METEO_PAST_DAYS: Final = 0
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
