"""Regression tests for the 2026-07 review fixes."""

from __future__ import annotations

from custom_components.pollenwatch.sensor import _species_from_suffix


def test_species_from_suffix_handles_multi_token_keys() -> None:
    """Multi-token canonical species must not be mis-parsed on the prune path.

    A blind split("_", 1)[0] recovered "cypress" from "cypress_family_...",
    which is never in the configured set, so a SELECTED multi-token species was
    pruned on every reload (wiping the user's entity customisations).
    """
    configured = {"grass", "cypress_family", "nettle_family", "holm_oak", "plane_tree"}

    # Raw sensor (no metric suffix).
    assert _species_from_suffix("cypress_family", configured) == "cypress_family"
    assert _species_from_suffix("holm_oak", configured) == "holm_oak"
    # Derived metrics.
    assert (
        _species_from_suffix("cypress_family_recent_percentile", configured)
        == "cypress_family"
    )
    assert (
        _species_from_suffix("plane_tree_personal_score", configured) == "plane_tree"
    )
    assert _species_from_suffix("grass_recent_percentile", configured) == "grass"
    # Every configured species round-trips to itself (nothing selected is pruned).
    for species in configured:
        assert _species_from_suffix(species, configured) in configured
        assert (
            _species_from_suffix(f"{species}_recent_percentile", configured)
            == species
        )


def test_species_from_suffix_prefix_disambiguation() -> None:
    """A shorter key that prefixes a longer one must not shadow the longer key."""
    configured = {"oak", "holm_oak"}
    assert _species_from_suffix("holm_oak", configured) == "holm_oak"
    assert _species_from_suffix("holm_oak_personal_score", configured) == "holm_oak"
    assert _species_from_suffix("oak", configured) == "oak"
    assert _species_from_suffix("oak_personal_score", configured) == "oak"


def test_species_from_suffix_empty_configured_falls_back() -> None:
    """The disabled-source sweep passes an empty set; everything then prunes."""
    assert _species_from_suffix("cypress_family", set()) == "cypress_family"
    assert _species_from_suffix("grass_recent_percentile", set()) == "grass_recent_percentile"
