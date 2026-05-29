"""Unit tests for the polleninformation.at source client.

All HTTP is mocked via the injectable async transport; a placeholder API key is
used (never the real one). These run offline.
"""

from __future__ import annotations

import asyncio

import pytest

from custom_components.pollenwatch.sources.base import (
    SourceAuthError,
    SourceStatus,
    SourceUnavailable,
)
from custom_components.pollenwatch.sources.polleninformation import (
    PolleninformationSource,
)

_KEY = "test-key-placeholder"


def _payload() -> dict:
    return {
        "contamination": [
            {
                "poll_id": 5,
                "poll_title": "grasses (Poaceae)",
                "contamination_1": 3,
                "contamination_2": 3,
                "contamination_3": 2,
                "contamination_4": 1,
            },
            {
                "poll_id": 1,
                "poll_title": "alder (Alnus)",
                "contamination_1": 1,
                "contamination_2": 0,
                "contamination_3": 0,
                "contamination_4": 0,
            },
            {  # not one of PollenWatch's canonical species -> ignored
                "poll_id": 23,
                "poll_title": "fungal spores (Alternaria)",
                "contamination_1": 2,
                "contamination_2": 2,
                "contamination_3": 1,
                "contamination_4": 1,
            },
        ],
        "allergyrisk": {"allergyrisk_1": 8},
        "allergyrisk_hourly": {},
    }


def _async_transport(status: int, payload: object):
    async def transport(url: str, timeout: float):
        return status, payload

    return transport


def _source(transport, allergens=("grass", "alder", "birch")):
    return PolleninformationSource(
        47.0707, 15.4395, "AT", _KEY, list(allergens), async_transport=transport
    )


def test_success_parses_daily_index():
    source = _source(_async_transport(200, _payload()))
    result = asyncio.run(source.async_fetch())

    assert result.ok
    assert result.status is SourceStatus.OK
    assert result.source == "polleninformation"
    # grass + alder mapped & requested; Alternaria dropped; birch absent in payload
    assert set(result.allergens) == {"grass", "alder"}
    grass = result.allergens["grass"]
    assert grass.current == 3
    assert grass.values == [3, 3, 2, 1]
    assert grass.unit is None  # ordinal index, not grains/m³
    assert len(result.times) == 4
    assert result.current_time == result.times[0]
    assert result.forecast_split == 0


def test_unmapped_species_are_ignored():
    source = _source(_async_transport(200, _payload()), allergens=("grass",))
    result = asyncio.run(source.async_fetch())
    assert set(result.allergens) == {"grass"}


def test_out_of_coverage_returns_status_not_raise():
    source = _source(
        _async_transport(200, {"error": "No data available for this location"})
    )
    result = asyncio.run(source.async_fetch())
    assert result.status is SourceStatus.OUT_OF_COVERAGE
    assert not result.ok
    assert result.allergens == {}


def test_http_401_raises_auth_error():
    source = _source(_async_transport(401, {}))
    with pytest.raises(SourceAuthError):
        asyncio.run(source.async_fetch())


def test_api_key_error_body_raises_auth_error():
    source = _source(_async_transport(200, {"error": "Invalid API key"}))
    with pytest.raises(SourceAuthError):
        asyncio.run(source.async_fetch())


def test_retry_then_succeed():
    calls = {"n": 0}

    async def flaky(url: str, timeout: float):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("temporary")
        return 200, _payload()

    source = _source(flaky)
    source.retry_delay = 0
    result = asyncio.run(source.async_fetch())
    assert calls["n"] == 2
    assert result.ok


def test_retry_exhaustion_raises_unavailable():
    async def always_fails(url: str, timeout: float):
        raise ConnectionError("down")

    source = _source(always_fails)
    source.retry_delay = 0
    with pytest.raises(SourceUnavailable):
        asyncio.run(source.async_fetch())
