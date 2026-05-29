"""Constants for the PollenWatch integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "pollenwatch"

# Attribution text required by the data providers. See README.
ATTRIBUTION_CAMS: Final = (
    "Generated using Copernicus Atmosphere Monitoring Service information. "
    "Pollen data via Open-Meteo.com."
)

# Canonical allergen keys supported across the integration. Individual sources
# expose a subset of these; the analytics layer reconciles them by this key.
ALLERGEN_ALDER: Final = "alder"
ALLERGEN_BIRCH: Final = "birch"
ALLERGEN_GRASS: Final = "grass"
ALLERGEN_MUGWORT: Final = "mugwort"
ALLERGEN_OLIVE: Final = "olive"
ALLERGEN_RAGWEED: Final = "ragweed"
