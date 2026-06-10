"""Unit tests for the pure analytics functions (HA-free)."""

from __future__ import annotations

import pytest

from custom_components.pollenwatch.analytics import (
    bucket_level,
    collapse_index,
    compute_recent_percentile,
    consensus,
    daily_peaks,
    dwd_collapse,
    google_collapse,
    level_label,
    percentile_rank,
    recent_percentile_from_series,
)


@pytest.mark.parametrize(
    ("species", "grains", "expected"),
    [
        # grass: still 3/50 — best-anchored EAACI bracket.
        ("grass", 0, 0),
        ("grass", 2.9, 0),
        ("grass", 3, 1),
        ("grass", 49.9, 1),
        ("grass", 50, 2),
        ("grass", 200, 2),
        # v2.2 birch: refined 10→20 onset (Aerobiologia 2021); peak 100
        # VALIDATED by Struß 2025 controlled chamber (doi:10.1159/000545509).
        ("birch", 9.9, 0),
        ("birch", 19.9, 0),
        ("birch", 20, 1),   # new onset
        ("birch", 99.9, 1),
        ("birch", 100, 2),  # peak validated
        # v2.2 alder: refined to per-species cited values 45/80
        # (Rapiejko 2007 PMC6245103). Peak BELOW the Fagales family
        # bracket — per-species evidence wins.
        ("alder", 30, 0),
        ("alder", 44.9, 0),
        ("alder", 45, 1),   # new onset
        ("alder", 79.9, 1),
        ("alder", 80, 2),   # new peak (was 100)
        # v2.2 hazel: refined to 35/80 (Rapiejko 2007 PMC4996891).
        ("hazel", 34.9, 0),
        ("hazel", 35, 1),   # new onset
        ("hazel", 79.9, 1),
        ("hazel", 80, 2),   # new peak (was 100)
        # v2.2 olive: peak raised 100→200 (Spanish op scale PMC7349006;
        # corrects regional over-warning).
        ("olive", 10, 1),
        ("olive", 99, 1),   # was high under v2.1; now low
        ("olive", 199, 1),
        ("olive", 200, 2),  # new peak
        # v2.2 ragweed: refined 3/50 → 5/20 (PMC5357339; PMC2868868).
        # Watch UBAMBI (NCT05346718, ragweed arm unpublished as of mid-2026).
        ("ragweed", 3, 0),  # was low under v2.1; now none
        ("ragweed", 4.9, 0),
        ("ragweed", 5, 1),  # new onset
        ("ragweed", 19.9, 1),
        ("ragweed", 20, 2), # new peak (was 50)
        # v2.2 mugwort: HERB-class fix — moved from tree bracket (10, 100)
        # to herb-class default (3, 50). No mugwort-specific cited cutoff;
        # evidence graded *limited* (Aerobiologia 2021).
        ("mugwort", 0, 0),
        ("mugwort", 3, 1),  # new onset (was none under v2.1)
        ("mugwort", 49.9, 1),
        ("mugwort", 50, 2), # new peak (was 100)
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


# --- consensus -------------------------------------------------------------


def test_consensus_equal_levels():
    res = consensus({"open_meteo": 0, "polleninformation": 0})
    assert res.state == "none"
    assert res.level == 0
    assert res.diverged is False


def test_consensus_equal_high():
    res = consensus({"open_meteo": 2, "polleninformation": 2})
    assert res.state == "high"
    assert res.level == 2
    assert res.diverged is False


def test_consensus_adjacent_takes_higher():
    # 0 & 1 -> low (the higher); 1 & 2 -> high (the higher).
    assert consensus({"a": 0, "b": 1}).state == "low"
    assert consensus({"a": 0, "b": 1}).level == 1
    assert consensus({"a": 1, "b": 2}).state == "high"
    assert consensus({"a": 1, "b": 2}).level == 2


def test_consensus_two_apart_is_mixed():
    res = consensus({"open_meteo": 0, "polleninformation": 2})
    assert res.state == "mixed"
    assert res.level is None
    assert res.diverged is True


def test_consensus_single_source_passes_through():
    """v2.0+: single-source species emit a pass-through consensus + source_count=1.
    The card's n/m badge tells users the reading is single-source, not the
    sensor's absence (which was v1.x behaviour)."""
    res = consensus({"open_meteo": 2}, max_possible=6)
    assert res.state == "high"          # pass-through of level 2
    assert res.level == 2
    assert res.diverged is False        # nothing to disagree with
    assert res.source_levels == {"open_meteo": 2}
    assert res.source_count == 1
    assert res.max_possible == 6


def test_consensus_zero_sources_omitted():
    """A species with no sources covering it has no consensus at all."""
    res = consensus({}, max_possible=6)
    assert res.state is None
    assert res.level is None
    assert res.diverged is False
    assert res.source_levels == {}
    assert res.source_count == 0
    assert res.max_possible == 6


def test_consensus_reports_source_levels():
    res = consensus({"open_meteo": 2, "polleninformation": 1})
    assert res.source_levels == {"open_meteo": 2, "polleninformation": 1}
    assert res.state == "high"  # adjacent -> higher


# --- DWD collapse ----------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "level"),
    [
        ("0", 0), ("0-1", 0),
        ("1", 1), ("1-2", 1), ("2", 1),
        ("2-3", 2), ("3", 2),
    ],
)
def test_dwd_collapse_scale(value, level):
    assert dwd_collapse(value) == level


@pytest.mark.parametrize("value", ["-1", "", "5", "x", None, "0 - 1"])
def test_dwd_collapse_unexpected_omits(value):
    # no-data / missing / unexpected -> None (omit), never crash, never ->0
    assert dwd_collapse(value) is None


# --- Google UPI collapse ---------------------------------------------------


@pytest.mark.parametrize(
    ("upi", "level"),
    [(0, 0), (1, 1), (2, 1), (3, 1), (4, 2), (5, 2)],
)
def test_google_collapse_scale(upi, level):
    # None->0; Very Low/Low/Moderate(1-3)->1; High/Very High(4-5)->2.
    assert google_collapse(upi) == level


@pytest.mark.parametrize("value", [None, -1, 6, 99, "x"])
def test_google_collapse_unexpected_omits(value):
    # Out-of-range / non-int / missing -> None, never crash, never ->0.
    assert google_collapse(value) is None


# --- 3-source consensus (new: never exercised before DWD) ------------------


def test_consensus_three_sources_all_agree():
    res = consensus({"open_meteo": 1, "polleninformation": 1, "dwd": 1})
    assert res.state == "low"
    assert res.level == 1
    assert res.diverged is False


def test_consensus_three_sources_lone_high_outlier_takes_higher():
    # {1,1,2}: two sources agree "low", one says "high". DOCUMENTED WART:
    # take-the-higher makes the lone outlier win (-> high) AND divergence stays
    # OFF (spread is only 1), so a minority high reading presents as confident
    # consensus. Interim behavior; see REVIEW_QUEUE (revisit divergence semantics).
    res = consensus({"open_meteo": 1, "polleninformation": 1, "dwd": 2})
    assert res.state == "high"
    assert res.level == 2
    assert res.diverged is False  # <- the wart


def test_consensus_three_sources_spanning_two_levels_is_mixed():
    res = consensus({"open_meteo": 0, "polleninformation": 0, "dwd": 2})
    assert res.state == "mixed"
    assert res.diverged is True


def test_consensus_three_sources_low_outlier_takes_higher():
    # {0,0,1}: take-higher -> low (level 1), not diverged (spread 1).
    res = consensus({"open_meteo": 0, "polleninformation": 0, "dwd": 1})
    assert res.state == "low"
    assert res.level == 1
    assert res.diverged is False


def test_consensus_two_sources_unchanged_when_third_omitted():
    # A species only 2 sources cover (DWD omitted, e.g. out-of-coverage or -1)
    # yields the exact same result as the 2-source case — the "third source
    # disturbs nothing" guarantee at the pure-logic level.
    two = consensus({"open_meteo": 1, "polleninformation": 2})
    assert two.state == "high" and two.level == 2 and two.diverged is False
    assert two.source_levels == {"open_meteo": 1, "polleninformation": 2}


# --- 4- and 5-source consensus (new: MeteoSwiss + ePIN raise the ceiling) ---
# consensus() is source-count-agnostic, but these scales were never exercised
# before this milestone. They also lock in the documented lone-higher wart at
# the new scale (issue #1) — asserted as KNOWN behavior, not fixed here.


def test_consensus_four_sources_all_agree():
    res = consensus({"open_meteo": 1, "polleninformation": 1, "dwd": 1, "epin": 1})
    assert res.state == "low"
    assert res.level == 1
    assert res.diverged is False
    assert set(res.source_levels) == {"open_meteo", "polleninformation", "dwd", "epin"}


def test_consensus_four_sources_adjacent_takes_higher():
    # {1,1,2,2}: spread 1 -> take-the-higher -> high, not diverged.
    res = consensus({"open_meteo": 1, "polleninformation": 1, "dwd": 2, "epin": 2})
    assert res.state == "high"
    assert res.level == 2
    assert res.diverged is False


def test_consensus_four_sources_lone_high_outlier_wart():
    # {1,1,1,2}: three sources agree "low", one lone source says "high". WART
    # (issue #1): take-the-higher lets the lone outlier win (-> high) AND
    # divergence stays OFF (spread is only 1), so a single dissenting high
    # reading presents as confident consensus. Documented + deferred; the
    # divergence-semantics redesign is out of scope for this milestone — this
    # test pins the behavior so the wider scale is not silently untested.
    res = consensus(
        {"open_meteo": 1, "polleninformation": 1, "dwd": 1, "meteoswiss": 2}
    )
    assert res.state == "high"
    assert res.level == 2
    assert res.diverged is False  # <- the wart, now confirmed at 4 sources


def test_consensus_four_sources_spanning_two_levels_is_mixed():
    res = consensus(
        {"open_meteo": 0, "polleninformation": 0, "dwd": 2, "meteoswiss": 2}
    )
    assert res.state == "mixed"
    assert res.level is None
    assert res.diverged is True


def test_consensus_five_sources_all_agree():
    # grass is the species all five sources can cover.
    res = consensus(
        {
            "open_meteo": 2,
            "polleninformation": 2,
            "dwd": 2,
            "meteoswiss": 2,
            "epin": 2,
        }
    )
    assert res.state == "high"
    assert res.level == 2
    assert res.diverged is False
    assert len(res.source_levels) == 5


def test_consensus_five_sources_lone_high_outlier_wart():
    # {1,1,1,1,2} at five sources: same wart — lone outlier wins, no divergence.
    res = consensus(
        {
            "open_meteo": 1,
            "polleninformation": 1,
            "dwd": 1,
            "meteoswiss": 1,
            "epin": 2,
        }
    )
    assert res.state == "high"
    assert res.level == 2
    assert res.diverged is False  # the wart persists at 5 sources (issue #1)


def test_consensus_five_sources_spanning_two_levels_is_mixed():
    res = consensus(
        {
            "open_meteo": 0,
            "polleninformation": 1,
            "dwd": 1,
            "meteoswiss": 2,
            "epin": 2,
        }
    )
    assert res.state == "mixed"
    assert res.diverged is True


# --- level_label -----------------------------------------------------------


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (0, "none"),
        (1, "low"),
        (2, "high"),
        (None, None),  # None in -> None out (explicit guard)
        (3, None),  # out-of-range -> None (LEVEL_LABELS.get miss)
        (-1, None),  # out-of-range -> None
        (99, None),  # far out-of-range -> None (LEVEL_LABELS.get miss)
    ],
)
def test_level_label_maps_levels_and_passes_through_none(level, expected):
    assert level_label(level) == expected
