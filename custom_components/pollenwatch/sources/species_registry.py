"""Canonical PollenWatch species registry.

Single source of truth for the species PollenWatch tracks: botanical
identity, allergenic class, EAACI/D'Amato potency rating, threshold
knowledge, and which upstream sources can report them globally.

Replaces (in v2.0+) the simpler ``ALLERGENS`` tuple in ``sources.base``.
The 24-species set is the v2.0 expansion from the v1.x hand-picked 6
(alder, birch, grass, mugwort, olive, ragweed).

Kept import-free of ``homeassistant`` so the data layer is testable in
isolation — same discipline as ``sources/base.py`` and ``const.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class SpeciesClass(StrEnum):
    """Botanical / clinical class — used for onboarding UI grouping."""

    TREE = "tree"
    GRASS = "grass"
    HERB = "herb"
    SPORE = "spore"


class Potency(StrEnum):
    """EAACI / D'Amato 2007 allergenic-potency tier.

    LOW and NEGLIGIBLE are deliberately not represented — only species with
    HIGH or MODERATE clinical relevance enter the registry. Pine, poplar,
    and the like were filtered out before the registry was defined.
    """

    HIGH = "high"
    MODERATE = "moderate"


class ThresholdStatus(StrEnum):
    """Whether published EAACI/CAMS clinical-grade thresholds exist."""

    YES = "yes"           # exact-species cutoffs published
    PARTIAL = "partial"   # cutoffs for a related family member exist
    NO = "no"             # ungraded — raw value only (no species at NO yet)


# Source keys — literal strings mirrored from const.SOURCE_*. Kept inline
# here to keep this module import-free of const (which depends on this
# module via const.ALLERGEN_NAMES derivation in Phase B+).
_OM = "open_meteo"
_PI = "polleninformation"
_DWD = "dwd"
_MS = "meteoswiss"
_EPIN = "epin"
_GOOGLE = "google"


@dataclass(frozen=True)
class SpeciesInfo:
    """Canonical metadata for a PollenWatch species.

    ``sources`` is the *global* set — the upstream sources that can report
    this species when actively configured and in their coverage area.
    Per-install coverage is computed at runtime by intersecting with the
    user's enabled sources.
    """

    key: str
    latin: str
    common: str
    class_: SpeciesClass
    potency: Potency
    thresholds: ThresholdStatus
    sources: frozenset[str]


CANONICAL_SPECIES: Final[dict[str, SpeciesInfo]] = {
    # =================================================================
    # HIGH potency (12)
    # =================================================================
    "alder": SpeciesInfo(
        "alder", "Alnus", "Alder",
        SpeciesClass.TREE, Potency.HIGH, ThresholdStatus.YES,
        frozenset({_OM, _PI, _DWD, _MS, _EPIN, _GOOGLE}),
    ),
    "birch": SpeciesInfo(
        "birch", "Betula", "Birch",
        SpeciesClass.TREE, Potency.HIGH, ThresholdStatus.YES,
        frozenset({_OM, _PI, _DWD, _MS, _EPIN, _GOOGLE}),
    ),
    "grass": SpeciesInfo(
        "grass", "Poaceae", "Grass",
        SpeciesClass.GRASS, Potency.HIGH, ThresholdStatus.YES,
        frozenset({_OM, _PI, _DWD, _MS, _EPIN, _GOOGLE}),
    ),
    "hazel": SpeciesInfo(
        "hazel", "Corylus", "Hazel",
        SpeciesClass.TREE, Potency.HIGH, ThresholdStatus.YES,
        frozenset({_PI, _DWD, _MS, _EPIN, _GOOGLE}),
    ),
    "mugwort": SpeciesInfo(
        "mugwort", "Artemisia", "Mugwort",
        SpeciesClass.HERB, Potency.HIGH, ThresholdStatus.YES,
        frozenset({_OM, _PI, _DWD, _EPIN, _GOOGLE}),
    ),
    "ragweed": SpeciesInfo(
        "ragweed", "Ambrosia", "Ragweed",
        SpeciesClass.HERB, Potency.HIGH, ThresholdStatus.YES,
        frozenset({_OM, _PI, _DWD, _EPIN, _GOOGLE}),
    ),
    "olive": SpeciesInfo(
        "olive", "Olea", "Olive",
        SpeciesClass.TREE, Potency.HIGH, ThresholdStatus.YES,
        frozenset({_OM, _PI, _GOOGLE}),
    ),
    "rye": SpeciesInfo(
        "rye", "Secale", "Cereal rye",
        SpeciesClass.GRASS, Potency.HIGH, ThresholdStatus.PARTIAL,
        frozenset({_PI, _DWD, _EPIN}),
    ),
    "plantago": SpeciesInfo(
        "plantago", "Plantago", "Plantain",
        SpeciesClass.HERB, Potency.HIGH, ThresholdStatus.YES,
        frozenset({_EPIN}),
    ),
    "urtica": SpeciesInfo(
        "urtica", "Urtica", "Common nettle",
        SpeciesClass.HERB, Potency.HIGH, ThresholdStatus.PARTIAL,
        frozenset({_EPIN}),
    ),
    "nettle_family": SpeciesInfo(
        "nettle_family", "Urticaceae", "Nettle / pellitory",
        SpeciesClass.HERB, Potency.HIGH, ThresholdStatus.PARTIAL,
        frozenset({_PI}),
    ),
    # Mould spore, not pollen — kept in the registry because EAACI treats
    # Alternaria as a major outdoor aeroallergen with strong asthma
    # associations. Labelled "(spore)" in UI; opt-in only (not in any
    # region-default set per the locked recommendation table).
    "alternaria": SpeciesInfo(
        "alternaria", "Alternaria", "Alternaria (spore)",
        SpeciesClass.SPORE, Potency.HIGH, ThresholdStatus.PARTIAL,
        frozenset({_PI}),
    ),
    # =================================================================
    # MODERATE potency (12)
    # =================================================================
    "ash": SpeciesInfo(
        "ash", "Fraxinus", "Ash",
        SpeciesClass.TREE, Potency.MODERATE, ThresholdStatus.PARTIAL,
        frozenset({_DWD, _MS, _EPIN, _GOOGLE}),
    ),
    "oak": SpeciesInfo(
        "oak", "Quercus", "Oak",
        SpeciesClass.TREE, Potency.MODERATE, ThresholdStatus.PARTIAL,
        frozenset({_MS, _EPIN, _GOOGLE}),
    ),
    # Cupressaceae family — Google's JUNIPER + CYPRESS_PINE both fold here.
    "cypress_family": SpeciesInfo(
        "cypress_family", "Cupressaceae", "Cypress / juniper",
        SpeciesClass.TREE, Potency.MODERATE, ThresholdStatus.YES,
        frozenset({_PI, _GOOGLE}),
    ),
    "plane_tree": SpeciesInfo(
        "plane_tree", "Platanus", "Plane tree",
        SpeciesClass.TREE, Potency.MODERATE, ThresholdStatus.PARTIAL,
        frozenset({_PI, _EPIN}),
    ),
    "beech": SpeciesInfo(
        "beech", "Fagus", "Beech",
        SpeciesClass.TREE, Potency.MODERATE, ThresholdStatus.PARTIAL,
        frozenset({_MS, _EPIN}),
    ),
    "elm": SpeciesInfo(
        "elm", "Ulmus", "Elm",
        SpeciesClass.TREE, Potency.MODERATE, ThresholdStatus.PARTIAL,
        frozenset({_EPIN, _GOOGLE}),
    ),
    "carpinus": SpeciesInfo(
        "carpinus", "Carpinus", "Hornbeam",
        SpeciesClass.TREE, Potency.MODERATE, ThresholdStatus.PARTIAL,
        frozenset({_EPIN}),
    ),
    # Quercus ilex — distinct from Quercus (deciduous oak); Mediterranean
    # evergreen with different clinical profile. ePIN distinguishes.
    "holm_oak": SpeciesInfo(
        "holm_oak", "Quercus ilex", "Holm oak",
        SpeciesClass.TREE, Potency.MODERATE, ThresholdStatus.PARTIAL,
        frozenset({_EPIN}),
    ),
    "chenopodium": SpeciesInfo(
        "chenopodium", "Chenopodium", "Goosefoot",
        SpeciesClass.HERB, Potency.MODERATE, ThresholdStatus.PARTIAL,
        frozenset({_EPIN}),
    ),
    "rumex": SpeciesInfo(
        "rumex", "Rumex", "Sorrel / dock",
        SpeciesClass.HERB, Potency.MODERATE, ThresholdStatus.PARTIAL,
        frozenset({_EPIN}),
    ),
    "juglans": SpeciesInfo(
        "juglans", "Juglans", "Walnut",
        SpeciesClass.TREE, Potency.MODERATE, ThresholdStatus.PARTIAL,
        frozenset({_EPIN}),
    ),
    # Family-level catch-all for Asteraceae pollen ePIN measures but cannot
    # identify to genus. Mugwort and ragweed (also Asteraceae) are tracked
    # separately; this row is for the "other Asteraceae" residual.
    "asteraceae": SpeciesInfo(
        "asteraceae", "Asteraceae", "Asteraceae (other)",
        SpeciesClass.HERB, Potency.MODERATE, ThresholdStatus.PARTIAL,
        frozenset({_EPIN}),
    ),
}


ALL_SPECIES_KEYS: Final[frozenset[str]] = frozenset(CANONICAL_SPECIES.keys())


# The v1.x canonical set — used as the migration fallback when a v2 entry is
# encountered with no recoverable allergen list. These keys MUST exist in
# CANONICAL_SPECIES above, since that's the lossless-upgrade contract.
CANONICAL_V1_SPECIES: Final[tuple[str, ...]] = (
    "alder", "birch", "grass", "mugwort", "olive", "ragweed",
)


# Sanity: the v1 set is a subset of the canonical registry.
assert set(CANONICAL_V1_SPECIES) <= ALL_SPECIES_KEYS, (
    "CANONICAL_V1_SPECIES contains keys not in CANONICAL_SPECIES — "
    "migration would orphan data"
)
