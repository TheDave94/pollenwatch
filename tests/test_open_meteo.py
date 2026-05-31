"""Unit tests for the Open-Meteo (CAMS) source client.

All HTTP is mocked via the source's injectable transport, so these tests run
offline and deterministically.
"""

from __future__ import annotations

import asyncio
import urllib.error

import pytest

from custom_components.pollenwatch.sources.base import (
    SourceResponseError,
    SourceStatus,
    SourceUnavailable,
)
from custom_components.pollenwatch.sources.open_meteo import OpenMeteoSource


def _european_payload() -> dict:
    """A trimmed but realistic successful Open-Meteo response.

    Coordinates are snapped (47.0707 -> 47.1, 15.4395 -> 15.4). The grass
    series ends in a ``None`` to mirror the forecast horizon running out.
    """
    times = [
        "2026-05-29T12:00",
        "2026-05-29T13:00",
        "2026-05-29T14:00",
        "2026-05-29T15:00",
    ]
    return {
        "latitude": 47.1,
        "longitude": 15.4,
        "timezone": "Europe/Vienna",
        "elevation": 363.0,
        "hourly_units": {"grass_pollen": "grains/m³", "birch_pollen": "grains/m³"},
        "current": {"time": "2026-05-29T14:00", "grass_pollen": 20.8, "birch_pollen": 0.1},
        "hourly": {
            "time": times,
            "grass_pollen": [18.0, 19.5, 20.8, None],
            "birch_pollen": [0.0, 0.1, 0.1, 0.0],
        },
    }


def _transport_returning(status: int, payload: object):
    """Build a transport that records calls and returns a fixed response."""
    calls: list[tuple[str, float]] = []

    def transport(url: str, timeout: float):
        calls.append((url, timeout))
        return status, payload

    transport.calls = calls  # type: ignore[attr-defined]
    return transport


def test_success_for_european_coords_parses_series():
    source = OpenMeteoSource(
        47.0707, 15.4395, ["grass", "birch"],
        transport=_transport_returning(200, _european_payload()),
    )
    result = source.fetch()

    assert result.ok
    assert result.status is SourceStatus.OK
    assert result.source == "open_meteo"
    # snapped coordinates surfaced and shift computed
    assert result.snapped_lat == 47.1
    assert result.snapped_lon == 15.4
    assert result.coordinate_shift_km is not None
    assert 3.0 < result.coordinate_shift_km < 6.0
    # both requested allergens present with aligned values + current
    assert set(result.allergens) == {"grass", "birch"}
    grass = result.allergens["grass"]
    assert grass.unit == "grains/m³"
    assert grass.current == 20.8
    assert grass.values == [18.0, 19.5, 20.8, None]
    # forecast split lands on the "current" timestamp
    assert result.forecast_split == 2


def test_out_of_coverage_returns_status_not_raise():
    transport = _transport_returning(
        400, {"error": True, "reason": "No data is available for this location"}
    )
    source = OpenMeteoSource(40.71, -74.0, ["grass"], transport=transport)

    result = source.fetch()  # must not raise

    assert result.status is SourceStatus.OUT_OF_COVERAGE
    assert not result.ok
    assert result.allergens == {}
    assert result.message and "no data" in result.message.lower()


def test_unexpected_error_reason_raises_response_error():
    transport = _transport_returning(
        400, {"error": True, "reason": "Invalid hourly variable foo_pollen"}
    )
    source = OpenMeteoSource(47.07, 15.44, ["grass"], transport=transport)

    with pytest.raises(SourceResponseError):
        source.fetch()


def test_network_error_retries_once_then_succeeds():
    calls = {"n": 0}

    def flaky_transport(url: str, timeout: float):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.URLError("temporary failure")
        return 200, _european_payload()

    source = OpenMeteoSource(
        47.07, 15.44, ["grass"], transport=flaky_transport, retry_delay=0
    )
    result = source.fetch()

    assert calls["n"] == 2  # initial attempt + one retry
    assert result.ok


def test_network_error_exhausts_retries_and_raises_unavailable():
    calls = {"n": 0}

    def always_fails(url: str, timeout: float):
        calls["n"] += 1
        raise urllib.error.URLError("down")

    source = OpenMeteoSource(
        47.07, 15.44, ["grass"], transport=always_fails, retry_delay=0
    )
    with pytest.raises(SourceUnavailable):
        source.fetch()

    assert calls["n"] == 2  # tried exactly twice, no infinite loop


def test_unknown_allergen_silent_dropped_at_construction():
    """v2.0+: OM silent-drops allergens it doesn't cover (matching every
    other source). The orchestrator passes the user's GLOBAL selection (24
    species in v2+); OM takes only the 6 it can. Raising would block any
    install selecting a v2 species OM doesn't cover (e.g. hazel)."""
    source = OpenMeteoSource(
        47.07, 15.44, ["grass", "ragweed", "hazel", "dandelion"]
    )
    assert source.allergens == ["grass", "ragweed"]


def test_past_days_clamped_to_provider_maximum():
    source = OpenMeteoSource(47.07, 15.44, ["grass"], past_days=999)
    assert source.past_days == 92
    assert "past_days=92" in source.build_url()
    assert "domains=cams_europe" in source.build_url()


# -- async fetch path --------------------------------------------------------


def _async_transport_returning(status: int, payload: object):
    async def transport(url: str, timeout: float):
        return status, payload

    return transport


def test_async_success_parses_series():
    source = OpenMeteoSource(
        47.0707, 15.4395, ["grass", "birch"],
        async_transport=_async_transport_returning(200, _european_payload()),
    )
    result = asyncio.run(source.async_fetch())

    assert result.ok
    assert result.status is SourceStatus.OK
    assert result.allergens["grass"].current == 20.8
    assert result.allergens["grass"].values == [18.0, 19.5, 20.8, None]
    assert result.forecast_split == 2


def test_async_out_of_coverage_returns_status_not_raise():
    source = OpenMeteoSource(
        40.71, -74.0, ["grass"],
        async_transport=_async_transport_returning(
            400, {"error": True, "reason": "No data is available for this location"}
        ),
    )
    result = asyncio.run(source.async_fetch())

    assert result.status is SourceStatus.OUT_OF_COVERAGE
    assert result.allergens == {}


def test_async_retries_once_then_succeeds():
    calls = {"n": 0}

    async def flaky(url: str, timeout: float):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("temporary")
        return 200, _european_payload()

    source = OpenMeteoSource(
        47.07, 15.44, ["grass"], async_transport=flaky, retry_delay=0
    )
    result = asyncio.run(source.async_fetch())

    assert calls["n"] == 2
    assert result.ok


def test_async_exhausts_retries_and_raises_unavailable():
    calls = {"n": 0}

    async def always_fails(url: str, timeout: float):
        calls["n"] += 1
        raise ConnectionError("down")  # OSError subclass

    source = OpenMeteoSource(
        47.07, 15.44, ["grass"], async_transport=always_fails, retry_delay=0
    )
    with pytest.raises(SourceUnavailable):
        asyncio.run(source.async_fetch())

    assert calls["n"] == 2
