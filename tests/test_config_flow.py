"""Tests for the PollenWatch config and options flows."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pollenwatch.config_flow import CONF_ENABLE_PI
from custom_components.pollenwatch.const import (
    CONF_ALLERGENS,
    CONF_API_KEY,
    CONF_COUNTRY,
    CONF_ENABLED,
    CONF_SOURCES,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    SOURCE_POLLENINFORMATION,
    new_sources_config,
)

_LOCATION = {"latitude": 47.07, "longitude": 15.44}
_PROBE = "custom_components.pollenwatch.config_flow._async_probe_coverage"
_PROBE_PI = "custom_components.pollenwatch.config_flow._async_probe_polleninformation"
_SETUP = "custom_components.pollenwatch.async_setup_entry"


def _options_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="47.0700_15.4400",
        data={
            CONF_LATITUDE: 47.07,
            CONF_LONGITUDE: 15.44,
            CONF_ALLERGENS: ["grass", "birch"],
        },
        options={CONF_ALLERGENS: ["grass", "birch"], CONF_SOURCES: new_sources_config()},
    )


async def _start(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(_PROBE, return_value=None),
        patch(_SETUP, return_value=True) as mock_setup,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"location": _LOCATION, CONF_ALLERGENS: ["grass", "birch"]},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_LATITUDE: 47.07,
        CONF_LONGITUDE: 15.44,
        CONF_ALLERGENS: ["grass", "birch"],
    }
    assert result["result"].unique_id == "47.0700_15.4400"
    assert len(mock_setup.mock_calls) == 1


async def test_user_flow_out_of_coverage_shows_error(hass: HomeAssistant) -> None:
    result = await _start(hass)
    with patch(_PROBE, return_value="out_of_coverage"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"location": {"latitude": 40.71, "longitude": -74.0}, CONF_ALLERGENS: ["grass"]},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "out_of_coverage"}


async def test_user_flow_cannot_connect_shows_error(hass: HomeAssistant) -> None:
    result = await _start(hass)
    with patch(_PROBE, return_value="cannot_connect"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"location": _LOCATION, CONF_ALLERGENS: ["grass"]},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_requires_an_allergen(hass: HomeAssistant) -> None:
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"location": _LOCATION, CONF_ALLERGENS: []},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ALLERGENS: "no_allergens"}


async def test_duplicate_location_aborts(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id="47.0700_15.4400").add_to_hass(hass)

    result = await _start(hass)
    with patch(_PROBE, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"location": _LOCATION, CONF_ALLERGENS: ["grass"]},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_updates_allergens_and_interval(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="47.0700_15.4400",
        data={
            CONF_LATITUDE: 47.07,
            CONF_LONGITUDE: 15.44,
            CONF_ALLERGENS: ["grass", "birch"],
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_ALLERGENS: ["grass"], CONF_UPDATE_INTERVAL: 120},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_ALLERGENS] == ["grass"]
    assert entry.options[CONF_UPDATE_INTERVAL] == 120


async def test_options_enable_polleninformation(hass: HomeAssistant) -> None:
    entry = _options_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    with patch(_PROBE_PI, return_value=None):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_ALLERGENS: ["grass", "birch"],
                CONF_UPDATE_INTERVAL: 60,
                CONF_ENABLE_PI: True,
                CONF_COUNTRY: "AT",
                CONF_API_KEY: "secret-key",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    pi = entry.options[CONF_SOURCES][SOURCE_POLLENINFORMATION]
    assert pi[CONF_ENABLED] is True
    assert pi[CONF_COUNTRY] == "AT"
    assert pi[CONF_API_KEY] == "secret-key"


async def test_options_pi_out_of_coverage_errors(hass: HomeAssistant) -> None:
    entry = _options_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    with patch(_PROBE_PI, return_value="out_of_coverage"):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_ALLERGENS: ["grass", "birch"],
                CONF_UPDATE_INTERVAL: 60,
                CONF_ENABLE_PI: True,
                CONF_COUNTRY: "AT",
                CONF_API_KEY: "secret-key",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "out_of_coverage"}


async def test_options_pi_requires_country_and_key(hass: HomeAssistant) -> None:
    entry = _options_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ALLERGENS: ["grass", "birch"],
            CONF_UPDATE_INTERVAL: 60,
            CONF_ENABLE_PI: True,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_COUNTRY: "country_required",
        CONF_API_KEY: "api_key_required",
    }
