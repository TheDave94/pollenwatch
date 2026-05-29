"""Unit tests for the ePIN (Bavaria) source client (mocked, offline)."""

from __future__ import annotations

import asyncio

from custom_components.pollenwatch.sources.base import SourceStatus
from custom_components.pollenwatch.sources.epin import (
    STATIONS,
    EpinSource,
    nearest_station,
)

# Munich (-> station DEMUNC) vs Graz (Austria, out of coverage).
_MUNICH = (48.13, 11.56)
_GRAZ = (47.0707, 15.4395)

_T1 = 1780000000  # window start
_T2 = _T1 + 10800  # +3 h (next 3-hourly window)


def _payload() -> dict:
    return {
        "from": _T1,
        "to": _T2 + 10800,
        "measurements": [
            {
                "polle": "Poaceae",
                "location": "DEMUNC",
                "data": [
                    {"from": _T1, "to": _T2, "value": 10.0, "algorithm": "PomoAIv1"},
                    {"from": _T2, "to": _T2 + 10800, "value": 26.97, "algorithm": "x"},
                ],
            },
            {  # birch only reports the earlier window
                "polle": "Betula",
                "location": "DEMUNC",
                "data": [{"from": _T1, "to": _T2, "value": 2.0}],
            },
            {
                "polle": "Alnus",
                "location": "DEMUNC",
                "data": [{"from": _T2, "to": _T2 + 10800, "value": 0.0}],
            },
            {  # hazel — not in our six, must be ignored
                "polle": "Corylus",
                "location": "DEMUNC",
                "data": [{"from": _T2, "to": _T2 + 10800, "value": 99.0}],
            },
            {  # a different station — must be ignored
                "polle": "Poaceae",
                "location": "DEHOF",
                "data": [{"from": _T2, "to": _T2 + 10800, "value": 500.0}],
            },
        ],
    }


def _transport(status: int, payload: object):
    async def transport(url: str, timeout: float):
        return status, payload

    return transport


def test_manual_stations_are_excluded():
    # Only the 8 automatic stations are bundled; the 4 "ePIN Manu" are not.
    assert set(STATIONS) == {
        "DEALTO", "DEFEUC", "DEGARM", "DEHOF",
        "DEMARK", "DEMIND", "DEMUNC", "DEVIEC",
    }
    assert "DEBAMB" not in STATIONS  # Bamberg is manual


def test_nearest_station_picks_automatic_only():
    assert nearest_station(*_MUNICH) == "DEMUNC"
    # Near Bamberg (manual station) -> nearest *automatic* station instead.
    picked = nearest_station(49.9, 10.89)
    assert picked in STATIONS
    assert picked != "DEBAMB"


def test_parse_maps_canonical_and_filters_station():
    source = EpinSource(*_MUNICH, async_transport=_transport(200, _payload()))
    result = asyncio.run(source.async_fetch())

    assert result.ok
    assert result.source == "epin"
    assert result.timezone == "UTC"
    assert result.station == "München (DEMUNC)"
    # 5 canonical possible; this payload has grass/birch/alder. Corylus ignored,
    # DEHOF (other station) ignored, olive never present (ePIN has none).
    assert set(result.allergens) == {"grass", "birch", "alder"}

    grass = result.allergens["grass"]
    assert grass.unit == "grains/m³"
    assert grass.current == 26.97  # latest window
    assert grass.values == [10.0, 26.97]


def test_current_uses_latest_non_null_across_union_axis():
    # birch only reported the first window; aligned to the 2-window axis its
    # latest cell is None, so current falls back to the earlier reading.
    source = EpinSource(*_MUNICH, async_transport=_transport(200, _payload()))
    result = asyncio.run(source.async_fetch())
    birch = result.allergens["birch"]
    assert birch.values == [2.0, None]
    assert birch.current == 2.0


def test_olive_never_offered():
    source = EpinSource(
        *_MUNICH, ["olive", "grass"], async_transport=_transport(200, _payload())
    )
    # olive is filtered out at construction (ePIN doesn't measure it).
    assert "olive" not in source.allergens
    result = asyncio.run(source.async_fetch())
    assert "olive" not in result.allergens


def test_recorder_baselining_capability_flags():
    source = EpinSource(*_MUNICH)
    assert source.supports_history is True
    assert source.provides_history_series is False  # ~7 days -> recorder


def test_empty_measurement_set_yields_no_allergens():
    # A quiet day (or a station with nothing reported) returns an empty
    # measurement set: the source must yield no raw value — not crash, and not
    # fabricate a bogus 0. ("3 windows today" makes "0 windows" plausible.)
    source = EpinSource(
        *_MUNICH, async_transport=_transport(200, {"from": 1, "to": 2, "measurements": []})
    )
    result = asyncio.run(source.async_fetch())
    assert result.ok  # covered location, simply no readings right now
    assert result.allergens == {}
    assert result.current_time is None
    assert result.times == []


def test_station_records_with_empty_data_have_no_current():
    # Station present but its data array is empty -> current is None (unavailable),
    # never a fabricated 0.
    payload = {
        "measurements": [{"polle": "Poaceae", "location": "DEMUNC", "data": []}]
    }
    source = EpinSource(*_MUNICH, async_transport=_transport(200, payload))
    result = asyncio.run(source.async_fetch())
    assert result.allergens["grass"].current is None
    assert result.allergens["grass"].values == []


def test_non_bavarian_location_is_out_of_coverage_without_fetch():
    async def must_not_call(url: str, timeout: float):
        raise AssertionError("transport should not be called outside Bavaria")

    source = EpinSource(*_GRAZ, async_transport=must_not_call)
    assert source.station is None
    result = asyncio.run(source.async_fetch())
    assert result.status is SourceStatus.OUT_OF_COVERAGE
    assert result.allergens == {}
