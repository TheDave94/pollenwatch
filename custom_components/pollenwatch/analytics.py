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
# v2.0+ additions for the expanded 24-species set: species without exact-
# species EAACI cutoffs borrow from the family analogue (tree group → birch
# bracket; herb/grass group → Poaceae bracket). These are flagged as
# `ThresholdStatus.PARTIAL` in `species_registry`; promoting them to exact
# cutoffs is tracked in REVIEW_QUEUE.md.
_THRESHOLDS: dict[str, tuple[float, float]] = {
    # v1.x exact EAACI cutoffs
    "alder": (10, 100),
    "birch": (10, 100),
    "olive": (10, 100),
    "mugwort": (10, 100),
    "grass": (3, 50),
    "ragweed": (3, 50),
    # v2.0 trees — birch/olive bracket
    "hazel": (10, 100),
    "ash": (10, 100),
    "oak": (10, 100),
    "holm_oak": (10, 100),
    "beech": (10, 100),
    "elm": (10, 100),
    "carpinus": (10, 100),
    "plane_tree": (10, 100),
    "cypress_family": (10, 100),
    "juglans": (10, 100),
    # v2.0 grasses + herbs — Poaceae/Ambrosia bracket
    "rye": (3, 50),
    "plantago": (3, 50),
    "urtica": (3, 50),
    "nettle_family": (3, 50),
    "chenopodium": (3, 50),
    "rumex": (3, 50),
    "asteraceae": (3, 50),
    # Note: alternaria (spore) is reported by PI as a 0-4 index — collapse_index
    # path, never grains/m³ — so it never reaches bucket_level. No threshold
    # entry needed; intentionally omitted.
}

# polleninformation 0–4 index -> 3-level scale (operational alignment).
_INDEX_TO_LEVEL: dict[int, int] = {0: 0, 1: 1, 2: 1, 3: 2, 4: 2}

#: Trailing window for recent_percentile (rolling days, relative to today).
PERCENTILE_WINDOW_DAYS = 92
#: Minimum distinct days of data before a percentile is emitted (else
#: "insufficient history"). ~2 weeks.
MIN_PERCENTILE_DAYS = 14


def bucket_level(species: str, grains: float) -> int | None:
    """Bucket a grains/m³ concentration down to the 0/1/2 level.

    Boundary convention: a value equal to a threshold belongs to the higher
    level (``>=``). Returns ``None`` for species without published thresholds
    (the source contributes a raw value but no level → not in consensus
    aggregation). Defensive even though v2.0+ covers all 24 species.
    """
    bounds = _THRESHOLDS.get(species)
    if bounds is None:
        return None
    onset, peak = bounds
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


# Google Universal Pollen Index (UPI) 0–5 -> 3-level (operational alignment, by
# meaning; see ANALYTICS.md). "None"(0) -> 0 (below onset); "Very Low"/"Low"/
# "Moderate"(1–3) -> 1 (in season); "High"/"Very High"(4–5) -> 2 (peak). Moderate
# stays at 1 because Google reserves High/Very High for the elevated tier — the
# health-conservative bias lives once in consensus take-the-higher, not here.
# Top-two -> 2 mirrors the polleninformation 0–4 collapse.
_UPI_TO_LEVEL: dict[int, int] = {0: 0, 1: 1, 2: 1, 3: 1, 4: 2, 5: 2}


def google_collapse(value: object) -> int | None:
    """Collapse a Google UPI value (0–5) to the 0/1/2 level.

    Returns ``None`` (omit the source for this species) for missing or
    unexpected values — never crash, never silently treat as 0.
    """
    if value is None:
        return None
    try:
        upi = int(value)
    except (ValueError, TypeError):
        return None
    return _UPI_TO_LEVEL.get(upi)


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

    v2.0+: single-source species are also represented (state = that source's
    own level mapped to none/low/high; `diverged` always False; the n/m badge
    on the sensor tells the user it's single-source). `source_count` is how
    many sources actually contributed; `max_possible` is the global ceiling
    from the species registry (used by the card for the badge denominator).
    """

    state: str | None        # one of CONSENSUS_OPTIONS, or None if 0 sources
    level: int | None        # 0/1/2 when single or agreed; None for mixed/0
    diverged: bool           # True only in the "mixed" case (levels differ by >1)
    source_levels: dict[str, int]  # contributing per-source levels
    source_count: int        # len(source_levels) — how many contributed now
    max_possible: int        # global ceiling from species_registry


def consensus(levels: dict[str, int], max_possible: int = 0) -> ConsensusResult:
    """Combine per-source levels (0/1/2) into a consensus.

    Equal weighting (v1.0). Tiebreak (deliberate, health-conservative — see
    ANALYTICS.md): equal → that level; adjacent (differ by 1) → the **higher**
    level; differ by >1 → "mixed".

    Source-count semantics:
    - 0 sources: state=None, level=None, source_count=0 (sensor unavailable).
    - 1 source: pass-through — state = that source's level mapped to
      none/low/high; never "mixed" (nothing to disagree with); never diverged.
      The n/m badge on the sensor tells the user this is single-source.
    - >=2 sources: existing v1 logic.

    ``max_possible`` is the registry ceiling (how many sources GLOBALLY cover
    this species); defaults to ``source_count`` if not provided (safe but
    less informative for the badge).
    """
    source_levels = dict(levels)
    source_count = len(source_levels)
    if max_possible == 0:
        max_possible = source_count or 1
    if source_count == 0:
        return ConsensusResult(None, None, False, source_levels, 0, max_possible)
    if source_count == 1:
        # Single-source pass-through. The lone source IS the consensus.
        level = next(iter(source_levels.values()))
        return ConsensusResult(
            _LEVEL_TO_CONSENSUS[level], level, False, source_levels,
            1, max_possible,
        )
    values = list(source_levels.values())
    if max(values) - min(values) > 1:
        return ConsensusResult(
            CONSENSUS_MIXED, None, True, source_levels,
            source_count, max_possible,
        )
    level = max(values)  # take-the-higher on equal/adjacent
    return ConsensusResult(
        _LEVEL_TO_CONSENSUS[level], level, False, source_levels,
        source_count, max_possible,
    )


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

