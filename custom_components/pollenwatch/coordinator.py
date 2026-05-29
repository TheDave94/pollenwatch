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
from homeassistant.util import dt as dt_util

from .analytics import (
    PERCENTILE_WINDOW_DAYS,
    PercentileResult,
    compute_recent_percentile,
    daily_peaks,
    recent_percentile_from_series,
)
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
    """Runtime data stored on the config entry: source + analytics coordinators."""

    coordinators: dict[str, PollenWatchSourceCoordinator] = field(
        default_factory=dict
    )
    analytics: PollenWatchAnalyticsCoordinator | None = None


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


# Result key: (source_key, species) -> PercentileResult
type PercentileMap = dict[tuple[str, str], PercentileResult]


class PollenWatchAnalyticsCoordinator(DataUpdateCoordinator["PercentileMap"]):
    """Computes derived analytics from the source coordinators.

    Milestone 3b: recent_percentile per (source, species). consensus/divergence
    arrive in later steps. Sources with their own history (Open-Meteo's 92-day
    backfill) compute purely; sources without one (polleninformation) baseline on
    HA recorder history of their raw sensor, emitting "insufficient_history" until
    enough days accrue.
    """

    config_entry: PollenWatchConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PollenWatchConfigEntry,
        sources: dict[str, PollenWatchSourceCoordinator],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_analytics",
            config_entry=entry,
            update_interval=timedelta(hours=1),
        )
        self._sources = sources

    async def _async_update_data(self) -> PercentileMap:
        today = dt_util.now().date().isoformat()
        out: PercentileMap = {}
        for source_key, coordinator in self._sources.items():
            data = coordinator.data
            if data is None:
                continue
            for species, series in data.allergens.items():
                if source_key == SOURCE_OPEN_METEO:
                    out[(source_key, species)] = recent_percentile_from_series(
                        data.times, series.values, today
                    )
                else:
                    out[(source_key, species)] = await self._recorder_percentile(
                        source_key, species, today
                    )
        return out

    async def _recorder_percentile(
        self, source_key: str, species: str, today: str
    ) -> PercentileResult:
        """recent_percentile from HA recorder history of a source's raw sensor."""
        entity_id = f"sensor.{DOMAIN}_{source_key}_{species}"
        peaks = await self._recorder_daily_peaks(entity_id)
        return compute_recent_percentile(peaks[-PERCENTILE_WINDOW_DAYS:], today)

    async def _recorder_daily_peaks(
        self, entity_id: str
    ) -> list[tuple[str, float]]:
        """Daily peaks of a numeric entity over the trailing window, via recorder.

        Returns an empty list if the recorder is unavailable (→ the caller emits
        "insufficient_history" rather than a misleading number).
        """
        if "recorder" not in self.hass.config.components:
            return []
        from homeassistant.components.recorder import get_instance, history

        end = dt_util.now()
        start = end - timedelta(days=PERCENTILE_WINDOW_DAYS)
        states = await get_instance(self.hass).async_add_executor_job(
            history.state_changes_during_period,
            self.hass,
            start,
            end,
            entity_id,
        )
        times: list[str] = []
        values: list[float] = []
        for state in states.get(entity_id, []):
            try:
                value = float(state.state)
            except (ValueError, TypeError):
                continue  # 'unknown'/'unavailable'
            times.append(dt_util.as_local(state.last_changed).isoformat())
            values.append(value)
        return daily_peaks(times, values)
