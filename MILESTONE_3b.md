# Milestone 3b — derived analytics layer

> **Status:** approved 2026-05-29 — decisions in §5 resolved (3-level sourced
> scale, entity model, recent_percentile method). Building in order, starting
> with recent_percentile. Thresholds + level scale live in `ANALYTICS.md`.

## 1. Foundation decision (settled)

All cross-source comparison happens on a common **level** scale, not raw values.
- polleninformation is natively a 0–4 index — used as-is.
- Open-Meteo (grains/m³) is **bucketed down** to a level via published per-species
  thresholds. Direction is fixed: continuous → level, never level → concentration.
- Raw per-source sensors (grains/m³, native 0–4) are **untouched**; bucketing is
  internal to the analytics layer. Consensus is inherently a coarsening, so
  comparing at level granularity is honest.
- The level abstraction is reusable — future sources (DWD 0–3, …) slot in.

(See [[project-live-deployment]]; two sources are live accumulating data.)

## 2. Build order (each its own commit; mocked tests then live verify)

thresholds research → bucketing → **recent_percentile** → personal_score →
consensus → divergence. recent_percentile first: it's single-source and needs no
cross-source work, and is what the maintainer's indoor-env advisor most wants.

## 3. Step 1 — threshold research (DONE; gate hit)

Full findings + citations in `ANALYTICS.md`. Summary:
- **Authoritative & citable:** EAACI (Pfaar 2017/2020), used by Copernicus
  CAMS / Climate-ADAPT — but only **two** boundaries per species group
  (season onset, peak): alder/birch/olive/mugwort = 10 / 100; grass/ragweed =
  3 / 50 grains/m³.
- **Does not exist:** an authoritative *cited* **4-band per-species** table. The
  online 4-band tables are uncited operational conventions — adopting them =
  inventing numbers (gate forbids).
- **Consequence / GATE:** authoritative data supports a **3-level** scale
  (below-season / season→peak / at-peak), not the 5-level (0–4) the index uses.
  This conflicts with §1's implicit 0–4 assumption → **maintainer decision
  needed** before bucketing (see §5).

## 4. Proposed entity/device model (B1 — for approval)

- **Keep source-specific derived metrics with their source.** Under each existing
  per-source device, add that source's `recent_percentile` and `personal_score`
  companions (lineage preserved, consistent with the per-source device model).
  - `sensor.pollenwatch_<source>_<species>_recent_percentile`
  - `sensor.pollenwatch_<source>_<species>_personal_score`
- **New "PollenWatch Analytics" device** for the genuinely cross-source metrics:
  - `sensor.pollenwatch_consensus_<species>` (level, or "mixed")
  - `binary_sensor.pollenwatch_divergence_<species>` (boolean → new
    `binary_sensor` platform)

This matches the maintainer's lean (separate Analytics device for
consensus/divergence; personal_score with its source) and extends it to
recent_percentile (also source-specific).

## 5. Decisions (approved 2026-05-29)

- **D1 — Level granularity: 3-level sourced scale (option A).** 0 = below onset,
  1 = in season, 2 = at/above peak — every edge an EAACI/CAMS boundary. The
  polleninformation 0–4 index collapses `0→0, 1–2→1, 3–4→2`, labelled in
  ANALYTICS.md as an **operational alignment** (not a sourced equivalence). No
  4-band table invented. alder/mugwort thresholds carry the "extrapolated, not
  independently sourced" caveat.
- **D2 — Entity/device model: approved as §4.** Source-specific
  recent_percentile + personal_score under each per-source device; a separate
  "PollenWatch Analytics" device for cross-source consensus (sensor) and
  divergence (binary_sensor).
- **D3 — recent_percentile: approved**, method locked in ANALYTICS.md — empirical
  midrank percentile of today's **daily peak** vs the trailing **92-day** daily
  peaks; Open-Meteo day-one via backfill; polleninformation recorder-baselined
  with an honest "insufficient history" state until ~2–4 weeks.

**Carried forward:** equal source weighting (kickoff Q2), en/de only (Q4),
divergence ">1 level" threshold to revisit in REVIEW_QUEUE after real data.

## 6. Build status
Gate cleared. Building in order: **recent_percentile first** (Open-Meteo backfill
path, then the polleninformation recorder/insufficient-history mechanism), with
mocked tests, then live verification — checkpoint report before personal_score.
