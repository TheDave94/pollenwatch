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

__all__ = ["DOMAIN", "async_setup_entry", "async_unload_entry"]


async def async_setup_entry(
    hass: HomeAssistant, entry: PollenWatchConfigEntry
) -> bool:
    """Set up PollenWatch from a config entry."""
    from homeassistant.const import Platform

    from .coordinator import OpenMeteoDataUpdateCoordinator

    coordinator = OpenMeteoDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

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
