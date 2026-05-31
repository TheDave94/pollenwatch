"""Tests for the region-aware default-species preselection module.

These are pure-Python tests (no HA fixture); the module is data + lookup
only and stays import-free of homeassistant.
"""

from __future__ import annotations

import pytest

from custom_components.pollenwatch.region_defaults import (
    DEFAULT_FALLBACK,
    HIGH_POTENCY_CORE,
    NON_PI_DEFAULTS_MED,
    NON_PI_DEFAULTS_NORTH,
    REGION_DEFAULT_SPECIES,
    get_active_sources_for_country,
    get_locally_available_species,
    get_region_defaults,
    species_class_label,
)
from custom_components.pollenwatch.sources.species_registry import (
    ALL_SPECIES_KEYS,
    CANONICAL_SPECIES,
)

# --- Locked-decision invariants -----------------------------------------


def test_alternaria_never_in_any_region_default():
    """opt-in-spore decision (2026-05-30): alternaria stays unchecked
    everywhere; users co-tracking spores select it manually."""
    assert "alternaria" not in HIGH_POTENCY_CORE
    assert "alternaria" not in DEFAULT_FALLBACK
    assert "alternaria" not in NON_PI_DEFAULTS_NORTH
    assert "alternaria" not in NON_PI_DEFAULTS_MED
    for country, species in REGION_DEFAULT_SPECIES.items():
        assert "alternaria" not in species, (
            f"alternaria in {country} default: {species}"
        )


def test_high_potency_core_has_exactly_8_species():
    """Locked Phase-D contract: cross-validated quick-pick = 8 species."""
    assert len(HIGH_POTENCY_CORE) == 8
    assert set(HIGH_POTENCY_CORE) == {
        "alder", "birch", "grass", "hazel", "mugwort", "ragweed",
        "olive", "ash",
    }


def test_default_fallback_is_high_potency_core():
    assert DEFAULT_FALLBACK == HIGH_POTENCY_CORE


def test_all_region_default_species_are_canonical():
    """Every species in any region's default list must exist in the
    species registry — otherwise the preselection would orphan."""
    for country, species in REGION_DEFAULT_SPECIES.items():
        for s in species:
            assert s in ALL_SPECIES_KEYS, f"{s} (in {country}) not in registry"


# --- get_region_defaults -------------------------------------------------


@pytest.mark.parametrize(
    "country,expected_subset",
    [
        ("AT", {"alder", "birch", "grass", "hazel", "mugwort", "ragweed",
                "ash", "oak"}),
        ("DE", {"alder", "birch", "grass", "hazel", "mugwort", "ragweed",
                "ash", "oak", "plane_tree", "rye"}),
        ("CH", {"alder", "birch", "grass", "hazel", "mugwort", "ragweed",
                "ash", "oak", "beech"}),
        ("IT", {"alder", "birch", "grass", "hazel", "mugwort", "ragweed",
                "olive", "cypress_family", "nettle_family", "plane_tree"}),
        ("GB", {"alder", "birch", "grass", "hazel", "mugwort", "ragweed",
                "ash", "plane_tree"}),
        ("SE", {"alder", "birch", "grass", "hazel", "mugwort", "ragweed",
                "ash"}),
    ],
)
def test_known_country_defaults(country: str, expected_subset: set[str]):
    """The locked recommendation-table preselection per PI-supported country."""
    defaults = set(get_region_defaults(country))
    assert defaults == expected_subset


def test_country_lookup_is_case_insensitive():
    assert get_region_defaults("at") == get_region_defaults("AT")
    assert get_region_defaults("De") == get_region_defaults("DE")


@pytest.mark.parametrize("country", ["GR", "PT", "HR", "MT", "CY"])
def test_non_pi_mediterranean_falls_back_to_med_defaults(country: str):
    """Non-PI Mediterranean countries get olive + cypress_family in defaults."""
    defaults = get_region_defaults(country)
    assert "olive" in defaults
    assert "cypress_family" in defaults


@pytest.mark.parametrize("country", ["NL", "BE", "FI", "DK", "IE", "SI"])
def test_non_pi_northern_falls_back_to_north_defaults(country: str):
    """Non-PI Northern countries get no Mediterranean species in defaults."""
    defaults = get_region_defaults(country)
    assert "olive" not in defaults
    assert "cypress_family" not in defaults


def test_unknown_country_falls_back_to_high_potency_core():
    # Unknown countries → high-potency core (HIGH_POTENCY_CORE),
    # filtered down to species the picker would show.
    defaults_xx = get_region_defaults("XX")
    defaults_none = get_region_defaults(None)
    # XX has no country-specific source override, so the picker shows
    # species covered by always-available sources (OM + Google) — that
    # set includes all 8 core species.
    assert set(defaults_xx) == set(HIGH_POTENCY_CORE)
    assert set(defaults_none) == set(HIGH_POTENCY_CORE)


def test_defaults_filtered_to_locally_available():
    """If a region's default list includes a species not coverable in
    that country (shouldn't happen for the locked table, but defensive
    behaviour), it's filtered out."""
    # All entries in REGION_DEFAULT_SPECIES are checked: every species
    # in the per-country default must be locally available at that country.
    for country in REGION_DEFAULT_SPECIES:
        local = set(get_locally_available_species(country))
        defaults = get_region_defaults(country)
        assert set(defaults) <= local, (
            f"{country}: defaults {set(defaults) - local} not locally available"
        )


# --- get_active_sources_for_country -------------------------------------


def test_always_available_sources():
    """OM + Google are always available regardless of country."""
    for country in (None, "XX", "AT", "DE", "CH", "FR", "IT", "ZW"):
        active = get_active_sources_for_country(country)
        assert "open_meteo" in active
        assert "google" in active


def test_de_unlocks_dwd_and_epin():
    active = get_active_sources_for_country("DE")
    assert "dwd" in active
    assert "epin" in active  # surfaced for DE; Bavarians enable it


def test_ch_unlocks_meteoswiss():
    assert "meteoswiss" in get_active_sources_for_country("CH")


def test_pi_countries_unlock_polleninformation():
    for country in ("AT", "CH", "DE", "ES", "FR", "GB", "IT", "PL", "SE",
                    "TR", "UA", "LV", "LT"):
        active = get_active_sources_for_country(country)
        assert "polleninformation" in active, country


def test_non_pi_country_no_polleninformation():
    for country in ("NL", "BE", "FI", "NO", "GR", "PT"):
        active = get_active_sources_for_country(country)
        assert "polleninformation" not in active, country


def test_non_de_no_dwd_no_epin():
    for country in ("AT", "CH", "IT", "FR", "GB"):
        active = get_active_sources_for_country(country)
        assert "dwd" not in active, country
        assert "epin" not in active, country


# --- get_locally_available_species --------------------------------------


def test_locally_available_for_de_includes_epin_only_species():
    """DE unlocks ePIN — so ePIN-only species like plantago appear."""
    available = set(get_locally_available_species("DE"))
    assert "plantago" in available  # ePIN-only
    assert "carpinus" in available  # ePIN-only
    assert "juglans" in available   # ePIN-only


def test_locally_available_for_at_excludes_epin_only_species():
    """AT can't enable ePIN; plantago etc. shouldn't appear."""
    available = set(get_locally_available_species("AT"))
    assert "plantago" not in available
    assert "carpinus" not in available


def test_locally_available_always_includes_om_species():
    """OM is always-on; its 6 species appear for every country."""
    for country in ("AT", "DE", "CH", "FR", "NL", "XX", None):
        available = set(get_locally_available_species(country))
        for sp in ("alder", "birch", "grass", "mugwort", "olive", "ragweed"):
            assert sp in available, f"{sp} missing for country={country}"


# --- species_class_label ------------------------------------------------


def test_species_class_label_for_each_class():
    assert species_class_label("birch") == "Tree"
    assert species_class_label("grass") == "Grass"
    assert species_class_label("rye") == "Grass"
    assert species_class_label("mugwort") == "Herb"
    assert species_class_label("alternaria") == "Spore"


def test_species_class_label_covers_every_canonical_species():
    """No KeyError for any canonical species."""
    for key in CANONICAL_SPECIES:
        assert species_class_label(key) in (
            "Tree", "Grass", "Herb", "Spore"
        )
