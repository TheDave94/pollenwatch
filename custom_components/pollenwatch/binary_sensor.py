"""Binary sensors for PollenWatch — cross-source divergence.

divergence is the boolean companion to consensus's "mixed": on when the sources
disagree by more than one level for a species. Lives under the same "PollenWatch
Analytics" device as consensus, and is unavailable when fewer than two sources
currently cover the species (it never flags divergence from a single source).
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ALLERGEN_NAMES
from .coordinator import (
    PollenWatchAnalyticsCoordinator,
    PollenWatchConfigEntry,
    analytics_device_info,
    multi_source_species,
)

ATTR_SOURCE_LEVELS = "source_levels"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PollenWatchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the divergence binary sensors (one per multi-source species)."""
    runtime = entry.runtime_data
    analytics = runtime.analytics
    if analytics is None:
        return
    async_add_entities(
        DivergenceSensor(analytics, entry, species)
        for species in multi_source_species(runtime.coordinators)
    )


class DivergenceSensor(
    CoordinatorEntity[PollenWatchAnalyticsCoordinator], BinarySensorEntity
):
    """True when sources disagree by more than one level for a species."""

    # Explicit name (not has_entity_name) so the entity ID is the documented
    # binary_sensor.pollenwatch_divergence_<species> rather than device-prefixed.
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:call-split"

    def __init__(
        self,
        coordinator: PollenWatchAnalyticsCoordinator,
        entry: PollenWatchConfigEntry,
        species: str,
    ) -> None:
        super().__init__(coordinator)
        self._species = species
        self._attr_unique_id = f"{entry.entry_id}_divergence_{species}"
        self._attr_name = f"PollenWatch Divergence {ALLERGEN_NAMES.get(species, species)}"
        self._attr_device_info = analytics_device_info(entry)

    def _result(self):
        return self.coordinator.data.consensus.get(self._species)

    @property
    def available(self) -> bool:
        result = self._result()
        return (
            super().available
            and result is not None
            and len(result.source_levels) >= 2
        )

    @property
    def is_on(self) -> bool | None:
        result = self._result()
        return result.diverged if result else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        result = self._result()
        if result is None:
            return None
        return {ATTR_SOURCE_LEVELS: result.source_levels}
