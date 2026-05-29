"""End-to-end setup test: config entry -> coordinator -> sensors.

The network boundary is mocked at the integration's edge (the coordinator's
session getter and the source's async fetch) so no real aiohttp ClientSession
is created. This keeps the test deterministic and exercises the wiring that
matters here — coordinator data flow, sensor creation, entity IDs, attributes,
and unload. The real aiohttp transport is covered by the source's async unit
tests and was verified live against Open-Meteo.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pollenwatch.const import ATTRIBUTION_CAMS, CONF_ALLERGENS, DOMAIN
from custom_components.pollenwatch.sources.open_meteo import OpenMeteoSource

_SESSION = "custom_components.pollenwatch.coordinator.async_get_clientsession"
_FETCH = "custom_components.pollenwatch.sources.open_meteo.OpenMeteoSource.async_fetch"


def _payload() -> dict:
    times = [
        "2026-05-29T00:00",
        "2026-05-29T12:00",
        "2026-05-30T06:00",
        "2026-05-30T18:00",
    ]
    return {
        "latitude": 47.1,
        "longitude": 15.4,
        "timezone": "Europe/Vienna",
        "elevation": 363.0,
        "hourly_units": {"grass_pollen": "grains/m³", "birch_pollen": "grains/m³"},
        "current": {
            "time": "2026-05-29T12:00",
            "grass_pollen": 20.8,
            "birch_pollen": 0.1,
        },
        "hourly": {
            "time": times,
            "grass_pollen": [10.0, 20.8, 5.0, 7.0],
            "birch_pollen": [0.0, 0.1, 0.0, 0.0],
        },
    }


def _result():
    # Build a realistic SourceResult via the real parser.
    return OpenMeteoSource(47.07, 15.44, ["grass", "birch"]).parse(_payload())


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="47.0700_15.4400",
        title="PollenWatch (47.070, 15.440)",
        data={
            CONF_LATITUDE: 47.07,
            CONF_LONGITUDE: 15.44,
            CONF_ALLERGENS: ["grass", "birch"],
        },
    )


async def test_setup_creates_sensors_with_expected_naming(
    hass: HomeAssistant,
) -> None:
    entry = _entry()
    entry.add_to_hass(hass)

    with (
        patch(_SESSION, return_value=object()),
        patch(_FETCH, new=AsyncMock(return_value=_result())),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

        # Branded, ecosystem-style entity ID (see MILESTONE_2.md Q2).
        state = hass.states.get("sensor.pollenwatch_open_meteo_grass")
        assert state is not None
        assert float(state.state) == 20.8

        # Daily-peak forecast: 29th -> max(10, 20.8); 30th -> max(5, 7).
        assert state.attributes["forecast"] == [
            {"date": "2026-05-29", "value": 20.8},
            {"date": "2026-05-30", "value": 7.0},
        ]
        assert state.attributes["attribution"] == ATTRIBUTION_CAMS
        assert state.attributes["snapped_latitude"] == 47.1
        assert state.attributes["requested_latitude"] == 47.07

        assert hass.states.get("sensor.pollenwatch_open_meteo_birch") is not None


async def test_unload_entry(hass: HomeAssistant) -> None:
    entry = _entry()
    entry.add_to_hass(hass)

    with (
        patch(_SESSION, return_value=object()),
        patch(_FETCH, new=AsyncMock(return_value=_result())),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.NOT_LOADED
