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
    return _INDEX_TO_LEVEL[max(0, min(4, int(index)))]


# DWD 7-point string scale -> 3-level (operational alignment, by meaning; see
# ANALYTICS.md). "high"(3)/"moderate-high"(2-3) -> 2; "moderate"(2) is mid -> 1.
_DWD_TO_LEVEL: dict[str, int] = {
    "0": 0,
    "0-1": 0,
    "1": 1,
    "1-2": 1,
    "2": 1,
    "2-3": 2,
    "3": 2,
}


def dwd_collapse(value: str | None) -> int | None:
    """Collapse a DWD value ('0'..'3' with half-steps) to the 0/1/2 level.

    Returns ``None`` (omit the source for this species) for no-data ('-1'),
    missing, or any unexpected value — never crash, never silently treat as 0.
    """
    if value is None:
        return None
    return _DWD_TO_LEVEL.get(str(value).strip())


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
    status: str  # "ok" | "insufficient_history" | "off_season" | "no_data"


def compute_recent_percentile(
    peaks: list[tuple[str, float]],
    today: str,
    *,
    min_days: int = MIN_PERCENTILE_DAYS,
) -> PercentileResult:
    """Rank today's daily peak against the window's daily-peak distribution.

    ``peaks`` is the daily-peak series already limited to the trailing window
    (``daily_peaks`` output, dates ≤ today). The distribution includes today.

    Statuses (state is a number only for ``ok``):
    - ``no_data`` — today's value is missing from the window.
    - ``insufficient_history`` — fewer than ``min_days`` distinct days.
    - ``off_season`` — the **whole window is zero** (max == 0): a percentile
      would be a misreadable 50% ("no signal", not "mid-range"), and any trace
      would jerk it to ~90%. Note this is keyed on the window max, not today: a
      zero *today* in a window that has signal is a genuine, informative low
      percentile and stays ``ok``.
    - ``ok`` — a real percentile.
    """
    by_date = dict(peaks)
    today_peak = by_date.get(today)
    if today_peak is None:
        return PercentileResult(None, len(by_date), "no_data")
    if len(by_date) < min_days:
        return PercentileResult(None, len(by_date), "insufficient_history")
    distribution = list(by_date.values())
    if max(distribution) == 0:
        return PercentileResult(None, len(by_date), "off_season")
    return PercentileResult(
        percentile_rank(today_peak, distribution), len(by_date), "ok"
    )


# --- consensus / divergence (cross-source) --------------------------------

# Categorical consensus vocabulary. Levels 0/1/2 map to none/low/high; "mixed"
# is genuine disagreement (sources differ by >1 level) — a number can't hold it.
# (Level 1 is "in season, below peak"; "low" is the user-facing label — see
# ANALYTICS.md. "moderate" was considered.)
CONSENSUS_NONE = "none"
CONSENSUS_LOW = "low"
CONSENSUS_HIGH = "high"
CONSENSUS_MIXED = "mixed"
CONSENSUS_OPTIONS = [CONSENSUS_NONE, CONSENSUS_LOW, CONSENSUS_HIGH, CONSENSUS_MIXED]
_LEVEL_TO_CONSENSUS = {0: CONSENSUS_NONE, 1: CONSENSUS_LOW, 2: CONSENSUS_HIGH}


@dataclass(slots=True)
class ConsensusResult:
    """Cross-source consensus for one species.

    ``state`` is None when fewer than two sources cover the species (consensus
    needs ≥2 — the metric never reports one source talking to itself).
    """

    state: str | None  # one of CONSENSUS_OPTIONS, or None if < 2 sources
    level: int | None  # 0/1/2 when agreed; None for mixed or < 2 sources
    diverged: bool  # True only in the "mixed" case (levels differ by > 1)
    source_levels: dict[str, int]  # contributing per-source levels


def consensus(levels: dict[str, int]) -> ConsensusResult:
    """Combine per-source levels (0/1/2) into a consensus.

    Equal weighting (v1.0). Tiebreak (deliberate, health-conservative — see
    ANALYTICS.md): equal → that level; adjacent (differ by 1) → the **higher**
    level; differ by >1 → "mixed". Fewer than two sources → state None
    (omitted), so a single source never masquerades as consensus.
    """
    source_levels = dict(levels)
    if len(source_levels) < 2:
        return ConsensusResult(None, None, False, source_levels)
    values = list(source_levels.values())
    if max(values) - min(values) > 1:
        return ConsensusResult(CONSENSUS_MIXED, None, True, source_levels)
    level = max(values)  # take-the-higher on equal/adjacent
    return ConsensusResult(_LEVEL_TO_CONSENSUS[level], level, False, source_levels)


def recent_percentile_from_series(
    times: list[str],
    values: list[float | None],
    today: str,
    *,
    window_days: int = PERCENTILE_WINDOW_DAYS,
    min_days: int = MIN_PERCENTILE_DAYS,
) -> PercentileResult:
    """recent_percentile for a source that carries its own history series.

    Daily-peaks the aligned (times, values), keeps the trailing ``window_days``
    up to and including ``today``, and ranks today within it. (Open-Meteo's
    92-day backfill path.)
    """
    peaks = [(d, p) for d, p in daily_peaks(times, values) if d <= today]
    return compute_recent_percentile(
        peaks[-window_days:], today, min_days=min_days
    )

