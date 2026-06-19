"""Forecast slice + the empty-`today` guard in ``sensor._forecast_attr``.

Regression guard for the bug where a missing ``current_time`` left ``today``
empty, and ``date >= ""`` matched every ISO date — dumping the whole ~92-day
recent-percentile backfill window as if it were the forecast. The guard returns
an empty forecast in that case (validated on the AirWatch sibling).
"""

from __future__ import annotations

from custom_components.pollenwatch.sensor import _forecast_attr

# One sample per day → each day's peak is that day's value.
_TIMES = [
    "2026-06-17T00:00",
    "2026-06-18T00:00",
    "2026-06-19T00:00",
    "2026-06-20T00:00",
    "2026-06-21T00:00",
]
_VALUES = [10.0, 20.0, 30.0, 40.0, 50.0]


def test_forecast_is_today_onward_slice() -> None:
    out = _forecast_attr(_TIMES, _VALUES, "2026-06-19", max_days=4)
    assert [d["date"] for d in out] == ["2026-06-19", "2026-06-20", "2026-06-21"]
    assert out[0]["value"] == 30.0


def test_forecast_respects_max_days() -> None:
    out = _forecast_attr(_TIMES, _VALUES, "2026-06-17", max_days=2)
    assert [d["date"] for d in out] == ["2026-06-17", "2026-06-18"]


def test_forecast_empty_when_today_missing() -> None:
    # The guard: an empty `today` (source omitted current_time) yields NO
    # forecast — not the entire backfill window leaking through `date >= ""`.
    assert _forecast_attr(_TIMES, _VALUES, "", max_days=4) == []
