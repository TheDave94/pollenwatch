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

from .const import (
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
from .coordinator import PollenWatchConfigEntry, PollenWatchSourceCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PollenWatchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PollenWatch sensors for a config entry.

    Runs on every reload (including after an options change), so it also prunes
    registry entries for allergens no longer configured for each source.
    """
    coordinators = entry.runtime_data.coordinators
    entities: list[PollenWatchSensor] = []
    for source_key, coordinator in coordinators.items():
        configured = list(coordinator.source.allergens)
        _async_remove_deconfigured_entities(hass, entry, source_key, set(configured))
        entities.extend(
            PollenWatchSensor(coordinator, source_key, allergen)
            for allergen in configured
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
            allergen = reg_entry.unique_id[len(prefix):]
            if allergen not in configured:
                registry.async_remove(reg_entry.entity_id)


def _daily_peak_forecast(
    times: list[str], values: list[float | None], max_days: int
) -> list[dict[str, Any]]:
    """Collapse the hourly series into per-day peak values.

    Peaks (not means) drive allergic reactions; the partially-null 5th forecast
    day is dropped by capping at ``max_days``.
    """
    peaks: dict[str, float] = {}
    for time, value in zip(times, values, strict=False):
        if value is None:
            continue
        date = time[:10]  # 'YYYY-MM-DD'
        peaks[date] = max(peaks.get(date, value), value)
    return [
        {"date": date, "value": peak}
        for date, peak in sorted(peaks.items())[:max_days]
    ]


class PollenWatchSensor(
    CoordinatorEntity[PollenWatchSourceCoordinator], SensorEntity
):
    """Current pollen concentration for one allergen from one source."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "grains/m³"
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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{source_key}")},
            name=SOURCE_DEVICE_NAMES[source_key],
            manufacturer="PollenWatch",
            model=SOURCE_DEVICE_MODELS.get(source_key),
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=SOURCE_CONFIG_URLS.get(source_key),
        )

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
        return {
            ATTR_FORECAST: _daily_peak_forecast(
                result.times, series.values, FORECAST_DAYS
            ),
            ATTR_REQUESTED_LAT: result.requested_lat,
            ATTR_REQUESTED_LON: result.requested_lon,
            ATTR_SNAPPED_LAT: result.snapped_lat,
            ATTR_SNAPPED_LON: result.snapped_lon,
            ATTR_GRID_SHIFT_KM: round(shift, 2) if shift is not None else None,
            ATTR_LAST_UPDATED: result.generated_at,
        }
