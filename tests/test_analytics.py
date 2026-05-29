"""Unit tests for the pure analytics functions (HA-free)."""

from __future__ import annotations

import pytest

from custom_components.pollenwatch.analytics import (
    bucket_level,
    collapse_index,
    compute_recent_percentile,
    daily_peaks,
    percentile_rank,
    recent_percentile_from_series,
)


@pytest.mark.parametrize(
    ("species", "grains", "expected"),
    [
        ("grass", 0, 0),
        ("grass", 2.9, 0),
        ("grass", 3, 1),  # exactly onset -> higher level
        ("grass", 49.9, 1),
        ("grass", 50, 2),  # exactly peak -> higher level
        ("grass", 200, 2),
        ("birch", 9.9, 0),
        ("birch", 10, 1),
        ("birch", 99.9, 1),
        ("birch", 100, 2),
        ("ragweed", 3, 1),
        ("olive", 10, 1),
        ("mugwort", 100, 2),
    ],
)
def test_bucket_level_boundaries(species, grains, expected):
    assert bucket_level(species, grains) == expected


@pytest.mark.parametrize(
    ("index", "level"),
    [(0, 0), (1, 1), (2, 1), (3, 2), (4, 2)],
)
def test_collapse_index(index, level):
    assert collapse_index(index) == level


def test_daily_peaks_takes_per_day_max_and_skips_none():
    times = [
        "2026-05-29T00:00",
        "2026-05-29T12:00",
        "2026-05-30T06:00",
        "2026-05-30T18:00",
        "2026-05-31T03:00",
    ]
    values = [10.0, 20.8, 5.0, None, 0.0]
    assert daily_peaks(times, values) == [
        ("2026-05-29", 20.8),
        ("2026-05-30", 5.0),
        ("2026-05-31", 0.0),
    ]


def test_percentile_rank_midrank():
    dist = [0.0, 1.0, 2.0, 3.0, 4.0]
    assert percentile_rank(4.0, dist) == pytest.approx(90.0)  # (4 + 0.5)/5*100
    assert percentile_rank(0.0, dist) == pytest.approx(10.0)  # (0 + 0.5)/5*100
    assert percentile_rank(2.0, dist) == pytest.approx(50.0)
    assert percentile_rank(5.0, dist) == pytest.approx(100.0)


def test_percentile_rank_empty():
    assert percentile_rank(1.0, []) is None


def _peaks(n: int, today_value: float) -> list[tuple[str, float]]:
    # n distinct days ending today; today's peak is today_value.
    days = [f"2026-03-{d:02d}" for d in range(1, n)]
    pairs = [(d, 1.0) for d in days]
    pairs.append(("2026-04-01", today_value))
    return pairs


def test_recent_percentile_ok():
    peaks = _peaks(20, 9.0)  # 19 days at 1.0 + today at 9.0 = 20 days
    res = compute_recent_percentile(peaks, "2026-04-01", min_days=14)
    assert res.status == "ok"
    assert res.days == 20
    assert res.percentile == pytest.approx(100.0 * (19 + 0.5) / 20)


def test_recent_percentile_insufficient_history():
    peaks = _peaks(10, 9.0)  # only 10 days < min 14
    res = compute_recent_percentile(peaks, "2026-04-01", min_days=14)
    assert res.status == "insufficient_history"
    assert res.percentile is None
    assert res.days == 10


def test_recent_percentile_no_today_data():
    peaks = [("2026-03-01", 1.0), ("2026-03-02", 2.0)]
    res = compute_recent_percentile(peaks, "2026-04-01", min_days=1)
    assert res.status == "no_data"
    assert res.percentile is None


def test_recent_percentile_from_series_hourly_to_daily():
    # 16 days of hourly-ish data (two readings/day); today's peak is the max.
    times, values = [], []
    for d in range(1, 17):
        date = f"2026-03-{d:02d}"
        times += [f"{date}T03:00", f"{date}T15:00"]
        peak = 9.0 if d == 16 else 1.0
        values += [0.0, peak]  # overnight zero + daytime peak
    res = recent_percentile_from_series(times, values, "2026-03-16", min_days=14)
    assert res.status == "ok"
    assert res.days == 16  # one per day, not per hour
    assert res.percentile == pytest.approx(100.0 * (15 + 0.5) / 16)


def test_recent_percentile_off_season_when_window_all_zero():
    # 15 days, every day zero (incl today) -> off_season, no number.
    peaks = [(f"2026-01-{d:02d}", 0.0) for d in range(1, 16)]
    res = compute_recent_percentile(peaks, "2026-01-15", min_days=14)
    assert res.status == "off_season"
    assert res.percentile is None
    assert res.days == 15


def test_recent_percentile_quiet_today_with_signal_window_is_low_not_off_season():
    # Window has signal (days 1..14 nonzero); today is 0 -> genuinely low, ok.
    peaks = [(f"2026-01-{d:02d}", float(d)) for d in range(1, 15)]
    peaks.append(("2026-01-15", 0.0))  # today = 0
    res = compute_recent_percentile(peaks, "2026-01-15", min_days=14)
    assert res.status == "ok"
    assert res.percentile is not None
    assert res.percentile < 10  # at the bottom of a signal-bearing window
    assert res.percentile != 50


def test_recent_percentile_from_series_trims_window():
    times = [f"2026-01-{d:02d}T12:00" for d in range(1, 11)]
    values = [1.0] * 10
    res = recent_percentile_from_series(
        times, values, "2026-01-10", window_days=5, min_days=3
    )
    assert res.days == 5  # only the trailing 5 days kept
