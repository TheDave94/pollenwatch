"""Data update coordinators for PollenWatch.

Per-source ``DataUpdateCoordinator`` pattern (HA 2026.5): one coordinator per
data source, collected in a small runtime-data container on the config entry.
The meta-coordinator that fans these into cross-source analytics arrives in
milestone 3b.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ALLERGENS,
    CONF_API_KEY,
    CONF_COUNTRY,
    CONF_ENABLED,
    CONF_SOURCES,
    CONF_UPDATE_INTERVAL,
    DEFAULT_ALLERGENS,
    DEFAULT_UPDATE_INTERVAL_MIN,
    DOMAIN,
    OPEN_METEO_FORECAST_DAYS,
    OPEN_METEO_PAST_DAYS,
    PI_UPDATE_INTERVAL_MIN,
    SOURCE_OPEN_METEO,
    SOURCE_POLLENINFORMATION,
)
from .sources.base import PollenSource, SourceError, SourceResult
from .sources.open_meteo import OpenMeteoSource
from .sources.polleninformation import PolleninformationSource

_LOGGER = logging.getLogger(__name__)


@dataclass
class PollenWatchData:
    """Runtime data stored on the config entry: per-source coordinators."""

    coordinators: dict[str, PollenWatchSourceCoordinator] = field(
        default_factory=dict
    )


type PollenWatchConfigEntry = ConfigEntry[PollenWatchData]


def _entry_option(entry: ConfigEntry, key: str, default: Any) -> Any:
    """Read a value preferring options (user-editable) over initial data."""
    if key in entry.options:
        return entry.options[key]
    return entry.data.get(key, default)


class PollenWatchSourceCoordinator(DataUpdateCoordinator[SourceResult]):
    """Fetches one pollen source on an interval; source-agnostic."""

    config_entry: PollenWatchConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PollenWatchConfigEntry,
        source: PollenSource,
        source_key: str,
        update_interval_min: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{source_key}",
            config_entry=entry,
            update_interval=timedelta(minutes=update_interval_min),
        )
        self.source = source
        self.source_key = source_key

    async def _async_update_data(self) -> SourceResult:
        session = async_get_clientsession(self.hass)
        try:
            result = await self.source.async_fetch(session=session)
        except SourceError as err:
            raise UpdateFailed(str(err)) from err
        if not result.ok:
            # The location is coverage-checked at setup; a non-OK result now
            # means a transient upstream issue rather than a misconfiguration.
            raise UpdateFailed(
                result.message
                or f"{self.source_key} returned no usable pollen data."
            )
        return result


def build_coordinators(
    hass: HomeAssistant, entry: PollenWatchConfigEntry
) -> dict[str, PollenWatchSourceCoordinator]:
    """Construct the per-source coordinators enabled for this entry.

    Open-Meteo is always built; polleninformation is built only when enabled
    with an API key + country. The global allergen selection is passed to every
    source, which maps it onto its own capabilities.
    """
    interval = _entry_option(entry, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MIN)
    allergens = _entry_option(entry, CONF_ALLERGENS, DEFAULT_ALLERGENS)
    latitude = entry.data[CONF_LATITUDE]
    longitude = entry.data[CONF_LONGITUDE]
    sources_cfg = _entry_option(entry, CONF_SOURCES, {})

    open_meteo = OpenMeteoSource(
        latitude,
        longitude,
        allergens,
        past_days=OPEN_METEO_PAST_DAYS,
        forecast_days=OPEN_METEO_FORECAST_DAYS,
    )
    coordinators: dict[str, PollenWatchSourceCoordinator] = {
        SOURCE_OPEN_METEO: PollenWatchSourceCoordinator(
            hass, entry, open_meteo, SOURCE_OPEN_METEO, interval
        )
    }

    pi_cfg = sources_cfg.get(SOURCE_POLLENINFORMATION, {})
    if pi_cfg.get(CONF_ENABLED) and pi_cfg.get(CONF_API_KEY) and pi_cfg.get(CONF_COUNTRY):
        polleninformation = PolleninformationSource(
            latitude,
            longitude,
            pi_cfg[CONF_COUNTRY],
            pi_cfg[CONF_API_KEY],
            allergens,
        )
        coordinators[SOURCE_POLLENINFORMATION] = PollenWatchSourceCoordinator(
            hass,
            entry,
            polleninformation,
            SOURCE_POLLENINFORMATION,
            PI_UPDATE_INTERVAL_MIN,
        )

    return coordinators
