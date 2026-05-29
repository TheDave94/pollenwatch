"""Derived analytics for PollenWatch — pure, Home Assistant-free.

All cross-source comparison happens on a common 3-level scale (see ANALYTICS.md):
    0 = below season onset, 1 = in season, 2 = at/above peak.
Open-Meteo grains/m³ is bucketed *down* to a level via EAACI/CAMS thresholds;
the polleninformation 0–4 index is collapsed onto the same 3 levels (an
operational alignment). Raw per-source values are never reconstructed from a
level.

These functions take values in and return numbers out — no HA, no I/O — so they
are unit-tested in isolation like the source parsers.
"""

from __future__ import annotations

from dataclasses import dataclass

# (onset, peak) grains/m³ per species — EAACI (Pfaar 2017/2020), as used by
# Copernicus CAMS / Climate-ADAPT. See ANALYTICS.md for citations. alder and
# mugwort are grouped by analogy (birch/olive), NOT independently sourced.
_THRESHOLDS: dict[str, tuple[float, float]] = {
    "alder": (10, 100),
    "birch": (10, 100),
    "olive": (10, 100),
    "mugwort": (10, 100),
    "grass": (3, 50),
    "ragweed": (3, 50),
}

# polleninformation 0–4 index -> 3-level scale (operational alignment).
_INDEX_TO_LEVEL: dict[int, int] = {0: 0, 1: 1, 2: 1, 3: 2, 4: 2}

#: Trailing window for recent_percentile (rolling days, relative to today).
PERCENTILE_WINDOW_DAYS = 92
#: Minimum distinct days of data before a percentile is emitted (else
#: "insufficient history"). ~2 weeks.
MIN_PERCENTILE_DAYS = 14


def bucket_level(species: str, grains: float) -> int:
    """Bucket a grains/m³ concentration down to the 0/1/2 level.

    Boundary convention: a value equal to a threshold belongs to the higher
    level (``>=``).
    """
    onset, peak = _THRESHOLDS[species]
    if grains >= peak:
        return 2
    if grains >= onset:
        return 1
    return 0


def collapse_index(index: int) -> int:
    """Collapse the polleninformation 0–4 index to the 0/1/2 level."""
    return _INDEX_TO_LEVEL[int(index)]


def daily_peaks(
    times: list[str], values: list[float | None]
) -> list[tuple[str, float]]:
    """Group an aligned (times, values) series into per-day peak values.

    Returns ``(date, peak)`` pairs sorted by date; ``None`` values are skipped.
    Peaks (per-day max), not hourly values, are the population for percentiles.
    """
    peaks: dict[str, float] = {}
    for time, value in zip(times, values, strict=False):
        if value is None:
            continue
        date = time[:10]
        peaks[date] = max(peaks.get(date, value), value)
    return sorted(peaks.items())


def percentile_rank(value: float, distribution: list[float]) -> float | None:
    """Empirical percentile rank of ``value`` within ``distribution`` (0–100).

    Midrank ("mean") convention with linear tie handling:
    ``100 * (count(x < value) + 0.5 * count(x == value)) / n``. ``None`` for an
    empty distribution.
    """
    n = len(distribution)
    if n == 0:
        return None
    less = sum(1 for x in distribution if x < value)
    equal = sum(1 for x in distribution if x == value)
    return 100.0 * (less + 0.5 * equal) / n


@dataclass(slots=True)
class PercentileResult:
    """Outcome of a recent_percentile computation."""

    percentile: float | None
    days: int
    status: str  # "ok" | "insufficient_history" | "no_data"


def compute_recent_percentile(
    peaks: list[tuple[str, float]],
    today: str,
    *,
    min_days: int = MIN_PERCENTILE_DAYS,
) -> PercentileResult:
    """Rank today's daily peak against the window's daily-peak distribution.

    ``peaks`` is the daily-peak series already limited to the trailing window
    (``daily_peaks`` output, dates ≤ today). The distribution includes today.
    Emits ``insufficient_history`` until ``min_days`` distinct days exist.
    """
    by_date = dict(peaks)
    today_peak = by_date.get(today)
    if today_peak is None:
        return PercentileResult(None, len(by_date), "no_data")
    if len(by_date) < min_days:
        return PercentileResult(None, len(by_date), "insufficient_history")
    distribution = list(by_date.values())
    return PercentileResult(
        percentile_rank(today_peak, distribution), len(by_date), "ok"
    )
