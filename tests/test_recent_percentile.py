"""HA tests for the recent_percentile sensor (Open-Meteo backfill path)."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pollenwatch.const import (
    CONF_SELECTED_SPECIES,
    CONF_SOURCES,
    DOMAIN,
    new_sources_config,
)
from custom_components.pollenwatch.sources.open_meteo import OpenMeteoSource

_SESSION = "custom_components.pollenwatch.coordinator.async_get_clientsession"
_FETCH = "custom_components.pollenwatch.sources.open_meteo.OpenMeteoSource.async_fetch"
_ENTITY = "sensor.pollenwatch_open_meteo_grass_recent_percentile"


def _backfill_result(days: int, today_value: float):
    """OM SourceResult: `days` daily peaks ending today; today at today_value."""
    today = dt_util.now().date()
    times, vals = [], []
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        times.append(f"{d.isoformat()}T12:00")
        vals.append(today_value if i == days - 1 else 1.0)
    payload = {
        "latitude": 47.1,
        "longitude": 15.4,
        "timezone": "Europe/Vienna",
        "elevation": 363.0,
        "hourly_units": {"grass_pollen": "grains/m³"},
        "current": {"time": f"{today.isoformat()}T12:00", "grass_pollen": today_value},
        "hourly": {"time": times, "grass_pollen": vals},
    }
    return OpenMeteoSource(47.07, 15.44, ["grass"]).parse(payload)


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id="47.0700_15.4400",
        data={CONF_LATITUDE: 47.07, CONF_LONGITUDE: 15.44, CONF_SELECTED_SPECIES: ["grass"]},
        options={CONF_SELECTED_SPECIES: ["grass"], CONF_SOURCES: new_sources_config()},
    )


async def test_recent_percentile_value_with_full_backfill(
    hass: HomeAssistant,
) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    # 20 days, today the highest -> high percentile.
    with (
        patch(_SESSION, return_value=object()),
        patch(_FETCH, new=AsyncMock(return_value=_backfill_result(20, 50.0))),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_ENTITY)
    assert state is not None
    assert float(state.state) > 90  # today is the max of 20 days
    assert state.attributes["unit_of_measurement"] == "%"
    assert state.attributes["history_status"] == "ok"
    assert state.attributes["days_of_history"] == 20


async def test_recent_percentile_insufficient_history(hass: HomeAssistant) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    # Only 5 days < MIN_PERCENTILE_DAYS -> insufficient, no number.
    with (
        patch(_SESSION, return_value=object()),
        patch(_FETCH, new=AsyncMock(return_value=_backfill_result(5, 50.0))),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_ENTITY)
    assert state is not None
    assert state.state in ("unknown", "unavailable")
    assert state.attributes["history_status"] == "insufficient_history"
    assert state.attributes["days_of_history"] == 5
