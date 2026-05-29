"""Data update coordinator for PollenWatch.

Milestone 2 ships a single per-source coordinator (Open-Meteo / CAMS). The
meta-coordinator that fans these into cross-source analytics arrives in
milestone 3.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ALLERGENS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_ALLERGENS,
    DEFAULT_UPDATE_INTERVAL_MIN,
    DOMAIN,
    OPEN_METEO_FORECAST_DAYS,
    OPEN_METEO_PAST_DAYS,
)
from .sources.base import SourceError, SourceResult
from .sources.open_meteo import OpenMeteoSource

_LOGGER = logging.getLogger(__name__)

type PollenWatchConfigEntry = ConfigEntry[OpenMeteoDataUpdateCoordinator]


def _entry_option(entry: ConfigEntry, key: str, default: Any) -> Any:
    """Read a value preferring options (user-editable) over initial data."""
    if key in entry.options:
        return entry.options[key]
    return entry.data.get(key, default)


class OpenMeteoDataUpdateCoordinator(DataUpdateCoordinator[SourceResult]):
    """Coordinates hourly pollen fetches from Open-Meteo for one config entry."""

    config_entry: PollenWatchConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: PollenWatchConfigEntry
    ) -> None:
        interval_min = _entry_option(
            entry, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MIN
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(minutes=interval_min),
        )
        self.source = OpenMeteoSource(
            entry.data[CONF_LATITUDE],
            entry.data[CONF_LONGITUDE],
            _entry_option(entry, CONF_ALLERGENS, DEFAULT_ALLERGENS),
            past_days=OPEN_METEO_PAST_DAYS,
            forecast_days=OPEN_METEO_FORECAST_DAYS,
        )

    async def _async_update_data(self) -> SourceResult:
        session = async_get_clientsession(self.hass)
        try:
            result = await self.source.async_fetch(session=session)
        except SourceError as err:
            raise UpdateFailed(str(err)) from err
        if not result.ok:
            # Location was coverage-checked at setup; a non-OK result now means a
            # transient upstream issue rather than a misconfiguration.
            raise UpdateFailed(
                result.message or "Open-Meteo returned no usable pollen data."
            )
        return result
