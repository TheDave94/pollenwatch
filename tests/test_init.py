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

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pollenwatch import async_migrate_entry
from custom_components.pollenwatch.const import (
    ATTRIBUTION_CAMS,
    CONF_ALLERGENS,
    CONF_API_KEY,
    CONF_COUNTRY,
    CONF_ENABLED,
    CONF_SENSITIVITY,
    CONF_SOURCES,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    SOURCE_OPEN_METEO,
    SOURCE_POLLENINFORMATION,
    new_sources_config,
)
from custom_components.pollenwatch.sources.open_meteo import OpenMeteoSource
from custom_components.pollenwatch.sources.polleninformation import (
    PolleninformationSource,
)

_PI_FETCH = (
    "custom_components.pollenwatch.sources.polleninformation."
    "PolleninformationSource.async_fetch"
)

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
        version=2,
        unique_id="47.0700_15.4400",
        title="PollenWatch (47.070, 15.440)",
        data={
            CONF_LATITUDE: 47.07,
            CONF_LONGITUDE: 15.44,
            CONF_ALLERGENS: ["grass", "birch"],
        },
        options={CONF_SOURCES: new_sources_config()},
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


async def test_deselecting_allergen_removes_its_entity(hass: HomeAssistant) -> None:
    entry = _entry()  # grass + birch
    entry.add_to_hass(hass)

    with (
        patch(_SESSION, return_value=object()),
        patch(_FETCH, new=AsyncMock(return_value=_result())),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        registry = er.async_get(hass)
        birch_uid = f"{entry.entry_id}_open_meteo_birch"
        grass_uid = f"{entry.entry_id}_open_meteo_grass"
        assert registry.async_get_entity_id("sensor", DOMAIN, birch_uid) is not None

        # Deselect birch via options; the entry reloads on the update listener.
        hass.config_entries.async_update_entry(
            entry, options={CONF_ALLERGENS: ["grass"]}
        )
        await hass.async_block_till_done()

        # Birch is removed from the registry (not left as unavailable); grass stays.
        assert registry.async_get_entity_id("sensor", DOMAIN, birch_uid) is None
        assert registry.async_get_entity_id("sensor", DOMAIN, grass_uid) is not None
        assert hass.states.get("sensor.pollenwatch_open_meteo_birch") is None
        assert hass.states.get("sensor.pollenwatch_open_meteo_grass") is not None


def _v1_entry() -> MockConfigEntry:
    """Reconstruct the live single-source v1 entry shape (the API does not
    expose entry.data, so this mirrors what milestone-2 setup + options wrote)."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id="47.0700_15.4400",
        title="PollenWatch (47.070, 15.440)",
        data={
            CONF_LATITUDE: 47.07,
            CONF_LONGITUDE: 15.44,
            CONF_ALLERGENS: ["grass", "birch"],
        },
        options={CONF_ALLERGENS: ["grass", "birch"], CONF_UPDATE_INTERVAL: 60},
    )


async def test_migrate_v1_entry_to_v2(hass: HomeAssistant) -> None:
    entry = _v1_entry()
    entry.add_to_hass(hass)

    with (
        patch(_SESSION, return_value=object()),
        patch(_FETCH, new=AsyncMock(return_value=_result())),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Migrated to v2 with the additive sources config.
    assert entry.version == 2
    sources = entry.options[CONF_SOURCES]
    assert sources[SOURCE_OPEN_METEO][CONF_ENABLED] is True
    assert sources[SOURCE_POLLENINFORMATION][CONF_ENABLED] is False
    # Existing keys preserved (purely additive migration).
    assert entry.data[CONF_ALLERGENS] == ["grass", "birch"]
    assert entry.options[CONF_UPDATE_INTERVAL] == 60
    # Open-Meteo keeps working through the migration.
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.pollenwatch_open_meteo_grass") is not None


async def test_migrate_is_idempotent_on_v2(hass: HomeAssistant) -> None:
    entry = _entry()  # already v2 (default MockConfigEntry version)
    entry.add_to_hass(hass)
    before = dict(entry.options)
    assert await async_migrate_entry(hass, entry) is True
    assert entry.version == 2
    assert dict(entry.options) == before


def _pi_result():
    payload = {
        "contamination": [
            {"poll_id": 5, "poll_title": "grasses (Poaceae)",
             "contamination_1": 3, "contamination_2": 2,
             "contamination_3": 2, "contamination_4": 1},
            {"poll_id": 2, "poll_title": "birch (Betula)",
             "contamination_1": 0, "contamination_2": 0,
             "contamination_3": 0, "contamination_4": 0},
        ],
        "allergyrisk": {},
        "allergyrisk_hourly": {},
    }
    return PolleninformationSource(
        47.07, 15.44, "AT", "k", ["grass", "birch"]
    ).parse(payload)


def _two_source_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="47.0700_15.4400",
        title="PollenWatch (47.070, 15.440)",
        data={
            CONF_LATITUDE: 47.07,
            CONF_LONGITUDE: 15.44,
            CONF_ALLERGENS: ["grass", "birch"],
        },
        options={
            CONF_ALLERGENS: ["grass", "birch"],
            CONF_SOURCES: {
                SOURCE_OPEN_METEO: {CONF_ENABLED: True},
                SOURCE_POLLENINFORMATION: {
                    CONF_ENABLED: True,
                    CONF_API_KEY: "placeholder-key",
                    CONF_COUNTRY: "AT",
                },
            },
        },
    )


async def test_two_sources_coexist(hass: HomeAssistant) -> None:
    entry = _two_source_entry()
    entry.add_to_hass(hass)

    with (
        patch(_SESSION, return_value=object()),
        patch(_FETCH, new=AsyncMock(return_value=_result())),
        patch(_PI_FETCH, new=AsyncMock(return_value=_pi_result())),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Open-Meteo: grains/m³ concentration.
    om = hass.states.get("sensor.pollenwatch_open_meteo_grass")
    assert om is not None
    assert om.attributes.get("unit_of_measurement") == "grains/m³"

    # polleninformation: native 0–4 index, NO concentration unit.
    pi = hass.states.get("sensor.pollenwatch_polleninformation_grass")
    assert pi is not None
    assert pi.state == "3"
    assert pi.attributes.get("unit_of_measurement") is None
    assert pi.attributes["forecast"] == [
        {"date": pi.attributes["forecast"][0]["date"], "value": 3},
        {"date": pi.attributes["forecast"][1]["date"], "value": 2},
        {"date": pi.attributes["forecast"][2]["date"], "value": 2},
        {"date": pi.attributes["forecast"][3]["date"], "value": 1},
    ]


async def test_personal_score_applies_multiplier(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="47.0700_15.4400",
        data={
            CONF_LATITUDE: 47.07,
            CONF_LONGITUDE: 15.44,
            CONF_ALLERGENS: ["grass", "birch"],
        },
        options={
            CONF_ALLERGENS: ["grass", "birch"],
            CONF_SENSITIVITY: {"grass": 1.5},  # birch defaults to 1.0
            CONF_SOURCES: new_sources_config(),
        },
    )
    entry.add_to_hass(hass)
    with (
        patch(_SESSION, return_value=object()),
        patch(_FETCH, new=AsyncMock(return_value=_result())),  # grass current 20.8
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    grass = hass.states.get("sensor.pollenwatch_open_meteo_grass_personal_score")
    assert grass is not None
    assert float(grass.state) == pytest.approx(20.8 * 1.5)
    assert grass.attributes["multiplier"] == 1.5
    assert grass.attributes["unit_of_measurement"] == "grains/m³"

    # birch (no multiplier configured) -> 1.0, so equals raw (0.1)
    birch = hass.states.get("sensor.pollenwatch_open_meteo_birch_personal_score")
    assert birch is not None
    assert float(birch.state) == pytest.approx(0.1)
    assert birch.attributes["multiplier"] == 1.0


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
