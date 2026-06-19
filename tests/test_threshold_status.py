"""v2.2 (issue #3): per-species threshold-evidence tier.

Three layers of regression guard:

1. **Registry layer:** the 5-value ThresholdStatus enum exists and each
   of the 24 canonical species lands in the bucket the approved literature
   review (docs/THRESHOLD_PROVENANCE_REVIEW.md) assigns it. This guards
   against a future edit silently demoting (e.g.) cypress_family from
   FAMILY_EAACI back to FAMILY_ANALOGY without re-running the review.

2. **Raw-sensor wiring layer:** the `threshold_status` attribute appears
   on each per-source raw sensor and matches what the registry says for
   the species. Function-keyed (the assertion reads the registry); a
   wiring bug that hardcodes a value or omits the attribute breaks this.

3. **Consensus-sensor wiring layer:** same contract on the analytics
   ConsensusSensor — invariant: the threshold_status for `birch` is the
   same value whether read off `sensor.pollenwatch_open_meteo_birch` or
   `sensor.pollenwatch_analytics_birch_consensus`.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pollenwatch.analytics import _THRESHOLDS
from custom_components.pollenwatch.const import (
    CONF_ALLERGENS,
    CONF_SOURCES,
    DOMAIN,
    new_sources_config,
)
from custom_components.pollenwatch.sources.open_meteo import OpenMeteoSource
from custom_components.pollenwatch.sources.species_registry import (
    CANONICAL_SPECIES,
    THRESHOLD_BASIS_FROM_STATUS,
    ThresholdStatus,
    threshold_basis_for,
)

# Approved tier assignments per docs/THRESHOLD_PROVENANCE_REVIEW.md
# (2026-05-31). Tests assert membership two ways: (a) the registry agrees
# with this expected mapping, (b) every species in the registry lands in
# exactly one bucket.
EXPECTED_TIER_MEMBERSHIP: dict[ThresholdStatus, frozenset[str]] = {
    ThresholdStatus.SPECIES_SPECIFIC: frozenset({
        "birch", "ash", "alder", "hazel", "olive", "plane_tree",
        "mugwort", "ragweed", "grass", "plantago", "urtica",
        "nettle_family", "carpinus",
    }),
    ThresholdStatus.FAMILY_EAACI: frozenset({
        "rye", "oak", "holm_oak", "beech", "cypress_family",
    }),
    ThresholdStatus.ESTABLISHED_NO_THRESHOLD: frozenset({
        "chenopodium", "juglans", "elm",
    }),
    ThresholdStatus.FAMILY_ANALOGY: frozenset({"rumex", "asteraceae"}),
    ThresholdStatus.FUNGAL: frozenset({"alternaria"}),
}


# ---------------------------------------------------------------------------
# Layer 1: registry tier assignments
# ---------------------------------------------------------------------------

def test_threshold_status_enum_has_exactly_five_values():
    """The 5-value enum is the reconciled contract (PART A of issue #3)."""
    assert set(ThresholdStatus) == {
        ThresholdStatus.SPECIES_SPECIFIC,
        ThresholdStatus.FAMILY_EAACI,
        ThresholdStatus.ESTABLISHED_NO_THRESHOLD,
        ThresholdStatus.FAMILY_ANALOGY,
        ThresholdStatus.FUNGAL,
    }


def test_every_species_has_a_tier_assignment():
    """All 24 registry species map to exactly one of the 5 tiers."""
    covered: set[str] = set()
    for species_set in EXPECTED_TIER_MEMBERSHIP.values():
        covered |= species_set
    assert covered == set(CANONICAL_SPECIES.keys()), (
        f"missing from EXPECTED_TIER_MEMBERSHIP: "
        f"{sorted(set(CANONICAL_SPECIES.keys()) - covered)}; "
        f"extra: {sorted(covered - set(CANONICAL_SPECIES.keys()))}"
    )


@pytest.mark.parametrize(
    ("species", "expected_tier"),
    [
        (sp, tier)
        for tier, species_set in EXPECTED_TIER_MEMBERSHIP.items()
        for sp in sorted(species_set)
    ],
)
def test_species_threshold_status_matches_approved_review(
    species: str, expected_tier: ThresholdStatus,
) -> None:
    """Registry value for each species equals the approved review's tier."""
    actual = CANONICAL_SPECIES[species].thresholds
    assert actual == expected_tier, (
        f"{species}: registry says {actual.value}, "
        f"approved review says {expected_tier.value}"
    )


def test_tier_counts_match_review():
    """Final-doc tally: 13 SPECIES_SPECIFIC / 5 FAMILY_EAACI / 3
    ESTABLISHED_NO_THRESHOLD / 2 FAMILY_ANALOGY / 1 FUNGAL = 24."""
    actual_counts: dict[ThresholdStatus, int] = {}
    for info in CANONICAL_SPECIES.values():
        actual_counts[info.thresholds] = actual_counts.get(info.thresholds, 0) + 1
    expected = {
        ThresholdStatus.SPECIES_SPECIFIC: 13,
        ThresholdStatus.FAMILY_EAACI: 5,
        ThresholdStatus.ESTABLISHED_NO_THRESHOLD: 3,
        ThresholdStatus.FAMILY_ANALOGY: 2,
        ThresholdStatus.FUNGAL: 1,
    }
    assert actual_counts == expected


# ---------------------------------------------------------------------------
# Layer 1b: threshold_basis derived mapping (5 source tiers -> 3 derived
# values). Drives the binary "marked / unmarked" glance treatment in card
# UIs (PollenWatch's bundled card + oriel-dashboard, both consuming the
# same attribute — single source of truth lives here).
# ---------------------------------------------------------------------------

def test_threshold_basis_mapping_covers_every_tier():
    """Every ThresholdStatus value must have a derived-basis assignment —
    no source tier silently routes to None / KeyError at runtime."""
    assert set(THRESHOLD_BASIS_FROM_STATUS.keys()) == set(ThresholdStatus)


def test_threshold_basis_value_set_is_exactly_three():
    """The derived basis collapses 5 source tiers into exactly 3 values.
    Drift here means a card-side branch unexpectedly stops matching."""
    assert set(THRESHOLD_BASIS_FROM_STATUS.values()) == {
        "species", "family", "estimated",
    }


def test_basis_counts_per_value():
    """13 SPECIES_SPECIFIC + 1 FUNGAL -> 14 "species"; 5 FAMILY_EAACI ->
    5 "family"; 3 ESTABLISHED_NO_THRESHOLD + 2 FAMILY_ANALOGY -> 5
    "estimated"."""
    actual: dict[str, int] = {}
    for info in CANONICAL_SPECIES.values():
        basis = THRESHOLD_BASIS_FROM_STATUS[info.thresholds]
        actual[basis] = actual.get(basis, 0) + 1
    assert actual == {"species": 14, "family": 5, "estimated": 5}


@pytest.mark.parametrize("species", sorted(CANONICAL_SPECIES.keys()))
def test_threshold_basis_for_helper_matches_mapping(species: str) -> None:
    """``threshold_basis_for(sp)`` must equal the mapping lookup — catches
    any future re-implementation that hardcodes the 5->3 rule somewhere
    else and drifts from the registry constant."""
    expected = THRESHOLD_BASIS_FROM_STATUS[CANONICAL_SPECIES[species].thresholds]
    assert threshold_basis_for(species) == expected


# ---------------------------------------------------------------------------
# Layer 2 + 3: raw + consensus sensor wiring
# ---------------------------------------------------------------------------

_SESSION = "custom_components.pollenwatch.coordinator.async_get_clientsession"
_FETCH = "custom_components.pollenwatch.sources.open_meteo.OpenMeteoSource.async_fetch"


def _entry() -> MockConfigEntry:
    # Two species: birch (SPECIES_SPECIFIC) and mugwort (SPECIES_SPECIFIC,
    # but moved to the herb-class default bracket in v2.2 — exercises both
    # the v2.2 class-error fix and the consistent threshold_status surface).
    return MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="47.0700_15.4400",
        title="PollenWatch (47.070, 15.440)",
        data={
            CONF_LATITUDE: 47.07,
            CONF_LONGITUDE: 15.44,
            CONF_ALLERGENS: ["birch", "mugwort"],
        },
        options={CONF_SOURCES: new_sources_config()},
    )


def _payload() -> dict:
    times = [
        "2026-05-29T00:00",
        "2026-05-29T12:00",
        "2026-05-30T06:00",
        "2026-05-30T18:00",
    ]
    return {
        "latitude": 47.1,
        "longitude": 15.4,
        "timezone": "Europe/Vienna",
        "elevation": 363.0,
        "hourly_units": {"birch_pollen": "grains/m³", "mugwort_pollen": "grains/m³"},
        "current": {
            "time": "2026-05-29T12:00",
            "birch_pollen": 50.0,
            "mugwort_pollen": 25.0,
        },
        "hourly": {
            "time": times,
            "birch_pollen": [40.0, 50.0, 30.0, 35.0],
            "mugwort_pollen": [20.0, 25.0, 15.0, 18.0],
        },
    }


def _result():
    return OpenMeteoSource(47.07, 15.44, ["birch", "mugwort"]).parse(_payload())


async def test_raw_sensor_exposes_threshold_status_from_registry(
    hass: HomeAssistant,
) -> None:
    """The raw sensor's `threshold_status` attribute equals what the
    species_registry says for that species — function-keyed, no hardcode.
    """
    entry = _entry()
    entry.add_to_hass(hass)

    with (
        patch(_SESSION, return_value=object()),
        patch(_FETCH, new=AsyncMock(return_value=_result())),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

    for species in ("birch", "mugwort"):
        state = hass.states.get(f"sensor.pollenwatch_open_meteo_{species}")
        assert state is not None, f"no entity for {species}"
        expected = CANONICAL_SPECIES[species].thresholds.value
        actual = state.attributes.get("threshold_status")
        assert actual == expected, (
            f"{species}: entity threshold_status={actual!r} "
            f"!= registry {expected!r}"
        )


async def test_consensus_sensor_exposes_threshold_status_invariant_with_raw(
    hass: HomeAssistant,
) -> None:
    """Cross-source invariant: the consensus sensor for a species reports
    the same `threshold_status` as the raw sensor — same registry source.
    """
    entry = _entry()
    entry.add_to_hass(hass)

    with (
        patch(_SESSION, return_value=object()),
        patch(_FETCH, new=AsyncMock(return_value=_result())),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

    for species in ("birch", "mugwort"):
        raw = hass.states.get(f"sensor.pollenwatch_open_meteo_{species}")
        consensus = hass.states.get(f"sensor.pollenwatch_analytics_{species}_consensus")
        assert raw is not None and consensus is not None
        raw_ts = raw.attributes.get("threshold_status")
        cons_ts = consensus.attributes.get("threshold_status")
        registry_ts = CANONICAL_SPECIES[species].thresholds.value
        assert raw_ts == cons_ts == registry_ts, (
            f"{species}: raw={raw_ts!r}, consensus={cons_ts!r}, "
            f"registry={registry_ts!r} — should all be identical"
        )


# ---------------------------------------------------------------------------
# Layer 2b + 3b: threshold_basis wiring on raw + consensus sensors.
#
# Both species exercised here (birch + mugwort) carry SPECIES_SPECIFIC ->
# "species" — Open-Meteo's 6-species coverage doesn't include any
# non-SPECIES_SPECIFIC species, so the runtime path here only proves the
# "species" branch end-to-end. Mapping correctness for "family" and
# "estimated" is asserted at Layer 1b via the per-species parametrize,
# and the function-keyed wiring at sensor.py (threshold_basis_for(species))
# makes those branches correct by transitivity.
# ---------------------------------------------------------------------------

async def test_raw_sensor_exposes_threshold_basis_from_registry(
    hass: HomeAssistant,
) -> None:
    """The raw sensor's ``threshold_basis`` attribute equals
    ``threshold_basis_for(species)`` — same function-keyed contract as the
    threshold_status wiring test."""
    entry = _entry()
    entry.add_to_hass(hass)

    with (
        patch(_SESSION, return_value=object()),
        patch(_FETCH, new=AsyncMock(return_value=_result())),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

    for species in ("birch", "mugwort"):
        state = hass.states.get(f"sensor.pollenwatch_open_meteo_{species}")
        assert state is not None, f"no entity for {species}"
        expected = threshold_basis_for(species)
        actual = state.attributes.get("threshold_basis")
        assert actual == expected, (
            f"{species}: entity threshold_basis={actual!r} "
            f"!= helper {expected!r}"
        )


async def test_consensus_sensor_exposes_threshold_basis_invariant_with_raw(
    hass: HomeAssistant,
) -> None:
    """Cross-source invariant: the consensus sensor reports the same
    ``threshold_basis`` as the raw sensor for the same species."""
    entry = _entry()
    entry.add_to_hass(hass)

    with (
        patch(_SESSION, return_value=object()),
        patch(_FETCH, new=AsyncMock(return_value=_result())),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

    for species in ("birch", "mugwort"):
        raw = hass.states.get(f"sensor.pollenwatch_open_meteo_{species}")
        consensus = hass.states.get(f"sensor.pollenwatch_analytics_{species}_consensus")
        assert raw is not None and consensus is not None
        raw_basis = raw.attributes.get("threshold_basis")
        cons_basis = consensus.attributes.get("threshold_basis")
        helper_basis = threshold_basis_for(species)
        assert raw_basis == cons_basis == helper_basis, (
            f"{species}: raw={raw_basis!r}, consensus={cons_basis!r}, "
            f"helper={helper_basis!r} — should all be identical"
        )


# ---------------------------------------------------------------------------
# Layer 4: numeric brackets locked to the review doc
# ---------------------------------------------------------------------------
# The exact (onset, peak) grains/m³ brackets, per the "Operational brackets —
# LOCKED to analytics._THRESHOLDS" section of docs/THRESHOLD_PROVENANCE_REVIEW.md.
# This is rigor-on-what-exists, NOT manufactured precision: the cited refinements
# (birch/alder/hazel/olive/ragweed/grass) are study-derived; the rest are honest
# class defaults (tree 10/100, herb 3/50). Locking the numbers here means a
# bracket cannot drift in code without also editing the doc + this oracle.
EXPECTED_BRACKETS: dict[str, tuple[float, float]] = {
    # species-specific tier (13)
    "birch": (20, 100),
    "alder": (45, 80),
    "hazel": (35, 80),
    "ash": (10, 100),
    "olive": (10, 200),
    "plane_tree": (10, 100),
    "mugwort": (3, 50),
    "ragweed": (5, 20),
    "grass": (3, 50),
    "plantago": (3, 50),
    "urtica": (3, 50),
    "nettle_family": (3, 50),
    "carpinus": (10, 100),
    # family-EAACI (5)
    "rye": (3, 50),
    "oak": (10, 100),
    "holm_oak": (10, 100),
    "beech": (10, 100),
    "cypress_family": (10, 100),
    # established-no-threshold (3)
    "chenopodium": (3, 50),
    "juglans": (10, 100),
    "elm": (10, 100),
    # family-analogy (2)
    "rumex": (3, 50),
    "asteraceae": (3, 50),
    # alternaria (fungal) is intentionally absent — it routes via the PI 0–4
    # index, never the grains/m³ bucketing, so it carries no bracket.
}


def test_thresholds_match_locked_brackets() -> None:
    """`_THRESHOLDS` equals the brackets recorded in the review doc, exactly.

    Catches any silent drift of an operational (onset, peak) value.
    """
    assert _THRESHOLDS == EXPECTED_BRACKETS


def test_only_fungal_species_has_no_bracket() -> None:
    """Every canonical species has a grains/m³ bracket EXCEPT the fungal one
    (alternaria), which routes through the PI 0–4 index instead."""
    missing = set(CANONICAL_SPECIES) - set(_THRESHOLDS)
    assert missing == {"alternaria"}
    assert CANONICAL_SPECIES["alternaria"].thresholds is ThresholdStatus.FUNGAL


def test_brackets_are_structurally_sane() -> None:
    """Each bracket is 0 < onset <= peak (a usable two-step band)."""
    for species, (onset, peak) in _THRESHOLDS.items():
        assert 0 < onset <= peak, f"{species}: implausible bracket ({onset}, {peak})"
