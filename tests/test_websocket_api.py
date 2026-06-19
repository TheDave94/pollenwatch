"""Tests for the pollenwatch/config WebSocket API endpoint (v2.4+).

The endpoint exists so the bundled Lovelace card can fetch the user's
selected species + default layout without scraping ``hass.states`` or
forcing the user into YAML. Three things matter:

1. Configured entry → payload mirrors options.
2. Pre-v2.4 entry missing ``CONF_DEFAULT_LAYOUT`` → payload fills with
   the safe baseline ('gauge'). Tested without an entry-version bump.
3. Unknown / foreign entry_id → clean WS error, never a 500.

Test strategy: the handler is invoked directly with a stand-in
``ActiveConnection`` that captures the response. This sidesteps the
full aiohttp + pycares stack (which would otherwise leak a daemon
thread the pytest_homeassistant_custom_component cleanup fixture flags
as a failure). The handler's contract is purely (hass, connection, msg)
→ side-effects on connection, so direct invocation is the faithful
unit-test surface.
"""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pollenwatch.const import (
    CONF_DEFAULT_LAYOUT,
    CONF_SELECTED_SPECIES,
    CONF_SOURCES,
    DOMAIN,
    LAYOUT_BARS,
    LAYOUT_GAUGE,
    new_sources_config,
)
from custom_components.pollenwatch.websocket_api import _ws_get_config, async_register


class _CapturingConnection:
    """Minimal ActiveConnection stand-in: captures send_result / send_error.

    The real ``websocket_api.ActiveConnection`` carries permissions, user,
    refresh-token, and a JSON-writer callback. The handler under test only
    invokes ``send_result`` and ``send_error`` and reads no other attribute,
    so this stub is the entire contract.
    """

    def __init__(self) -> None:
        self.results: list[tuple[int, Any]] = []
        self.errors: list[tuple[int, str, str]] = []

    def send_result(self, msg_id: int, result: Any) -> None:
        self.results.append((msg_id, result))

    def send_error(self, msg_id: int, code: str, message: str) -> None:
        self.errors.append((msg_id, code, message))


def _entry(options_overrides: dict | None = None) -> MockConfigEntry:
    options = {
        CONF_SELECTED_SPECIES: ["grass", "birch"],
        CONF_SOURCES: new_sources_config(),
    }
    if options_overrides:
        options.update(options_overrides)
    return MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id="47.0700_15.4400",
        title="PollenWatch (47.070, 15.440)",
        data={
            CONF_LATITUDE: 47.07,
            CONF_LONGITUDE: 15.44,
            CONF_SELECTED_SPECIES: ["grass", "birch"],
        },
        options=options,
    )


async def test_ws_config_returns_species_and_layout(hass: HomeAssistant) -> None:
    """A v2.4+ entry with the option set surfaces both fields verbatim."""
    entry = _entry(options_overrides={CONF_DEFAULT_LAYOUT: LAYOUT_BARS})
    entry.add_to_hass(hass)

    connection = _CapturingConnection()
    _ws_get_config(hass, connection, {"id": 1, "entry_id": entry.entry_id})

    assert connection.errors == []
    assert connection.results == [
        (
            1,
            {
                "selected_species": ["grass", "birch"],
                "default_layout": LAYOUT_BARS,
            },
        )
    ]


async def test_ws_config_falls_back_to_gauge_for_legacy_entry(
    hass: HomeAssistant,
) -> None:
    """Pre-v2.4 entry has no CONF_DEFAULT_LAYOUT in options. The handler must
    return 'gauge' — the card's no-change-on-upgrade baseline — without
    requiring an entry-version bump or migration."""
    entry = _entry()  # no override → key absent
    assert CONF_DEFAULT_LAYOUT not in entry.options
    entry.add_to_hass(hass)

    connection = _CapturingConnection()
    _ws_get_config(hass, connection, {"id": 7, "entry_id": entry.entry_id})

    assert connection.errors == []
    assert connection.results == [
        (
            7,
            {
                "selected_species": ["grass", "birch"],
                "default_layout": LAYOUT_GAUGE,
            },
        )
    ]


async def test_ws_config_unknown_entry_id_returns_clean_error(
    hass: HomeAssistant,
) -> None:
    """An entry_id the integration doesn't own produces a WS error frame,
    not a server-side exception. The card surfaces this as a soft fallback."""
    connection = _CapturingConnection()
    _ws_get_config(
        hass, connection, {"id": 42, "entry_id": "this-entry-does-not-exist"}
    )

    assert connection.results == []
    assert len(connection.errors) == 1
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 42
    assert code == "not_found"


async def test_ws_config_rejects_foreign_domain_entry(hass: HomeAssistant) -> None:
    """A ConfigEntry that belongs to another integration must not leak its
    options through this endpoint — same not_found error path as a
    fully-unknown id."""
    foreign = MockConfigEntry(domain="other_integration", data={})
    foreign.add_to_hass(hass)

    connection = _CapturingConnection()
    _ws_get_config(hass, connection, {"id": 5, "entry_id": foreign.entry_id})

    assert connection.results == []
    assert len(connection.errors) == 1
    assert connection.errors[0][1] == "not_found"


async def test_ws_config_recovers_from_unknown_layout_value(
    hass: HomeAssistant,
) -> None:
    """A layout value not in ALLOWED_LAYOUTS (e.g. hand-edited storage) must
    be normalised to the safe baseline rather than passed through. The card
    should never receive a layout it cannot render."""
    entry = _entry(options_overrides={CONF_DEFAULT_LAYOUT: "spinner"})
    entry.add_to_hass(hass)

    connection = _CapturingConnection()
    _ws_get_config(hass, connection, {"id": 9, "entry_id": entry.entry_id})

    assert connection.errors == []
    assert connection.results[0][1]["default_layout"] == LAYOUT_GAUGE


async def test_ws_register_is_idempotent(hass: HomeAssistant) -> None:
    """async_register is called once per HA boot but the integration's
    async_setup_entry triggers it on every config-entry load. The hass.data
    flag must make subsequent calls no-ops; calling it twice in a row must
    not raise."""
    async_register(hass)
    async_register(hass)  # must not raise / re-register
