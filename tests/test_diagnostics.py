"""Diagnostics — the config-entry dump must redact location AND credentials.

Drives a real setup (Open-Meteo's fetch mocked) so diagnostics run against live
``runtime_data`` coordinators, then asserts: coordinates redacted from data;
a source ``api_key`` redacted from the nested options; and each coordinator is
summarised (status + per-allergen counts) without leaking location.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pollenwatch.const import (
    CONF_ALLERGENS,
    CONF_API_KEY,
    CONF_ENABLED,
    CONF_SOURCES,
    DOMAIN,
    SOURCE_GOOGLE,
    SOURCE_OPEN_METEO,
    new_sources_config,
)
from custom_components.pollenwatch.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.pollenwatch.sources.open_meteo import OpenMeteoSource

_SESSION = "custom_components.pollenwatch.coordinator.async_get_clientsession"
_FETCH = "custom_components.pollenwatch.sources.open_meteo.OpenMeteoSource.async_fetch"


def _payload() -> dict:
    times = ["2026-05-29T00:00", "2026-05-29T12:00", "2026-05-30T06:00"]
    return {
        "latitude": 47.1,
        "longitude": 15.4,
        "timezone": "Europe/Vienna",
        "elevation": 363.0,
        "hourly_units": {"grass_pollen": "grains/m³", "birch_pollen": "grains/m³"},
        "current": {"time": "2026-05-29T12:00", "grass_pollen": 20.8, "birch_pollen": 0.1},
        "hourly": {
            "time": times,
            "grass_pollen": [10.0, 20.8, 5.0],
            "birch_pollen": [0.0, 0.1, 0.0],
        },
    }


def _result():
    return OpenMeteoSource(47.07, 15.44, ["grass", "birch"]).parse(_payload())


def _entry() -> MockConfigEntry:
    # Google is disabled (no fetch) but carries an api_key in options — the
    # diagnostics must redact it.
    sources = new_sources_config()
    sources[SOURCE_GOOGLE] = {CONF_ENABLED: False, CONF_API_KEY: "secret-key"}
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
        options={CONF_SOURCES: sources},
    )


async def test_diagnostics_redacts_location_and_credentials(
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

        diag = await async_get_config_entry_diagnostics(hass, entry)

    # Location redacted in entry data.
    assert diag["entry"]["data"][CONF_LATITUDE] == REDACTED
    assert diag["entry"]["data"][CONF_LONGITUDE] == REDACTED

    # Nested credential redacted in options (recursive redaction).
    assert (
        diag["entry"]["options"][CONF_SOURCES][SOURCE_GOOGLE][CONF_API_KEY]
        == REDACTED
    )

    # Open-Meteo coordinator summarised, OK, location-free per-allergen view.
    om = diag["coordinators"][SOURCE_OPEN_METEO]
    assert om["last_update_success"] is True
    result = om["result"]
    assert result["status"] == "ok"
    assert set(result["allergens"]) == {"grass", "birch"}
    assert "latitude" not in result
    assert result["allergens"]["grass"]["unit"] == "grains/m³"
