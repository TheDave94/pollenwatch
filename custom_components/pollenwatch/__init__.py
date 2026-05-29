"""The PollenWatch integration.

This package entry point is deliberately free of top-level ``homeassistant``
imports: importing the package (and therefore the source layer under
``sources/``) must not require Home Assistant, so the data layer stays testable
in isolation. The Home Assistant API is imported inside the entry functions,
which only run when HA loads the integration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .const import DOMAIN, PLATFORMS

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import PollenWatchConfigEntry

__all__ = [
    "DOMAIN",
    "async_migrate_entry",
    "async_setup_entry",
    "async_unload_entry",
]


async def async_migrate_entry(
    hass: HomeAssistant, entry: PollenWatchConfigEntry
) -> bool:
    """Migrate a config entry to the current version.

    v1 → v2 (multi-source): additively add the per-source enablement config to
    options. Purely additive — no existing key is moved or dropped — so the live
    single-source (Open-Meteo) setup is preserved. Idempotent.
    """
    from .const import CONF_SOURCES, new_sources_config

    if entry.version > 2:
        # Downgrade (e.g. user rolled back) — refuse rather than corrupt.
        return False

    if entry.version == 1:
        options = {**entry.options}
        options.setdefault(CONF_SOURCES, new_sources_config())
        hass.config_entries.async_update_entry(entry, options=options, version=2)

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: PollenWatchConfigEntry
) -> bool:
    """Set up PollenWatch from a config entry."""
    from homeassistant.const import Platform

    from .const import SOURCE_OPEN_METEO
    from .coordinator import PollenWatchData, build_coordinators

    coordinators = build_coordinators(hass, entry)
    # Open-Meteo is the primary, keyless source: it must be ready or the entry
    # retries. Optional sources (polleninformation) refresh non-blockingly so a
    # failure there leaves their sensors unavailable without taking the entry down.
    await coordinators[SOURCE_OPEN_METEO].async_config_entry_first_refresh()
    for source_key, coordinator in coordinators.items():
        if source_key != SOURCE_OPEN_METEO:
            await coordinator.async_refresh()
    entry.runtime_data = PollenWatchData(coordinators=coordinators)

    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform(p) for p in PLATFORMS]
    )
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: PollenWatchConfigEntry
) -> bool:
    """Unload a config entry."""
    from homeassistant.const import Platform

    return await hass.config_entries.async_unload_platforms(
        entry, [Platform(p) for p in PLATFORMS]
    )


async def _async_reload_entry(
    hass: HomeAssistant, entry: PollenWatchConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
