# PollenWatch

[![Release](https://img.shields.io/github/v/release/TheDave94/pollenwatch?include_prereleases&sort=semver&color=E8920C)](https://github.com/TheDave94/pollenwatch/releases)
[![Validate](https://github.com/TheDave94/pollenwatch/actions/workflows/validate.yml/badge.svg)](https://github.com/TheDave94/pollenwatch/actions/workflows/validate.yml)
[![Lint & Test](https://github.com/TheDave94/pollenwatch/actions/workflows/lint.yml/badge.svg)](https://github.com/TheDave94/pollenwatch/actions/workflows/lint.yml)
[![hacs](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![License: MIT](https://img.shields.io/badge/License-MIT-2A3540.svg)](LICENSE)

![PollenWatch — multi-source European pollen for Home Assistant](brand/assets/repo-banner.png)

A multi-source European pollen aggregator for Home Assistant. The Home Assistant
ecosystem already has ~10 pollen integrations that each wrap a *single*
provider; PollenWatch instead **combines independent sources** and adds a
**cross-source analytics layer** on top. That combination is the point.

> [!NOTE]
> **PollenWatch is a personal project shared publicly.** Stable means the
> maintainer relies on it daily. It ships a bundled Lovelace severity-gauge
> card that is auto-registered on install — one HACS install delivers both.
> v2.0 expands tracked species from the original 6 to **24 canonical species
> across trees, grasses, herbs and spores**; you pick which ones to materialize
> as entities at setup (preselected from your country) and can change the
> selection any time in **Options**. See **[Known limitations](#known-limitations)**
> below for honest disclosure of the open items.
>
> **Existing v1.x installs upgrade losslessly:** the migration renames the
> stored allergen key, preserves every entity_id, and does not change your
> selection. No action required on your part.
>
> Minimum Home Assistant **2024.11.0** (see
> [HA_COMPATIBILITY.md](HA_COMPATIBILITY.md) for the API audit).

## Sources

Each source is optional except Open-Meteo, and **what you get depends on your
location**: outside Germany you get no DWD; outside Switzerland no MeteoSwiss;
outside Bavaria no ePIN; outside the 13 polleninformation countries you get only
Open-Meteo (all of Europe) and Google (global, if enabled).

| Source | Coverage | API key | Notes |
| --- | --- | --- | --- |
| **Open-Meteo (CAMS)** | All of Europe | none | **Always-on primary.** 6 species, hourly, 5-day **forecast**, 92-day backfill. |
| **polleninformation.at** | 13 countries¹ | **free key required** | Optional. Daily 0–4 index **forecast**; more species, country-dependent. |
| **DWD Pollenflug** | **Germany only** | none | Optional. Daily 7-point regional index **forecast**; you pick your DWD region. |
| **MeteoSwiss** | **Switzerland only** | none | Optional, **observation-only**. Hourly grains/m³; nearest of 19 automatic stations auto-picked. Covers alder/birch/grass. |
| **ePIN (Bavaria)** | **Bavaria only** | none | Optional, **observation-only**. 3-hourly grains/m³; nearest of 8 automatic stations auto-picked. No olive. |
| **Google Pollen** | **Global** | **billing-gated key**² | Optional, **consensus-only**³. UPI 0–5 index, 5-day **forecast**, all 6 allergens (**only source with olive**). |

¹ AT, CH, DE, ES, FR, GB, IT, LV, LT, PL, SE, TR, UA.
² Requires a Google Cloud project with the Pollen API enabled **and a billing
account** (free tier ~5,000 req/month, but a payment method must be on file) —
more involved than the other sources' free keys.
³ **Consensus-only:** Google's Maps Platform terms forbid caching/storing
forecast results, so Google feeds consensus/divergence and gets a raw sensor +
forecast + personal_score, but is **never** baselined into recent_percentile.

**Forecast vs observation:** Open-Meteo, polleninformation, DWD and Google
provide a *forward forecast* (today + coming days). MeteoSwiss and ePIN are
*observation networks* — they report measured concentrations up to the latest
reading, with **no tomorrow value**, so their sensors show the current/most-recent
reading and today's running peak rather than a multi-day outlook.

PollenWatch tracks **24 canonical species** spanning trees, grasses, herbs and
one spore — covering everything any of the six sources can publish, plus the
EAACI/D'Amato high- and moderate-potency set. Open-Meteo is the largest-coverage
source (the CAMS-canonical 6); polleninformation, DWD, ePIN, MeteoSwiss and
Google each add their own subset (e.g. ash, oak, hazel, rye, plane_tree, cypress,
plantago, alternaria). At setup you choose which species to materialize as
entities; the per-country preselection seeds a defensible starting set.
A source only produces sensors for species it actually reports at your location.
See [Entities](#entities) for the honest data-availability picture.

## Analytics

On top of the raw per-source sensors:

- **recent_percentile** — today's level versus the recent window (per source).
  Open-Meteo (92-day backfill) and MeteoSwiss (months of recent hourly data)
  compute it on day one from their own history; polleninformation, DWD and ePIN
  baseline on Home Assistant recorder history and honestly report "insufficient
  history" until ~2 weeks accrue (and "off_season" when the whole window is
  zero). **Google is excluded** — its licence forbids storing forecasts, so it
  gets no percentile (it still feeds consensus and gets a raw sensor).
- **personal_score** — a source's raw value × your per-species sensitivity
  multiplier (0.0–2.0), for personal-threshold automations.
- **consensus + divergence** *(cross-source)* — sources are compared on a common
  **3-level scale derived from the EAACI / Copernicus CAMS thresholds** (each
  source's native scale is bucketed or collapsed onto it — see
  [ANALYTICS.md](ANALYTICS.md), where every threshold is sourced, not invented).
  **consensus** is categorical — `none` / `low` / `high` / `mixed` — and carries
  `source_count` + `max_possible_sources` so the card can render the `n/m`
  authority badge. A single-source species (`1/m`) gets a consensus reading
  pass-through (no `mixed` is ever emitted) plus the card's visual humbling.
  **divergence** is a binary flag, only emitted when ≥2 sources actually
  disagree by more than one level. Note the
  [#1](https://github.com/TheDave94/pollenwatch/issues/1) lone-higher edge
  above (reachable when 3+ sources cover a species).

## Installation

PollenWatch is not in the default HACS store yet. Add it as a custom repository:

1. In Home Assistant, open **HACS → Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/TheDave94/pollenwatch` with category **Integration**.
3. Install **PollenWatch**, then restart Home Assistant (minimum HA 2024.11.0).
4. Go to **Settings → Devices & Services → Add Integration** and search for
   **PollenWatch**.

## Setup & configuration

Setup is a two-step wizard with Open-Meteo on by default.

**Step 1 — Location.** Pick the point to monitor on the map (defaults to your
Home Assistant location). Open-Meteo snaps it to the nearest ~10 km CAMS grid
cell; setup is refused if the location is outside CAMS European coverage.
**Location is fixed once set** (to keep recorder history and the percentile
baseline coherent). To move it, remove and re-add the integration. You can
add PollenWatch more than once for several locations.

**Step 2 — Species.** A checkbox list of all 24 species, **preselected from
your Home Assistant country** via the region-defaults table (e.g. AT/DE/CH
get the Central-European set + ash/oak; IT/ES add olive/cypress/nettle_family;
SE skips Mediterranean species; UK gets plane_tree). The maintainer's
recommendation is the starting point — uncheck what you don't want, check
extras that matter to you. `alternaria` (a fungal spore, not pollen) is the
single deliberate opt-in: never preselected, available if you want it.

In the integration's **Options** (after setup) you can change the selection
and update interval, set **personal sensitivity** multipliers per species, and
enable the optional sources:

- **polleninformation.at** — toggle on, pick your country, and paste a free API
  key (requested from polleninformation.at). Stored encrypted in HA.
- **DWD** — toggle on and pick your DWD region (Germany only; enabling it for a
  non-German location is rejected as out-of-coverage).
- **MeteoSwiss** (Switzerland) and **ePIN** (Bavaria) — just toggle on; no key,
  no region. The nearest measuring station to your location is picked
  automatically (shown in the option description and as a `station` attribute on
  the sensors). Enabling either outside its country/region is rejected as
  out-of-coverage.
- **Google Pollen** (global) — toggle on and paste an API key. **Read the option
  text first:** this needs a Google Cloud project with the Pollen API enabled
  **and a billing account attached** (there is a free tier, but Google requires a
  payment method on file) — it is more involved than the other keys. Stored
  encrypted in HA. Google is consensus-only (no recent_percentile).

Changing the selection later prunes any deselected species cleanly — the
entities and their device are removed from the registry, not left as
permanently-`unavailable` orphans.

## Entities

Raw sensors live under a per-source device (e.g. "PollenWatch Open-Meteo",
"PollenWatch MeteoSwiss", "PollenWatch ePIN"):
`sensor.pollenwatch_<source>_<species>` (state = that source's current value;
attributes include a daily-peak forecast and provenance — and, for the
station-based sources, the picked `station`). Source-specific derived sensors
sit alongside them: `..._<species>_recent_percentile` and
`..._<species>_personal_score`.

The cross-source metrics live under a separate **"PollenWatch Analytics"**
device: `sensor.pollenwatch_analytics_<species>_consensus` (categorical
none/low/high/mixed; carries `source_count` + `max_possible_sources` so the
card can render the `n/m` badge) and
`binary_sensor.pollenwatch_analytics_<species>_divergence` (binary flag, only
emitted when ≥2 sources actually disagree).

### How many entities will I see?

The entity-count table below is a **ceiling, not a promise** — it's the count
you'd get if every source you enable also covered every species you select.
Real installations almost always fall under it because of the data-availability
matrix.

The formula has two parts:
- **Per-source entities** = species × (3 if the source has recent_percentile, 2 if not). The five non-Google sources have percentile; Google omits it (its licence forbids storing forecasts).
- **Analytics entities** = species × (2 if covered by ≥2 enabled sources: consensus + divergence; 1 if covered by 1: consensus only).

| Selected species × sources enabled | Per-source ceiling | Analytics ceiling | Total ceiling |
|---|---|---|---|
| **6 species, 1 source** (Open-Meteo only) | 6 × 3 = 18 | 6 × 1 = 6 | **≤ 24** |
| **6 species, 2 sources** (Open-Meteo + DWD) *— clean-room Munich; **measured 44** because DWD has no olive* | 6 × 3 × 2 = 36 | 6 × 2 = 12 | **≤ 48** |
| **8 species, 4 sources** (AT default + DWD + ePIN, no Google) | 8 × 3 × 4 = 96 | 8 × 2 = 16 | **≤ 112** |
| **+ adding Google** to any of the above | + species × 2 | unchanged | + species × 2 |

A real install almost always lands well under the ceiling: actual coverage is
sparse (e.g. ePIN measures plantago + urtica but not olive; DWD has no olive;
MeteoSwiss only covers alder/birch/grass + beech). The clean-room verification
above shows a worked example — Munich's 6 × 2 ceiling of 48 came in at 44 measured.

**The honest data-availability picture (one paragraph):** not every species is
reported by every source — the matrix is asymmetric by design (DWD covers
Germany-relevant species, ePIN covers Bavaria-specific species like plantago
and urtica, MeteoSwiss measures only alder/birch/grass and beech, Google adds
olive globally). A species you've selected that **no enabled source covers at
your location simply does not materialize an entity** — selection bounds the
blowup; you don't get permanently-`unavailable` orphans. A species **one source
covers** still gets a consensus entity (badge reads `1/n`, with the gauge in
single-source mode — desaturated, with an explicit "single source" label, so the
honesty gradient is visible at a glance). The 3-level scale itself
(`none`/`low`/`high`) and its grains/m³ boundaries are sourced from
EAACI/Pfaar position papers and used by CAMS/Climate-ADAPT (see
[ANALYTICS.md](ANALYTICS.md)). v2.2 lands the per-species evidence-tier
review from [#3](https://github.com/TheDave94/pollenwatch/issues/3):
every raw and consensus sensor now carries a `threshold_status` attribute
classifying the species into one of 5 tiers — `species_specific` (peer-reviewed
per-species cutoff exists; 13 species), `family_eaaci` (EAACI's actual family
group, no species refinement; 5 species), `established_no_threshold`
(characterised allergen but no published numeric cutoff, working bracket
carried; 3 species), `family_analogy` (analogy-only, weakest; 2 species), and
`fungal` (Alternaria, separate evidence base). v2.2 also refines 6 numeric
brackets per the same review (ragweed 5/20, olive 10/200, birch 20/100, alder
45/80, hazel 35/80, mugwort 3/50 — see the v2.2 release notes for the cited
basis per species).

## Dashboard card

A combined-consensus severity gauge ships with the integration and is
auto-registered as a Lovelace resource on install — no manual resource step.
Add it to any dashboard:

```yaml
type: custom:pollenwatch-card
species: grass            # any of the 24 canonical species keys
                          # (alder, birch, grass, hazel, mugwort, olive, ragweed, rye,
                          #  ash, oak, beech, carpinus, juglans, elm, plane_tree,
                          #  cypress_family, holm_oak, plantago, urtica, nettle_family,
                          #  rumex, chenopodium, asteraceae, alternaria)
show_mixed_span: false    # optional; when true, the 'mixed' caption names
                          # the conflicting span (e.g. 'none–high · across 5 sources')
expanded_default: false   # optional; show per-source breakdown expanded by default
```

The gauge has six honest states — `none`, `low`, `high`, `mixed`, `unknown`,
`nodata` — with deliberately distinct treatments for missing data (gray, no
needle) so an empty reading never visually resembles a safe-low one. A small
`n/m` badge in the top-right shows how many of your enabled sources currently
cover this species; single-source readings (`1/m`) get a desaturated gauge plus
an explicit "single source" label so the honesty gradient is visible at a
glance. See [`brand/GAUGE_SPEC.md`](brand/GAUGE_SPEC.md) for the full spec.
Per-species breakdown is one click away — each source's native reading
(grains/m³, DWD's 7-point string, polleninformation's 0–4 index, Google's UPI
0–5) on demand. Adapts to HA's light + dark themes; brand severity ramp stays
constant per spec.

### Using the pollenprognos-card

[pollenprognos-card](https://github.com/krissen/pollenprognos-card) does not yet
auto-detect PollenWatch. Until a dedicated adapter exists, map the raw sensors
with the card's manual configuration (e.g. entity prefix
`pollenwatch_open_meteo_`).

## Attribution

PollenWatch's data carries these required attributions:

> Generated using Copernicus Atmosphere Monitoring Service information.
> Pollen data via Open-Meteo.com.

> © Polleninformation Austria

> © Deutscher Wetterdienst (DWD)

> Source: MeteoSwiss

> Source: ePIN, Bayerisches Landesamt für Gesundheit und Lebensmittelsicherheit (LGL)

> Source: Includes pollen data from Google

## Known limitations

Honest disclosures, not blockers — these describe the state of a project the
maintainer uses daily.

- **Consensus has a lone-higher edge** ([#1](https://github.com/TheDave94/pollenwatch/issues/1)):
  with ≥ 3 sources, a single higher reading can pull the consensus up without
  flagging divergence. The gauge surfaces `mixed` cleanly when sources differ
  by more than one level, but the adjacent-level `{1,1,2}` case still resolves
  to the higher (`high`). Under investigation for a future release; tracked
  in the [REVIEW_QUEUE](REVIEW_QUEUE.md).
- **Per-source maturity is uneven.** Open-Meteo, polleninformation and Google
  run on the maintainer's live HA. **DWD, MeteoSwiss and ePIN** are
  validated against the live feeds and exercised on a maintainer-side throwaway
  HA in Munich; they have **not yet run in normal end-user installations**, so
  enabling one of those is its first real-world run. Please
  [open an issue](https://github.com/TheDave94/pollenwatch/issues) if anything
  looks off.
- **Per-species threshold-evidence tiers are now classified** but the
  underlying number is *evidence-graded, not certainty-graded*
  ([#3](https://github.com/TheDave94/pollenwatch/issues/3), v2.2 review).
  The 3-level scale (`none`/`low`/`high`) and its grains/m³ boundaries are
  EAACI/Pfaar-sourced and CAMS/Climate-ADAPT-used. Per-species evidence sits
  in 5 tiers exposed as the `threshold_status` attribute on every raw and
  consensus sensor — see the Entities section above. Important honest
  caveats from the review: Tier-2 "numbers" are *ranges, not points* (birch
  20–155 across studies, olive 162–400, grass explicitly "no consensus"); the
  threshold concept itself is contested (a recent EJACI study argues there's
  no threshold below which sensitive people feel nothing — symptoms rise from
  the first grains); per-spore allergen content varies up to 15× day-to-day
  for alternaria. The five-tier label tracks **evidence provenance**, not
  clinical certainty.
- **v2.2 numeric refinements (behavior change).** Six species got refined
  brackets per the review: ragweed (3/50 → 5/20 — was under-warning), olive
  (10/100 → 10/200 — was over-warning regionally), birch (10/100 → 20/100 —
  peak validated by Struß 2025 controlled chamber, low refined per
  Aerobiologia 2021), alder (10/100 → 45/80 — Rapiejko 2007 per-species
  evidence), hazel (10/100 → 35/80 — same), mugwort (10/100 → 3/50 — fixes a
  v1 class-error: mugwort is a herb, not a tree). Existing entities may flip
  state on upgrade (e.g. olive at 150 grains/m³ was `high`, becomes `low`);
  entity_ids are preserved, only state values change.
- **alternaria is a fungal spore, not pollen** — kept opt-in (never
  preselected). Useful for people who track it alongside pollen; safe to
  ignore otherwise.
- **Per-region default selection is a starting recommendation, not a
  prescription.** The country-default table is maintained by the project, not
  a clinical authority; it's a defensible v1 of "what most people in this
  country are likely to want." Adjust freely in Options at any time.

## Brand & design

Brand identity, design tokens, the gauge spec and reference state SVGs live in
[`brand/`](brand/) — the design source-of-truth.

## License

[MIT](LICENSE)
