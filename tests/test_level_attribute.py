"""v2.1+: raw sensors expose normalised severity (level + level_label) so
downstream consumers (e.g. the bundled card, the Oriel dashboard) read the
integration's own bucketing instead of re-deriving thresholds.

The Oriel-side drift bug (PI=2/Google UPI=3/DWD=2.0/tree=75 all rendered
"high" while PW's analytics rendered "low") was the trigger; the tests here
are the regression guard against a similar drift sneaking back inside PW —
either in the bucketing function or in the sensor wiring.

Assertions are KEYED TO ``level_for_source()`` and ``level_label()`` rather
than hardcoded ints/strings: if a future PW change moves a threshold, both
sides of the assertion shift together and the test still passes. What it
catches is *disagreement between the function and the entity attribute*,
which is the wiring class of bug.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pollenwatch.analytics import (
    LEVEL_LABELS,
    level_for_source,
    level_label,
)
from custom_components.pollenwatch.const import (
    CONF_SELECTED_SPECIES,
    CONF_SOURCES,
    DOMAIN,
    SOURCE_DWD,
    SOURCE_GOOGLE,
    SOURCE_OPEN_METEO,
    SOURCE_POLLENINFORMATION,
    new_sources_config,
)
from custom_components.pollenwatch.sources.base import AllergenSeries
from custom_components.pollenwatch.sources.open_meteo import OpenMeteoSource

# ---------------------------------------------------------------------------
# Layer 1: function correctness on the drift values that prompted v2.1
# ---------------------------------------------------------------------------

DRIFT_CASES = [
    # (source_key, species, series, expected_level, label_when_low)
    #
    # PI 0–4 index — `current=2` is Austrian "Mittel" → level 1 (low). The
    # Oriel dashboard had been bucketing this as `high`.
    pytest.param(
        SOURCE_POLLENINFORMATION,
        "grass",
        AllergenSeries(allergen="grass", unit=None, current=2.0,
                       values=[2.0], native=None),
        1,
        id="pi_index_2_is_low_not_high",
    ),
    # Google UPI 0–5 — UPI=3 is "Moderate" → level 1 (low). Oriel bucketed
    # this as `high`; PW's google_collapse honestly puts it at 1 because
    # Google reserves High/Very High (4/5) for the elevated tier.
    pytest.param(
        SOURCE_GOOGLE,
        "grass",
        AllergenSeries(allergen="grass", unit=None, current=3,
                       values=[3], native=None),
        1,
        id="google_upi_3_is_low_not_high",
    ),
    # DWD 7-point string — `native="2"` is mid (midpoint float 2.0 in state)
    # → level 1 (low). Oriel was numerically `n >= 2 → high`; PW's
    # dwd_collapse correctly says level 1 because only "2-3"/"3" → 2.
    pytest.param(
        SOURCE_DWD,
        "grass",
        AllergenSeries(allergen="grass", unit=None, current=2.0,
                       values=[2.0], native="2"),
        1,
        id="dwd_string_2_is_low_not_high",
    ),
    # Grains/m³ tree species (birch threshold (10, 100)) — value 75 → level
    # 1 (low). Oriel was a universal grains/m³ `>= 50 → high`; PW's
    # bucket_level for trees uses peak=100 not 50, so 75 is `low`.
    pytest.param(
        SOURCE_OPEN_METEO,
        "birch",
        AllergenSeries(allergen="birch", unit="grains/m³", current=75.0,
                       values=[75.0], native=None),
        1,
        id="grains_per_m3_tree_75_is_low_not_high",
    ),
    # Grains/m³ grass species (grass threshold (3, 50)) — value 30 → level
    # 1 (low). This case agrees with Oriel's universal ≥50 cutoff but is
    # included as a sanity check that the grass bracket still rounds-trips.
    pytest.param(
        SOURCE_OPEN_METEO,
        "grass",
        AllergenSeries(allergen="grass", unit="grains/m³", current=30.0,
                       values=[30.0], native=None),
        1,
        id="grains_per_m3_grass_30_is_low",
    ),
]


@pytest.mark.parametrize(
    ("source_key", "species", "series", "expected_level"),
    [(c.values[0], c.values[1], c.values[2], c.values[3]) for c in DRIFT_CASES],
    ids=[c.id for c in DRIFT_CASES],
)
def test_level_for_source_drift_cases(
    source_key: str,
    species: str,
    series: AllergenSeries,
    expected_level: int,
) -> None:
    """Each drift value buckets to `low` (level 1) per PW's own bucketing.

    Pinning ``expected_level=1`` for the five cases that prompted the v2.1
    work — if any of them moves to `high` because a threshold was edited
    internally, this test surfaces the change as a CI failure rather than
    letting it ship silently.
    """
    assert level_for_source(source_key, species, series) == expected_level


def test_level_label_round_trip():
    """The label vocabulary matches the consensus enum exactly."""
    assert level_label(0) == "none"
    assert level_label(1) == "low"
    assert level_label(2) == "high"
    assert level_label(None) is None
    # LEVEL_LABELS is the shared mapping; the function reads it.
    assert LEVEL_LABELS == {0: "none", 1: "low", 2: "high"}


# ---------------------------------------------------------------------------
# Layer 2: sensor-wiring — the raw entity's attrs equal what the function
# would return, NOT a hardcoded constant. Catches a future refactor that
# silently desynchronises the entity from the bucketing function.
# ---------------------------------------------------------------------------

_SESSION = "custom_components.pollenwatch.coordinator.async_get_clientsession"
_FETCH = "custom_components.pollenwatch.sources.open_meteo.OpenMeteoSource.async_fetch"


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id="47.0700_15.4400",
        title="PollenWatch (47.070, 15.440)",
        data={
            CONF_LATITUDE: 47.07,
            CONF_LONGITUDE: 15.44,
            CONF_SELECTED_SPECIES: ["birch", "grass"],
        },
        options={CONF_SOURCES: new_sources_config()},
    )


def _payload() -> dict:
    """Open-Meteo payload tuned to land birch in the `low` bucket (75
    grains/m³ — between birch onset 10 and peak 100) and grass in `low` too
    (30 — between grass onset 3 and peak 50)."""
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
            "birch_pollen": 75.0,
            "grass_pollen": 30.0,
        },
        "hourly": {
            "time": times,
            "birch_pollen": [70.0, 75.0, 50.0, 60.0],
            "grass_pollen": [25.0, 30.0, 20.0, 22.0],
        },
    }


def _result():
    return OpenMeteoSource(47.07, 15.44, ["birch", "grass"]).parse(_payload())


async def test_raw_sensor_exposes_level_and_label_from_level_for_source(
    hass: HomeAssistant,
) -> None:
    """End-to-end: the entity's level/level_label attributes equal what
    ``level_for_source()`` + ``level_label()`` would compute for the same
    (source, species, series) tuple.

    Function-keyed (not constant-keyed): the assertion compares the entity
    attribute against a fresh call to the same function the entity is wired
    to. A future threshold edit moves both sides together. A future wiring
    regression breaks this test.
    """
    entry = _entry()
    entry.add_to_hass(hass)

    with (
        patch(_SESSION, return_value=object()),
        patch(_FETCH, new=AsyncMock(return_value=_result())),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

    result = _result()  # second realisation is identical to what HA stored
    for species in ("birch", "grass"):
        state = hass.states.get(f"sensor.pollenwatch_open_meteo_{species}")
        assert state is not None, f"no entity for {species}"
        series = result.allergens[species]
        expected_level = level_for_source(SOURCE_OPEN_METEO, species, series)
        expected_label = level_label(expected_level)
        assert state.attributes.get("level") == expected_level, (
            f"{species}: entity level {state.attributes.get('level')} "
            f"!= level_for_source() result {expected_level}"
        )
        assert state.attributes.get("level_label") == expected_label, (
            f"{species}: entity level_label {state.attributes.get('level_label')} "
            f"!= level_label() result {expected_label}"
        )
        # Sanity that we're still in the `low` bucket for the v2.1 drift
        # narrative — not a hardcoded assertion, just a sentinel that
        # something has changed if it ever fails.
        assert expected_label == "low"
