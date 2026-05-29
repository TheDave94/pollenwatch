# Milestone 3 — second source + derived analytics

> **Status:** approved 2026-05-29 — **split into 3a → 3b**. Decisions in §4.
> Starting with 3a. 3b is scoped here but not started.

## 1. The split (approved)

Milestone 3 is split into **3a = polleninformation.at as a second source**, then
**3b = the derived-analytics layer**, ordered 3a → 3b.

Why, and why this order:

1. **Scope-creep risk** (the project's stated #1 failure mode): two medium,
   independently shippable milestones beat one large one. See
   [[feedback-scope-discipline]].
2. **Dependency forces the order.** Consensus and divergence are *cross-source*
   — degenerate and untestable with one source. They only become real once a
   second source exists, so the source comes first and gives analytics real,
   testable inputs.
3. **Each delivers standalone value.** 3a = a second European source whose raw
   sensors are usable immediately (side-by-side via pollenprognos-card). 3b =
   the analytics that are PollenWatch's reason to exist.
4. **Architecture payoff lands where it's used.** 3a adopts the HA 2026.5
   per-source DataUpdateCoordinator pattern (genuinely multiple coordinators);
   3b adds the meta-coordinator on top.

---

## 2. Milestone 3a — polleninformation.at as a second source

### Meaning
One config entry, multiple per-source coordinators internally. A user enables
polleninformation, supplies an API key, and gets raw per-allergen sensors from
it under a second per-source device — alongside Open-Meteo. No analytics yet.

### Implementation order (each its own commit)
1. **Per-source coordinator refactor** (isolated; existing tests stay green) —
   see the blast-radius note in §4.
2. **Config-entry migration** VERSION 1 → 2 + `async_migrate_entry` + migration
   test, *before* any live deploy.
3. **Research the polleninformation API** (reference krissen/polleninformation;
   do not fork) → write findings into §5 of this doc.
4. **polleninformation source client** (`sources/polleninformation.py`) + mocked
   unit tests.
5. **Config flow**: API-key field, per-source enable/disable, global allergen
   selection mapped onto each source's capabilities.
6. **polleninformation coordinator** wired into the runtime container; sensors
   for the second source under its own device.
7. **Repair flow** for invalid/expired API key; `strings.json` + en/de.
8. **Floor bump** to 2026.5.0 (per-source pattern) in `HA_COMPATIBILITY.md`;
   manifest version bump.
9. **Live migration verification** (Open-Meteo must survive); report.

### Files
`coordinator.py` (base + per-source coordinators, runtime container),
`__init__.py` (build N coordinators, `async_migrate_entry`),
`config_flow.py` (API key, per-source enable, global allergens, VERSION=2),
`sources/polleninformation.py` (client), `sources/base.py` (allergen mapping
helper), `const.py` (pi catalogue + canonical mapping, config keys),
`sensor.py` (second per-source device), repair flow, translations, tests,
`manifest.json`, `HA_COMPATIBILITY.md`.

### Done
The live Open-Meteo entry **migrates cleanly** to the multi-source shape and
keeps working; enabling polleninformation with a key yields a second device with
raw sensors; an invalid key surfaces a repair issue. (Live second-source
verification waits for the API key — see §4.)

### Risks
1. **Config-entry migration of the LIVE instance** — top risk; see the migration
   protocol in §4. Must not break the running Graz setup
   ([[project-live-deployment]]).
2. **polleninformation API** — auth shape, rate limits, forecast structure,
   per-country species. Needs research (step 3) before the client.
3. **Allergen taxonomy mismatch** — pi species (country-dependent) must map to
   canonical keys; non-overlapping species stay source-local.

### Size
Medium-large: **~10–14 commits**; ~700–1000 lines + tests. The migration and the
API research are the long poles.

---

## 3. Milestone 3b — derived analytics (scoped, not started)

### Meaning
Cross-source and derived entities on top of the ≥2 sources from 3a.

### Implementation order (single-source first, then cross-source)
**recent_percentile → personal_score → consensus → divergence.** The
single-source analytics (percentile, personal score) don't depend on the
cross-source work and are proven first; recent_percentile is also the feature the
maintainer's planned indoor-environment advisor most wants ("is today's grass
high for the season").

### Files
`analytics.py` (pure consensus/divergence/percentile/personal-score),
`coordinator.py` (meta-coordinator over all source coordinators), `const.py`
(EAN grains/m³ → 0–4 thresholds per species), `sensor.py` (analytics entities +
analytics device), `config_flow.py` (personal-sensitivity multipliers in
options), tests.

### Done
For allergens covered by ≥2 sources: consensus level + divergence flag. Per
allergen: recent_percentile and personal_score. Personal multipliers in options.

### Risks
EAN threshold values (research); normalization across heterogeneous units;
precise recent_percentile definition; analytics entity/device model; card
compatibility (defer to v1.1 adapter, already in `TODO.md`).

### Open decisions for 3b (decide at 3b kickoff)
- **B1** analytics device model — separate "PollenWatch Analytics" device
  (lean) vs. attach to entry.
- **B2** `recent_percentile` exact definition (per-allergen, peak-based).
- **B3** consensus over single-source allergens — omit (lean; needs ≥2).

### Size
Medium-large: **~10–14 commits**; ~700–1000 lines + tests.

---

## 4. Decisions (approved 2026-05-29)

- **A1 — Single multi-source config entry**, per-source coordinators internally.
  An aggregator is one thing the user configured ("watch pollen at my location")
  with multiple backends; entry-per-source would fragment that and make 3b's
  analytics association fragile. Cost: a config-entry migration (below).
- **A2 — Global allergen selection** (not per-source). The user thinks "I'm
  allergic to grass and birch," not "grass from source X." Map the global
  selection onto what each source can provide; never create a sensor for an
  allergen a source lacks. Per-source selection is a power-user `TODO`.
- **A3 — All analytics stay in 3b** (don't expand 3a's scope; the migration is
  enough risk for one milestone). Within 3b, build **recent_percentile first**
  (see §3 order).
- **Source weighting** stays **equal** for v1.0 (kickoff Q2, in 3b);
  **languages** stay **en + de** (kickoff Q4). Both still deferred.

### Migration protocol (top risk — the live Graz instance must survive)
- `ConfigFlow.VERSION = 2` + `async_migrate_entry` converting the v1 single-
  source shape to the v2 multi-source shape.
- **Test the migration against a copy of the live entry's data shape** in the
  unit suite (construct the v1 dict, run the migration, assert the v2 result)
  **before** deploying. Note: HA's API doesn't expose `entry.data`, so the v1
  shape is reconstructed from what setup wrote (`latitude`/`longitude`/
  `allergens` in `data`; `allergens`/`update_interval` in `options`) — called out
  honestly in the test and report.
- Deploy is the highest-risk yet: document the current entry state first so it
  can be manually restored (worst case = remove + re-add Graz; low stakes, only
  lat/lon/allergens). Migration must be idempotent and never partially mutate.

### Per-source coordinator refactor — blast radius (assessed, bounded)
Adopting the pattern is a **bounded plumbing refactor, not a rewrite of working
code**. The single-coordinator `runtime_data` shape is referenced in 4 files:
`__init__.py` (3 lines), `sensor.py` (~5 refs), `config_flow.py` (only the
`PollenWatchConfigEntry` type alias + the pure `_entry_option` helper — neither
depends on the coordinator's internals), and `coordinator.py` (definitions).
**The source clients and all fetch/parse logic in `sources/` are untouched** —
only the runtime container (single coordinator → `dict[str, coordinator]`) and
the wiring change. Existing tests assert on states/entities (not `runtime_data`),
so they validate the refactor as-is. Done as **step 1 of 3a, isolated**, so the
blast radius stays observable (Open-Meteo keeps working through the new
container before polleninformation is added). **Recommendation: proceed.**

### Floor bump
Adopting the 2026.5 per-source pattern raises the declared HA minimum to
**2026.5.0**; `HA_COMPATIBILITY.md` updated with the rationale. Safe: the
maintainer runs 2026.5.4.

### Mocked vs. live (API key pending)
The polleninformation API key is still pending from the Austrian team. 3a builds
and tests the client against **mocked responses + the documented API shape**;
the **live second-source verification waits for the key**. The 3a completion
report will state clearly what is tested-mocked vs. tested-live. The refactor +
migration + Open-Meteo are verified **live**; polleninformation ships ready but
disabled until the key arrives.

---

## 5. polleninformation API — probe findings (2026-05-29)

Endpoint: `GET https://www.polleninformation.at/api/forecast/public`; params
`country` (ISO-2), `lang`, `latitude`, `longitude`, `apikey` (+ mobile UA,
Accept JSON). Probed live (Graz AT, Berlin DE, NYC US) with the real key (key
kept out of git — env var only).

**Response** (HTTP 200), top-level keys `contamination`, `allergyrisk`,
`allergyrisk_hourly`:
- `contamination`: list of allergens, each `{poll_id, poll_title,
  contamination_1..4}`.
  - `poll_id` = stable int; `poll_title` = English + Latin in parens.
  - `contamination_N` = **0–4 index** for day N (1 = today … 4 = +3 days).
    **Daily, not hourly.**
- `allergyrisk`: overall daily risk `{allergyrisk_1..4}` on a wider scale (saw
  8/8/8/5) — an aggregate, not per-allergen.
- `allergyrisk_hourly`: overall, 4 days × 24 hourly.

**Canonical allergen → poll_id** (all six present for AT): alder=1, birch=2,
grass=5, mugwort=7, olive=18, ragweed=6.

**Coverage / behavior:**
- Allergen set is **country-dependent** (AT=18, DE=8). Global selection maps
  onto what's present; absent allergens get no sensor (matches A2).
- Unsupported location → **HTTP 200 with `{"error": ...}`** (not a 4xx). Detect
  coverage via the error key — an echo of the Open-Meteo HTTP-400 lesson.
- Auth failure → 401/403 → repair flow. No rate-limit headers observed.
- **`country` (ISO-2) is required** — lat/lon alone is not enough.

**Discrepancies vs assumptions:** "0–4 native" confirmed; "14 countries" is
actually **13** (AT,CH,DE,ES,FR,GB,IT,LV,LT,PL,SE,TR,UA); and the data is a
**daily 0–4 index**, not hourly grains/m³ like Open-Meteo.

**Leans (pending maintainer decisions on country + index representation):** store
the 4 daily values in the existing `SourceResult` (times = dates) so the
sensor's daily-peak forecast works unchanged; `current` = `contamination_1`;
ignore the overall `allergyrisk` for v1.0; pi sensors expose the native 0–4
index (3b normalizes across sources).

## 6. Beyond milestone 3
DWD Pollenflug (the third v1.0 source) is a later source-addition milestone
mirroring the 3a pattern. The pollenprognos-card adapter stays a v1.1 item
(`TODO.md`).
