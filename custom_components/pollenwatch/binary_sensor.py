"""Binary sensors for PollenWatch — cross-source divergence.

divergence is the boolean companion to the consensus *level*: on whenever the
sources are NOT unanimous for a species (any disagreement, spread >= 1) — not
just the spread-of-two-or-more "mixed" case. This makes the consensus/divergence
pair honest: a {1,1,2} reading reports consensus "high" (take-the-higher) AND
divergence on, instead of a minority high masquerading as confident consensus
(issue #1; semantics widened 2026-06-29 from live 3-5 source data). Lives under
the same "PollenWatch Analytics" device as consensus, and is unavailable when
fewer than two sources currently cover the species (it never flags divergence
from a single source). The `spread` attribute (max-min of the per-source levels)
grades the disagreement: 1 = adjacent (a level reported with take-the-higher),
>=2 = "mixed" (no single level).
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

from .const import ALLERGEN_NAMES, DOMAIN
from .coordinator import (
    PollenWatchAnalyticsCoordinator,
    PollenWatchConfigEntry,
    analytics_device_info,
    multi_source_species,
)

# Coordinator-driven entities with no per-entity writes — HA serialization
# is unnecessary; declare parallel updates to keep the silver rule explicit.
PARALLEL_UPDATES = 0

ATTR_SOURCE_LEVELS = "source_levels"
ATTR_SPREAD = "spread"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PollenWatchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the divergence binary sensors (one per multi-source species)."""
    from .sensor import _async_remove_orphan_analytics

    runtime = entry.runtime_data
    analytics = runtime.analytics
    if analytics is None:
        _async_remove_orphan_analytics(hass, entry, set(), "divergence")
        return
    species_list = multi_source_species(runtime.coordinators)
    # Prune divergence binary sensors for species that dropped below the
    # 2-source threshold (mirrors the consensus pruning in sensor.py).
    _async_remove_orphan_analytics(hass, entry, set(species_list), "divergence")
    async_add_entities(
        DivergenceSensor(analytics, entry, species)
        for species in species_list
    )


class DivergenceSensor(
    CoordinatorEntity[PollenWatchAnalyticsCoordinator], BinarySensorEntity
):
    """True when the sources are not unanimous for a species (any spread >= 1)."""

    # Device-scoped entity ID (see ConsensusSensor): HA 2026.5 prefixes with the
    # device slug -> binary_sensor.pollenwatch_analytics_<species>_divergence.
    _attr_has_entity_name = True
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
        self._attr_translation_key = f"divergence_{species}"
        self._attr_name = f"{ALLERGEN_NAMES.get(species, species)} divergence"
        # Canonical-key entity_id — one rule across all 24 species so users
        # iterating programmatically don't need a translation table.
        self.entity_id = f"binary_sensor.{DOMAIN}_analytics_{species}_divergence"
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
        levels = result.source_levels.values()
        # Degree of disagreement: 1 = adjacent (a level is still reported via
        # take-the-higher), >=2 = "mixed" (no single level). 0 when unanimous.
        spread = (max(levels) - min(levels)) if levels else 0
        return {ATTR_SOURCE_LEVELS: result.source_levels, ATTR_SPREAD: spread}
