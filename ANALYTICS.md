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

### Google UPI 0–5 → 3-level collapse (OPERATIONAL ALIGNMENT)

Google reports the **Universal Pollen Index (UPI)**, a six-band index. We map it
**by the documented category meaning** (`google_collapse`):

| UPI | Google category | Documented meaning | level |
| --- | --- | --- | --- |
| 0 | None | "Pollen levels are very low and are not likely to trigger allergic reactions" | 0 |
| 1 | Very Low | "People with very high allergy to pollen are likely to experience symptoms" | 1 |
| 2 | Low | "People with high allergy to pollen are likely to experience symptoms" | 1 |
| 3 | Moderate | "People with allergy to pollen are likely to experience symptoms" | 1 |
| 4 | High | (elevated tier — less-allergic people react) | 2 |
| 5 | Very High | (top tier — most/all allergic people react) | 2 |

i.e. `0→0, 1–3→1, 4–5→2`. **Why Moderate (3) → 1, not 2:** Google's own naming
reserves *High*/*Very High* for the elevated tier and documents *Moderate* as
mid. The health-conservative bias belongs **once** in consensus take-the-higher,
not in the per-source collapse — inflating Moderate→2 would apply that bias twice
and systematically over-warn. Keeping the collapse faithful to the source also
keeps Google parallel to the polleninformation top-two→2 collapse. Like the
others, this is an **operational alignment, not a sourced equivalence**: the
3-level scale is EAACI-sourced; aligning Google's six bands onto it is editorial.
All six **category names** are documented (Google RPC reference). The 0–3
**descriptions** above are quoted verbatim from Google's docs.

**On-instance live check (2026-05-29, Graz, v1.2.0-rc1).** Read off the live HA
entities via `ha.py` (key stays in HA's encrypted config — never enters chat):
- Raw sensors populate on the UPI 0–5 scale, unit `None`, attribution `Source:
  Includes pollen data from Google`, with a 4-day forward forecast attribute.
- Cross-source consensus picks Google up (`source_levels` includes `google`):
  e.g. grass `{open_meteo:1, polleninformation:2, google:1}` → `high`; olive
  `{open_meteo:0, polleninformation:0, google:1}` → `low` (Google is the only
  source enabling an olive consensus at Graz).
- **`supports_history=False` payoff confirmed live:** *no*
  `sensor.pollenwatch_google_*_recent_percentile` entity exists for any Google
  allergen (404), while raw + `_personal_score` do — the Milestone-A flag works
  end-to-end on the real instance.

**Verbatim High (4) / Very High (5) strings: not capturable from Google's static
docs.** A re-check confirmed Google's `/forecast` guide publishes example
responses with `indexDescription` for **UPI 0, 1, 2 only** (the 3 description
came from a third-party blog showing a real response); UPI 4 and 5 do not
appear anywhere on Google's static documentation pages. Those strings ship
*dynamically* in the API response's `indexDescription` field when a real call
hits those bands — they are not in published category docs. Recording them
statically would therefore need either a parser change to surface
`indexDescription` onto the entity (declined this rc as enlarging the live
product for a footnote) or a paid query at a high-pollen location. The mapping
keys on the documented category *name* (which IS published for all six), not on
the prose, so this footnote does not gate the logic. See REVIEW_QUEUE.

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

### Per-species refinements (v2.2 — issue #3)

Six species have refined per-species brackets, overriding the family default
above. Each refinement has a peer-reviewed grains/m³ cutoff (Tier-2 evidence in
the per-species review); full provenance in `docs/THRESHOLD_PROVENANCE_REVIEW.md`.

| Species | v2.1 bracket | v2.2 bracket | Cited basis |
| --- | --- | --- | --- |
| ragweed | 3 / 50 | **5 / 20** | PMC5357339 (<20), PMC2868868 (sensitive 1–5), Nature s41598-022-20069-y (Milan 4-severity) — was *under*-warning |
| olive | 10 / 100 | **10 / 200** | Sciencedirect S1081120610010537 (162), PubMed 10394105 (~400 monosensitized), PMC7349006 — was *over*-warning regionally |
| birch | 10 / 100 | **20 / 100** | Struß 2025 controlled chamber (doi:10.1159/000545509) validates peak 100; Aerobiologia 2021 refines low |
| alder | 10 / 100 | **45 / 80** | Rapiejko 2007 (PMC6245103): 45 first symptoms, 80 all alder-allergics symptomatic |
| hazel | 10 / 100 | **35 / 80** | Rapiejko 2007 (PMC4996891): operational low 0–35 / high >35; severe >80 |
| mugwort | 10 / 100 | **3 / 50** | Aerobiologia 2021 + Rapiejko: clinically herb-like, not tree-like — v1 class-error fix |

Behaviour change for users: an existing entity sitting at e.g. olive 150 was
`high` under v2.1, becomes `low` under v2.2. Entity IDs are preserved; only the
state value flips.

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
- **MeteoSwiss:** self-baselines **day one** from its recent hourly CSV (months of
  history, like Open-Meteo — no recorder). **ePIN** exposes only ~7 days, far short
  of the window, so it baselines on **HA recorder** like polleninformation.
- **Reference day for lagged observation feeds:** a self-baselining source ranks the
  **latest available reading's day**, not the calendar today. An observation feed
  (e.g. MeteoSwiss) can publish with ~1 day of lag, so calendar-today may not exist
  in the data yet — ranking it would always be `no_data`. This is intentional, not a
  bug: you cannot percentile-rank a day that has not been measured. (Open-Meteo's
  `current` hour is today, so it is unaffected.)
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
the consensus *level*: on whenever the sources are **not unanimous** (any spread
`>= 1`), **not** just the spread-`>1` `mixed` case. The binary sensor carries a
`spread` attribute (max−min of the per-source levels) that grades the
disagreement: `1` = adjacent (a level is still reported via take-the-higher),
`>=2` = `mixed` (no single level).

This is the resolution of **issue #1** (the `{1,1,2}` wart). With take-the-higher,
a minority can pull the consensus *level* up (`{1,1,2}` → `high`); under the old
`>1` divergence threshold that reading carried divergence **off**, so a minority
high masqueraded as confident consensus. Flagging any non-unanimity makes the
pair honest: consensus still reports the cautious level, and divergence says "but
the sources don't all agree." The consensus *state* is unchanged — `mixed` still
means spread `>1`, and take-the-higher still names the level for spread `<=1`.

**Why widen `>1` → `>=1` rather than the alternatives** (decided 2026-06-29 from
24 days of live 3–5 source data, 453 multi-source readings via the Hermes
snapshot pipeline → `~/.hermes/state/pollenwatch-watch/snapshots.csv`):

- *Majority/mode for the level* was rejected — it throws away the
  health-conservative bias (would report `none` over a credible lone `low`).
  take-the-higher is a locked decision; the fix belongs in the confidence signal,
  not the level.
- The data showed the minority-pull-up pattern is **frequent** (42% of
  multi-source readings) but its dominant shape is **benign** — one source
  (systematically Google, occasionally ePIN) reading `low` while the others read
  `none`. That *is* genuine non-unanimity and is now flagged; the trade-off is a
  higher base divergence rate (≈2% → ≈64% of multi-source readings over the
  sample window), accepted as the honest signal. The `spread` attribute lets a
  card/automation suppress the mild spread-`1` case if it wants to.
- The truly alarming shape (a *lone* source pulling consensus to `high`) was rare
  (2 readings in 24 days) but is exactly what the widened flag now catches.

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

## DWD scale — probe findings & shipped mapping

Probed `https://opendata.dwd.de/climate_environment/health/alerts/s31fg.json`
(open, no key) on 2026-05-29. "Pollenflug-Gefahrenindex für Deutschland" —
**Germany only**. The mapping below ships in `analytics.py`.

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

**DWD→3-level mapping (operational alignment, by MEANING — not a sourced
equivalence):**

| DWD value | meaning | level |
| --- | --- | --- |
| `0`, `0-1` | none / none–low | **0** |
| `1`, `1-2`, `2` | low / low–moderate / moderate | **1** |
| `2-3`, `3` | moderate–high / high | **2** |
| `-1` | no data | (omit) |

Anchored on meaning: our level 2 = "high", and DWD's own "high" is `3` (with
`2-3` = moderate-to-high → rounds up, health-conservative); DWD's "moderate"
(`2`) is mid, not high → level 1; "none"/"none-low" → level 0. Implemented as
`dwd_collapse` in `analytics.py` (boundary-tested).
