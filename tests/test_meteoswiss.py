"""Unit tests for the MeteoSwiss source client (mocked, offline)."""

from __future__ import annotations

import asyncio

from custom_components.pollenwatch.sources.base import SourceStatus
from custom_components.pollenwatch.sources.meteoswiss import (
    STATIONS,
    MeteoSwissSource,
    nearest_station,
)

# Bern (-> station pbe) vs Graz (Austria, out of coverage).
_BERN = (46.9503, 7.4247)
_GRAZ = (47.0707, 15.4395)

# Real header column order; semicolon-delimited. Columns after the timestamp:
# birch, grass, alder, hazel, beech, ash, oak (only the first three are canonical).
_HEADER = (
    "station_abbr;reference_timestamp;"
    "kabetuh0;khpoach0;kaalnuh0;kacoryh0;kafaguh0;kafraxh0;kaquerh0"
)
_CSV = "\n".join(
    [
        _HEADER,
        "PBE;28.05.2026 21:00;0;174;0;9;0;0;0",
        "PBE;28.05.2026 22:00;1;211;0;9;0;0;0",
        "PBE;28.05.2026 23:00;0;366;2;9;0;0;0",
    ]
)


def _transport(status: int, text: str):
    async def transport(url: str, timeout: float):
        return status, text

    return transport


def test_nearest_station_picks_closest():
    assert nearest_station(*_BERN) == "pbe"
    assert nearest_station(46.0, 8.96) == "plu"  # Lugano


def test_parse_maps_three_canonical_and_ignores_others():
    source = MeteoSwissSource(*_BERN, async_transport=_transport(200, _CSV))
    result = asyncio.run(source.async_fetch())

    assert result.ok
    assert result.source == "meteoswiss"
    assert result.timezone == "UTC"
    assert result.station == "Bern (PBE)"
    # Only the three overlapping canonical allergens; hazel/beech/ash/oak ignored.
    assert set(result.allergens) == {"birch", "grass", "alder"}

    grass = result.allergens["grass"]
    assert grass.unit == "grains/m³"
    assert grass.current == 366.0  # latest row
    assert grass.values == [174.0, 211.0, 366.0]
    assert grass.native is None
    assert result.allergens["alder"].current == 2.0
    assert result.allergens["birch"].current == 0.0


def test_parse_timestamps_are_iso_utc():
    source = MeteoSwissSource(*_BERN, async_transport=_transport(200, _CSV))
    result = asyncio.run(source.async_fetch())
    assert result.times == [
        "2026-05-28T21:00:00",
        "2026-05-28T22:00:00",
        "2026-05-28T23:00:00",
    ]
    assert result.current_time == "2026-05-28T23:00:00"


def test_current_uses_latest_non_null():
    # Last row's grass cell is empty -> current falls back to the prior reading.
    csv = "\n".join(
        [
            _HEADER,
            "PBE;29.05.2026 00:00;0;120;0;0;0;0;0",
            "PBE;29.05.2026 01:00;0;;0;0;0;0;0",
        ]
    )
    source = MeteoSwissSource(*_BERN, async_transport=_transport(200, csv))
    result = asyncio.run(source.async_fetch())
    grass = result.allergens["grass"]
    assert grass.values == [120.0, None]
    assert grass.current == 120.0  # latest non-null, not None


def test_allergen_filtering_limits_series():
    source = MeteoSwissSource(
        *_BERN, ["grass"], async_transport=_transport(200, _CSV)
    )
    result = asyncio.run(source.async_fetch())
    assert set(result.allergens) == {"grass"}


def test_self_baselining_capability_flags():
    source = MeteoSwissSource(*_BERN)
    assert source.supports_history is True
    assert source.provides_history_series is True  # recent CSV carries history


def test_header_only_csv_yields_no_allergens():
    # An empty file (header only) is covered-but-no-data: no crash, no bogus 0.
    source = MeteoSwissSource(*_BERN, async_transport=_transport(200, _HEADER))
    result = asyncio.run(source.async_fetch())
    assert result.ok
    assert result.allergens == {}
    assert result.current_time is None
    assert result.station == "Bern (PBE)"


def test_non_swiss_location_is_out_of_coverage_without_fetch():
    async def must_not_call(url: str, timeout: float):
        raise AssertionError("transport should not be called outside Switzerland")

    source = MeteoSwissSource(*_GRAZ, async_transport=must_not_call)
    assert source.station is None
    result = asyncio.run(source.async_fetch())
    assert result.status is SourceStatus.OUT_OF_COVERAGE
    assert result.allergens == {}


def test_pinned_station_honoured_when_valid():
    source = MeteoSwissSource(*_BERN, station="pzh")  # Zürich, pinned
    assert source.station == "pzh"
    assert source.station in STATIONS
