"""Unit tests for the Google Pollen API source client (mocked, offline)."""

from __future__ import annotations

import asyncio

import pytest

from custom_components.pollenwatch.sources.base import (
    SourceAuthError,
    SourceStatus,
    SourceUnavailable,
)
from custom_components.pollenwatch.sources.google import GoogleSource

_GRAZ = (47.0707, 15.4395)


def _payload() -> dict:
    return {
        "regionCode": "AT",
        "dailyInfo": [
            {
                "date": {"year": 2026, "month": 5, "day": 29},
                "plantInfo": [
                    {"code": "GRAMINALES", "inSeason": True,
                     "indexInfo": {"code": "UPI", "value": 4, "category": "High"}},
                    {"code": "BIRCH", "inSeason": False,
                     "indexInfo": {"code": "UPI", "value": 0, "category": "None"}},
                    {"code": "OLIVE", "inSeason": True,
                     "indexInfo": {"code": "UPI", "value": 2, "category": "Low"}},
                    # ASH is not one of our six -> must be ignored
                    {"code": "ASH", "indexInfo": {"code": "UPI", "value": 5}},
                ],
            },
            {
                "date": {"year": 2026, "month": 5, "day": 30},
                "plantInfo": [
                    {"code": "GRAMINALES", "indexInfo": {"code": "UPI", "value": 3}},
                    {"code": "OLIVE", "indexInfo": {"code": "UPI", "value": 1}},
                    # BIRCH absent this day
                ],
            },
        ],
    }


def _transport(status: int, payload: object):
    async def transport(url: str, timeout: float):
        return status, payload

    return transport


def test_capability_flags_consensus_only():
    src = GoogleSource(*_GRAZ, "k")
    assert src.supports_history is False  # licence: no recent_percentile baseline
    assert src.provides_history_series is False


def test_parse_maps_all_canonical_including_olive():
    source = GoogleSource(*_GRAZ, "k", async_transport=_transport(200, _payload()))
    result = asyncio.run(source.async_fetch())

    assert result.ok
    assert result.source == "google"
    assert result.message == "AT"  # regionCode
    # grass/birch/olive present (olive is unique to Google); ASH ignored.
    assert set(result.allergens) == {"grass", "birch", "olive"}

    grass = result.allergens["grass"]
    assert grass.unit is None  # UPI index, not a concentration
    assert grass.current == 4
    assert grass.values == [4, 3]
    olive = result.allergens["olive"]
    assert olive.current == 2
    assert olive.values == [2, 1]


def test_parse_times_and_5day_forecast_alignment():
    source = GoogleSource(*_GRAZ, "k", async_transport=_transport(200, _payload()))
    result = asyncio.run(source.async_fetch())
    assert result.times == ["2026-05-29", "2026-05-30"]
    assert result.current_time == "2026-05-29"
    # birch only reported on day 0 -> aligned series has None for the missing day.
    assert result.allergens["birch"].values == [0, None]
    assert result.allergens["birch"].current == 0


def test_allergen_filtering_drops_unselected():
    source = GoogleSource(
        *_GRAZ, "k", ["grass"], async_transport=_transport(200, _payload())
    )
    result = asyncio.run(source.async_fetch())
    assert set(result.allergens) == {"grass"}


def test_empty_plantinfo_yields_no_allergens():
    payload = {
        "regionCode": "XX",
        "dailyInfo": [{"date": {"year": 2026, "month": 5, "day": 29}, "plantInfo": []}],
    }
    source = GoogleSource(*_GRAZ, "k", async_transport=_transport(200, payload))
    result = asyncio.run(source.async_fetch())
    assert result.ok  # covered, just no pollen plants reported
    assert result.allergens == {}
    assert result.current_time == "2026-05-29"


def test_403_is_auth_error():
    payload = {"error": {"code": 403, "status": "PERMISSION_DENIED", "message": "no"}}
    source = GoogleSource(*_GRAZ, "bad", async_transport=_transport(403, payload))
    with pytest.raises(SourceAuthError):
        asyncio.run(source.async_fetch())


def test_429_is_unavailable():
    source = GoogleSource(
        *_GRAZ, "k", async_transport=_transport(429, {"error": {"code": 429}})
    )
    with pytest.raises(SourceUnavailable):
        asyncio.run(source.async_fetch())


def test_global_no_coverage_gate():
    # Even a far-flung point is fetched (global coverage, no bbox short-circuit):
    # an empty result is OK-with-no-allergens, never out_of_coverage by geometry.
    source = GoogleSource(
        -33.86, 151.21, "k", async_transport=_transport(200, _payload())
    )
    result = asyncio.run(source.async_fetch())
    assert result.status is SourceStatus.OK
