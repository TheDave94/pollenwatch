"""Tests for the PollenWatch config and options flows."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pollenwatch.config_flow import CONF_ENABLE_PI, _sensitivity_field
from custom_components.pollenwatch.const import (
    CONF_ALLERGENS,
    CONF_API_KEY,
    CONF_COUNTRY,
    CONF_DEFAULT_LAYOUT,
    CONF_ENABLED,
    CONF_SELECTED_SPECIES,
    CONF_SENSITIVITY,
    CONF_SOURCES,
    CONF_UPDATE_INTERVAL,
    DEFAULT_LAYOUT,
    DOMAIN,
    LAYOUT_BARS,
    LAYOUT_GAUGE,
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
    """v2.0+ two-step flow: location → species → entry.

    The user step is now location-only; species selection is the next
    step with region-aware preselection.
    """
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Step 1: submit location, advance to species step
    with patch(_PROBE, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"location": _LOCATION},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "species"

    # Step 2: submit species, create entry
    with patch(_SETUP, return_value=True) as mock_setup:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SELECTED_SPECIES: ["grass", "birch"]},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_LATITUDE: 47.07,
        CONF_LONGITUDE: 15.44,
        CONF_SELECTED_SPECIES: ["grass", "birch"],
    }
    assert result["result"].unique_id == "47.0700_15.4400"
    assert len(mock_setup.mock_calls) == 1


async def test_quick_pick_overrides_selection(hass: HomeAssistant) -> None:
    """The cross-validated quick-pick toggle replaces the user's selection
    with the 8 core species (locked Phase D contract)."""
    from custom_components.pollenwatch.config_flow import CONF_QUICK_PICK_CORE
    from custom_components.pollenwatch.region_defaults import HIGH_POTENCY_CORE

    result = await _start(hass)
    with patch(_PROBE, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"location": _LOCATION},
        )
    assert result["step_id"] == "species"

    # Submit with quick-pick toggle TRUE — even with a minimal valid
    # selection (just grass), the toggle overrides to the full 8-species
    # cross-validated core.
    with patch(_SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SELECTED_SPECIES: ["grass"],
                CONF_QUICK_PICK_CORE: True,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    selected = result["data"][CONF_SELECTED_SPECIES]
    # Should be exactly the 8 core species (test env has all available).
    assert set(selected) == set(HIGH_POTENCY_CORE), selected


async def test_user_flow_out_of_coverage_shows_error(hass: HomeAssistant) -> None:
    result = await _start(hass)
    with patch(_PROBE, return_value="out_of_coverage"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"location": {"latitude": 40.71, "longitude": -74.0}},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "out_of_coverage"}


async def test_user_flow_cannot_connect_shows_error(hass: HomeAssistant) -> None:
    result = await _start(hass)
    with patch(_PROBE, return_value="cannot_connect"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"location": _LOCATION},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_species_flow_requires_a_species(hass: HomeAssistant) -> None:
    """The species step rejects empty selection (no quick-pick override).
    Renamed from v1.x's test_user_flow_requires_an_allergen: in v2.0+ the
    allergen check moves to the species step, not the user step."""
    result = await _start(hass)
    with patch(_PROBE, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"location": _LOCATION},
        )
    assert result["step_id"] == "species"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SELECTED_SPECIES: []},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_SELECTED_SPECIES: "no_species"}


async def test_duplicate_location_aborts(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id="47.0700_15.4400").add_to_hass(hass)

    result = await _start(hass)
    with patch(_PROBE, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"location": _LOCATION},
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
        {CONF_SELECTED_SPECIES: ["grass"], CONF_UPDATE_INTERVAL: 120},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    # v3 storage key — options flow writes CONF_SELECTED_SPECIES.
    assert entry.options[CONF_SELECTED_SPECIES] == ["grass"]
    assert entry.options[CONF_UPDATE_INTERVAL] == 120


async def test_options_enable_polleninformation(hass: HomeAssistant) -> None:
    entry = _options_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    with patch(_PROBE_PI, return_value=None):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_SELECTED_SPECIES: ["grass", "birch"],
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
                CONF_SELECTED_SPECIES: ["grass", "birch"],
                CONF_UPDATE_INTERVAL: 60,
                CONF_ENABLE_PI: True,
                CONF_COUNTRY: "AT",
                CONF_API_KEY: "secret-key",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "out_of_coverage"}


async def test_options_store_sensitivity_multiplier(hass: HomeAssistant) -> None:
    entry = _options_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SELECTED_SPECIES: ["grass", "birch"],
            CONF_UPDATE_INTERVAL: 60,
            CONF_ENABLE_PI: False,
            _sensitivity_field("grass"): 1.8,
            _sensitivity_field("birch"): 0.5,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    sensitivity = entry.options[CONF_SENSITIVITY]
    assert sensitivity["grass"] == 1.8
    assert sensitivity["birch"] == 0.5
    # Unspecified species fall back to the default (1.0) in the form.
    assert sensitivity["olive"] == 1.0


async def test_options_default_layout_round_trips(hass: HomeAssistant) -> None:
    """v2.4+: the layout dropdown stores into entry.options and reads back.

    Set 'bars'; assert the option round-trips. The card consumes this via
    the pollenwatch/config WS endpoint (covered in test_websocket_api.py).
    """
    entry = _options_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SELECTED_SPECIES: ["grass", "birch"],
            CONF_DEFAULT_LAYOUT: LAYOUT_BARS,
            CONF_UPDATE_INTERVAL: 60,
            CONF_ENABLE_PI: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_DEFAULT_LAYOUT] == LAYOUT_BARS


async def test_options_default_layout_falls_back_for_legacy_entry(
    hass: HomeAssistant,
) -> None:
    """A pre-v2.4 entry has no CONF_DEFAULT_LAYOUT key; the form must pre-fill
    'gauge' and a submission that omits the key must still write 'gauge'
    (the schema default). No migration / no entry-version bump."""
    entry = _options_entry()
    # Sanity: the fixture omits CONF_DEFAULT_LAYOUT — this is the legacy shape.
    assert CONF_DEFAULT_LAYOUT not in entry.options
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    # Submit without the layout key — voluptuous fills the schema default.
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SELECTED_SPECIES: ["grass", "birch"],
            CONF_UPDATE_INTERVAL: 60,
            CONF_ENABLE_PI: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_DEFAULT_LAYOUT] == LAYOUT_GAUGE
    assert DEFAULT_LAYOUT == LAYOUT_GAUGE


async def test_options_default_layout_rejects_invalid_value(
    hass: HomeAssistant,
) -> None:
    """An out-of-enum value (e.g. typoed 'spinner') must be rejected at the
    selector level — the option store must never receive a layout the card
    cannot render."""
    entry = _options_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    # Submitting an unknown value raises voluptuous.MultipleInvalid before
    # the flow's handler is reached. The card-facing storage stays clean.
    with pytest.raises(vol.Invalid):
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_SELECTED_SPECIES: ["grass", "birch"],
                CONF_DEFAULT_LAYOUT: "spinner",
                CONF_UPDATE_INTERVAL: 60,
                CONF_ENABLE_PI: False,
            },
        )

    # Nothing was written.
    assert CONF_DEFAULT_LAYOUT not in entry.options


async def test_options_pi_requires_country_and_key(hass: HomeAssistant) -> None:
    entry = _options_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SELECTED_SPECIES: ["grass", "birch"],
            CONF_UPDATE_INTERVAL: 60,
            CONF_ENABLE_PI: True,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_COUNTRY: "country_required",
        CONF_API_KEY: "api_key_required",
    }


def _suggested_values(schema: vol.Schema) -> dict:
    """Field name → suggested_value the re-rendered form carries."""
    out = {}
    for marker in schema.schema:
        desc = getattr(marker, "description", None) or {}
        if "suggested_value" in desc:
            out[marker.schema] = desc["suggested_value"]
    return out


async def test_options_flow_preserves_input_on_error(hass: HomeAssistant) -> None:
    """On an error re-render, the options form keeps what the user just
    submitted rather than snapping back to the saved entry state.

    Regression guard for the input-reset bug: the saved entry has PI disabled,
    so a surviving ``CONF_ENABLE_PI: True`` (+ country/key/interval/species)
    proves the form re-seeds from ``user_input``, not from the entry.
    """
    entry = _options_entry()  # PI disabled in the saved options
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    submitted = {
        CONF_SELECTED_SPECIES: ["grass"],
        CONF_UPDATE_INTERVAL: 90,
        CONF_ENABLE_PI: True,
        CONF_COUNTRY: "AT",
        CONF_API_KEY: "secret-key",
    }
    with patch(_PROBE_PI, return_value="out_of_coverage"):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], submitted,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "out_of_coverage"}
    suggested = _suggested_values(result["data_schema"])
    assert suggested[CONF_ENABLE_PI] is True
    assert suggested[CONF_COUNTRY] == "AT"
    assert suggested[CONF_API_KEY] == "secret-key"
    assert suggested[CONF_UPDATE_INTERVAL] == 90
    assert suggested[CONF_SELECTED_SPECIES] == ["grass"]
