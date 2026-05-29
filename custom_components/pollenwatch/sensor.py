"""Sensor entities for PollenWatch.

Milestone 2: one sensor per Open-Meteo allergen. State is the current value in
grains/m³; the daily-peak forecast and provenance live in attributes. Entities
sit under a per-source device (see MILESTONE_2.md Q1) and are named so their
entity IDs slug to ``sensor.pollenwatch_open_meteo_<allergen>`` (see §7).
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .analytics import daily_peaks
from .const import (
    ALLERGEN_NAMES,
    ATTR_FORECAST,
    ATTR_GRID_SHIFT_KM,
    ATTR_LAST_UPDATED,
    ATTR_REQUESTED_LAT,
    ATTR_REQUESTED_LON,
    ATTR_SNAPPED_LAT,
    ATTR_SNAPPED_LON,
    ATTRIBUTION_CAMS,
    DOMAIN,
    FORECAST_DAYS,
    SOURCE_ATTRIBUTIONS,
    SOURCE_CONFIG_URLS,
    SOURCE_DEVICE_MODELS,
    SOURCE_DEVICE_NAMES,
)
from .coordinator import (
    PollenWatchAnalyticsCoordinator,
    PollenWatchConfigEntry,
    PollenWatchSourceCoordinator,
)

# Extra-state-attribute keys for the recent_percentile sensor.
ATTR_HISTORY_STATUS = "history_status"
ATTR_DAYS_OF_HISTORY = "days_of_history"


def _source_device_info(entry: PollenWatchConfigEntry, source_key: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{source_key}")},
        name=SOURCE_DEVICE_NAMES[source_key],
        manufacturer="PollenWatch",
        model=SOURCE_DEVICE_MODELS.get(source_key),
        entry_type=DeviceEntryType.SERVICE,
        configuration_url=SOURCE_CONFIG_URLS.get(source_key),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PollenWatchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PollenWatch sensors for a config entry.

    Runs on every reload (including after an options change), so it also prunes
    registry entries for allergens no longer configured for each source.
    """
    runtime = entry.runtime_data
    analytics = runtime.analytics
    entities: list[SensorEntity] = []
    for source_key, coordinator in runtime.coordinators.items():
        # Keep registry entries for every configured allergen (so a transient
        # absence doesn't delete a sensor); only create sensors for allergens the
        # source actually returned (a source's set is location/country-dependent).
        configured = set(coordinator.source.allergens)
        _async_remove_deconfigured_entities(hass, entry, source_key, configured)
        if coordinator.data is None:
            continue
        present = [a for a in coordinator.source.allergens if a in coordinator.data.allergens]
        for allergen in present:
            entities.append(PollenWatchSensor(coordinator, source_key, allergen))
            if analytics is not None:
                entities.append(
                    RecentPercentileSensor(analytics, entry, source_key, allergen)
                )
    async_add_entities(entities)


@callback
def _async_remove_deconfigured_entities(
    hass: HomeAssistant,
    entry: PollenWatchConfigEntry,
    source_key: str,
    configured: set[str],
) -> None:
    """Remove a source's sensor entities for allergens no longer configured.

    Without this, deselecting an allergen in the options flow would leave the
    sensor lingering as ``unavailable`` in the registry instead of disappearing.
    """
    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_{source_key}_"
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.unique_id.startswith(prefix):
            # Suffix is "<allergen>" or "<allergen>_<metric>" (e.g.
            # grass_recent_percentile); the allergen is the first token. Removing
            # a deconfigured allergen drops all its entities (raw + derived).
            allergen = reg_entry.unique_id[len(prefix):].split("_", 1)[0]
            if allergen not in configured:
                registry.async_remove(reg_entry.entity_id)


def _forecast_attr(
    times: list[str], values: list[float | None], today: str, max_days: int
) -> list[dict[str, Any]]:
    """The upcoming daily-peak forecast: per-day max for dates >= today.

    The series now spans ~92 past days (for recent_percentile), so the forecast
    must be the today-onward slice — not the earliest days. Peaks (not means)
    drive allergic reactions; the partially-null 5th day is dropped via max_days.
    """
    return [
        {"date": date, "value": peak}
        for date, peak in daily_peaks(times, values)
        if date >= today
    ][:max_days]


class PollenWatchSensor(
    CoordinatorEntity[PollenWatchSourceCoordinator], SensorEntity
):
    """Current pollen concentration for one allergen from one source."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:flower-pollen"

    def __init__(
        self,
        coordinator: PollenWatchSourceCoordinator,
        source_key: str,
        allergen: str,
    ) -> None:
        super().__init__(coordinator)
        self._allergen = allergen
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{source_key}_{allergen}"
        self._attr_translation_key = allergen
        self._attr_attribution = SOURCE_ATTRIBUTIONS.get(source_key, ATTRIBUTION_CAMS)
        # Unit comes from the source: grains/m³ for Open-Meteo, None (an ordinal
        # 0–4 index) for polleninformation — never fake a concentration unit.
        series = coordinator.data.allergens.get(allergen)
        self._attr_native_unit_of_measurement = series.unit if series else None
        self._attr_device_info = _source_device_info(entry, source_key)

    @property
    def available(self) -> bool:
        return (
            super().available
            and self._allergen in self.coordinator.data.allergens
        )

    @property
    def native_value(self) -> float | None:
        series = self.coordinator.data.allergens.get(self._allergen)
        return series.current if series else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        result = self.coordinator.data
        series = result.allergens.get(self._allergen)
        if series is None:
            return None
        shift = result.coordinate_shift_km
        today = (result.current_time or "")[:10]
        return {
            ATTR_FORECAST: _forecast_attr(
                result.times, series.values, today, FORECAST_DAYS
            ),
            ATTR_REQUESTED_LAT: result.requested_lat,
            ATTR_REQUESTED_LON: result.requested_lon,
            ATTR_SNAPPED_LAT: result.snapped_lat,
            ATTR_SNAPPED_LON: result.snapped_lon,
            ATTR_GRID_SHIFT_KM: round(shift, 2) if shift is not None else None,
            ATTR_LAST_UPDATED: result.generated_at,
        }


class RecentPercentileSensor(
    CoordinatorEntity[PollenWatchAnalyticsCoordinator], SensorEntity
):
    """Today's daily peak as a percentile of the recent window (per source).

    Single-source (each source gets its own). Open-Meteo computes from its
    92-day backfill (day one); polleninformation baselines on recorder history
    and reports an honest "insufficient_history" state (no number) until enough
    days accrue. State is unitless 0–100; the history status is in attributes.
    """

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:chart-bell-curve-cumulative"
    _attr_suggested_display_precision = 0

    def __init__(
        self,
        coordinator: PollenWatchAnalyticsCoordinator,
        entry: PollenWatchConfigEntry,
        source_key: str,
        allergen: str,
    ) -> None:
        super().__init__(coordinator)
        self._key = (source_key, allergen)
        self._attr_unique_id = (
            f"{entry.entry_id}_{source_key}_{allergen}_recent_percentile"
        )
        # English name (derived metrics aren't localised yet); the device-name
        # slug keeps the entity ID as pollenwatch_<source>_<allergen>_recent_percentile.
        self._attr_name = f"{ALLERGEN_NAMES.get(allergen, allergen)} recent percentile"
        self._attr_device_info = _source_device_info(entry, source_key)

    @property
    def native_value(self) -> float | None:
        result = self.coordinator.data.get(self._key)
        if result is None or result.status != "ok":
            return None
        return result.percentile

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        result = self.coordinator.data.get(self._key)
        if result is None:
            return None
        return {
            ATTR_HISTORY_STATUS: result.status,
            ATTR_DAYS_OF_HISTORY: result.days,
        }
