"""Unit tests for the DWD source client (mocked, offline)."""

from __future__ import annotations

import asyncio

from custom_components.pollenwatch.sources.base import SourceStatus
from custom_components.pollenwatch.sources.dwd import DwdSource

# In-Germany coords (Freiburg-ish) vs Graz (Austria, out of coverage).
_DE = (48.0, 7.85)
_GRAZ = (47.0707, 15.4395)


def _payload(region_id: int = 111) -> dict:
    return {
        "legend": {},
        "content": [
            {
                "region_id": 110,
                "region_name": "Baden-Württemberg",
                "partregion_id": region_id,
                "partregion_name": "Oberrhein",
                "Pollen": {
                    "Graeser": {"today": "2-3", "tomorrow": "2", "dayafter_to": "1"},
                    "Birke": {"today": "0", "tomorrow": "0", "dayafter_to": "0"},
                    "Erle": {"today": "-1", "tomorrow": "-1", "dayafter_to": "-1"},
                    "Ambrosia": {"today": "1-2", "tomorrow": "1", "dayafter_to": "0"},
                    "Esche": {"today": "1", "tomorrow": "0", "dayafter_to": "0"},
                },
            }
        ],
    }


def _transport(status: int, payload: object):
    async def transport(url: str, timeout: float):
        return status, payload

    return transport


def test_parse_maps_species_and_keeps_native():
    source = DwdSource(
        *_DE, 111, ["grass", "birch", "alder", "ragweed", "olive"],
        async_transport=_transport(200, _payload()),
    )
    result = asyncio.run(source.async_fetch())

    assert result.ok
    assert result.source == "dwd"
    # grass: "2-3" -> 2.5 float, native kept; olive absent (DWD has none);
    # alder omitted (today "-1"); ragweed "1-2" -> 1.5
    assert set(result.allergens) == {"grass", "birch", "ragweed"}
    grass = result.allergens["grass"]
    assert grass.current == 2.5
    assert grass.native == "2-3"
    assert grass.values == [2.5, 2.0, 1.0]
    assert grass.unit is None
    assert result.allergens["birch"].current == 0.0
    assert result.allergens["ragweed"].current == 1.5


def test_no_data_today_omits_allergen():
    source = DwdSource(
        *_DE, 111, ["alder"], async_transport=_transport(200, _payload())
    )
    result = asyncio.run(source.async_fetch())
    assert "alder" not in result.allergens  # Erle today is "-1"


def test_non_german_location_is_out_of_coverage_without_fetch():
    async def must_not_call(url: str, timeout: float):
        raise AssertionError("transport should not be called outside Germany")

    source = DwdSource(*_GRAZ, 111, ["grass"], async_transport=must_not_call)
    result = asyncio.run(source.async_fetch())
    assert result.status is SourceStatus.OUT_OF_COVERAGE
    assert result.allergens == {}


def test_region_not_found_is_out_of_coverage():
    source = DwdSource(
        *_DE, 999, ["grass"], async_transport=_transport(200, _payload(region_id=111))
    )
    result = asyncio.run(source.async_fetch())
    assert result.status is SourceStatus.OUT_OF_COVERAGE


def test_region_minus_one_is_valid_brandenburg_berlin():
    # partregion_id -1 is a real region, not a no-data marker.
    payload = _payload(region_id=-1)
    source = DwdSource(
        52.5, 13.4, -1, ["grass"], async_transport=_transport(200, payload)
    )
    result = asyncio.run(source.async_fetch())
    assert result.ok
    assert result.allergens["grass"].current == 2.5
