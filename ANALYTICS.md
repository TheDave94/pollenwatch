# PollenWatch analytics — sourced constants & definitions

Paper trail for the milestone-3b analytics layer: every threshold/constant is
documented with its source (same discipline as `HA_COMPATIBILITY.md`). Numbers
are **sourced, not invented**.

## Level scale for cross-source comparison (decided 2026-05-29)

Cross-source consensus/divergence compares sources on a common **level** scale,
not on raw values (grains/m³ vs the polleninformation 0–4 index aren't directly
comparable). Open-Meteo's grains/m³ is bucketed **down** to a level; the index
is never reconstructed into a concentration (lossy, indefensible). Raw per-source
sensors are untouched — bucketing is internal to analytics.

The scale is **3 levels**, defined by their aerobiological meaning so every edge
is a sourced EAACI/CAMS boundary (not an invented number):

| Level | Meaning | Open-Meteo grains/m³ bucket |
| --- | --- | --- |
| **0** | below season onset (negligible exposure) | `< onset` |
| **1** | in season (onset ≤ value < peak) | `onset ≤ x < peak` |
| **2** | at/above peak (high exposure) | `≥ peak` |

with `onset`/`peak` the per-group EAACI thresholds in the table below.

### polleninformation 0–4 → 3-level collapse (OPERATIONAL ALIGNMENT)

The polleninformation index (0–4) is collapsed onto the 3-level scale as:

| index | 0 | 1 | 2 | 3 | 4 |
| --- | --- | --- | --- | --- | --- |
| level | 0 | 1 | 1 | 2 | 2 |

i.e. `0→0, 1–2→1, 3–4→2`. **This mapping is an operational alignment, not a
sourced equivalence** — the 3-level scale itself is EAACI-sourced, but aligning
the provider's 5-band index onto it is our editorial choice (labelled here for
honesty, like the support-policy HA floor). The provider does not publish a
grains/m³↔index table to derive it rigorously.

## Threshold finding (research 2026-05-29)

Goal: authoritative, published, **per-species** grains/m³ → level thresholds.

**What is authoritative and citable.** The clinically-grounded thresholds from
the **EAACI position papers (Pfaar et al. 2017, 2020)**, used by the official
**Copernicus CAMS / Climate-ADAPT** ground-level pollen forecast, define **two**
boundaries per species group:

| Species group | "Season onset" (grains/m³) | "Peak period" (grains/m³) |
| --- | --- | --- |
| alder, birch, olive, mugwort | ≥ 10 | ≥ 100 |
| grass, ragweed | ≥ 3 | ≥ 50 |

Sources:
- Climate-ADAPT, *Four-day forecast of ground-level pollen (CAMS)* — states these
  thresholds, attributed to EAACI and Pfaar et al. (2017, 2020).
- Pfaar O, et al. *Defining pollen exposure times for clinical trials … — an
  EAACI position paper.* Allergy. 2017;72(5):713–722.

**Caveat that travels with these numbers:** the grouping is by species **group**,
not fully per-species (within a group the numbers are identical). Pfaar's core
species are **birch, grass, olive, ragweed**; **alder and mugwort are grouped by
analogy (birch/olive), not independently sourced**. Do not smooth this into false
confidence — for a mugwort- or alder-allergic user the honest position is "this
threshold is extrapolated." This caveat is surfaced in the integration's docs.

**What does NOT exist (the gate finding):** an authoritative, *cited*, **4-band**
(none/low/moderate/high/very-high) **per-species** grains/m³ table. The 4-band
tables that circulate online (e.g. "tree 10/100/1000, grass 5/20/50") are
operational conventions with **no traceable authoritative citation** — adopting
them would be inventing numbers, which this milestone's gate forbids.

**Decision (2026-05-29):** use the **3-level** scale above (option A), which is
fully EAACI/CAMS-sourced. No 4-band table is invented.

### Bucketing thresholds (per group, grains/m³)

```
onset / peak
  alder, birch, olive, mugwort : 10 / 100   # mugwort, alder extrapolated (caveat)
  grass, ragweed               :  3 / 50
```
Boundary convention: a value exactly equal to a threshold belongs to the **higher**
level (`value >= onset` → ≥1; `value >= peak` → 2).

## recent_percentile (per-source, per-species) — definition

"Today is at the Nth percentile of the recent period." Single-source (each source
gets its own); **not** cross-source.

- **Statistic:** empirical percentile **rank** of today's value within the
  trailing-window distribution, midrank/“mean” convention:
  `100 * (count(x < today) + 0.5 * count(x == today)) / n`. (Linear handling of
  ties; documented and deterministic.)
- **Population = DAILY PEAKS** (one value per day = that day's max), **not** hourly
  readings — otherwise overnight zeros dominate and everything reads high.
- **Window:** trailing **92 days** relative to today (rolling, not fixed-calendar),
  so it stays meaningful as the season moves.
- **Open-Meteo:** works **day one** via the `past_days=92` backfill (no recorder
  dependency).
- **polleninformation:** no history endpoint, so it baselines on **HA recorder**
  history of its own raw sensor. Until enough days accumulate (`MIN_PERCENTILE_DAYS`,
  ~14) it emits an honest **"insufficient history"** state, not a misleading
  number; it improves passively as data accrues.
- **Statuses** (state is a number only for `ok`; otherwise unknown + a
  `history_status` attribute): `ok`, `insufficient_history`, `no_data`, and
  **`off_season`**. `off_season` fires when the **whole trailing window is zero**
  (`max == 0`): a percentile there is a misreadable 50% ("no signal", not
  "mid-range"), and any trace would jerk it to ~90%. Keyed on the window max, not
  today — a zero *today* within a window that has signal is a genuine, informative
  low percentile and stays `ok`.

## Consensus & divergence (cross-source)

Both compare sources on the common **3-level** scale above (Open-Meteo bucketed,
polleninformation index collapsed). They exist **only for species ≥2 sources
cover in the current data** — a single source never masquerades as consensus
(unavailable otherwise).

**consensus** (categorical sensor; `none`/`low`/`high`/`mixed`, with the numeric
`level` and per-source `source_levels` in attributes). Combining rule, equal
weighting (v1.0, no station>model):

| Source levels | consensus |
| --- | --- |
| equal | that level (`none`/`low`/`high`) |
| **adjacent** (differ by 1) | **the higher level** |
| differ by >1 (0 vs 2) | `mixed` |

The **take-the-higher** rule for adjacent levels is a **deliberate,
health-conservative choice** — round an allergy sufferer toward the more cautious
reading, not away — **not** a statistical necessity.

**divergence** (binary sensor, device_class problem) is the boolean companion to
`mixed`: on when source levels differ by **>1**. The ">1" threshold is tunable
(see REVIEW_QUEUE) once we observe how often it fires on real dual-source data.

**Entity IDs (HA 2026.5 constraint):** both sit under a "PollenWatch Analytics"
device, and on HA 2026.5 a device-associated entity's ID is **always**
`<device_slug>_<name>` — the device prefix can't be suppressed (confirmed with
has_entity_name False/True and an explicit `self.entity_id`, on a cleared
registry). So the IDs are
`sensor.pollenwatch_analytics_<species>_consensus` and
`binary_sensor.pollenwatch_analytics_<species>_divergence`, **not** the originally
intended `sensor.pollenwatch_consensus_<species>`. Getting the un-prefixed form
would require dropping the Analytics device. **Decided (2026-05-29): keep the
Analytics device and accept the prefixed IDs** — the device grouping (a tidy,
user-visible container for the cross-source metrics, distinct from the per-source
devices) is worth more than a shorter ID, which only matters in
automations/templates where length is irrelevant and the prefix is arguably
clearer. Fresh installs register these IDs directly; the existing live instance
was migrated via an entity-registry rename.

## DWD scale — probe findings & PROPOSED mapping (pending review)

Probed `https://opendata.dwd.de/climate_environment/health/alerts/s31fg.json`
(open, no key) on 2026-05-29. "Pollenflug-Gefahrenindex für Deutschland" —
**Germany only**.

- **Native scale:** a 7-point ordinal encoded as **strings**:
  `"0","0-1","1","1-2","2","2-3","3"` (half-steps are hyphenated strings, not
  floats), plus `"-1"` = no data (documented; absent from the current feed, but
  the client must handle it). Legend semantics: 0 keine (none), 0-1 keine bis
  geringe (none–low), 1 geringe (low), 1-2 geringe bis mittlere (low–moderate),
  2 mittlere (moderate), 2-3 mittlere bis hohe (moderate–high), 3 hohe (high).
- **Forecast horizon:** 3 days (today / tomorrow / dayafter_to).
- **Coverage:** region-based — 12 regions (region_id 10…120) → ~26 partregions
  (partregion_id). **No lat/lon in the feed** (point→region mapping is on us;
  non-German location → out_of_coverage).
- **Allergens (8):** Erle→alder, Birke→birch, Graeser→grass, Beifuss→mugwort,
  Ambrosia→ragweed (5 of our 6); plus Esche/ash, Hasel/hazel, Roggen/rye (not
  tracked). **No olive** (DWD covers 5/6 canonical).

**PROPOSED DWD→3-level mapping (operational alignment, by MEANING — not a
sourced equivalence; pending maintainer review):**

| DWD value | meaning | level |
| --- | --- | --- |
| `0`, `0-1` | none / none–low | **0** |
| `1`, `1-2`, `2` | low / low–moderate / moderate | **1** |
| `2-3`, `3` | moderate–high / high | **2** |
| `-1` | no data | (omit) |

Anchored on meaning: our level 2 = "high", and DWD's own "high" is `3` (with
`2-3` = moderate-to-high → rounds up, health-conservative); DWD's "moderate"
(`2`) is mid, not high → level 1; "none"/"none-low" → level 0. A pure
`dwd_collapse` function (heavily boundary-tested) lands once approved.
