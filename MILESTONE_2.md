# Milestone 2 — End-to-end Open-Meteo in Home Assistant

> **Status:** approved 2026-05-29 — implementation in progress. Decisions in §5.

## 1. What this milestone means, concretely

Turn the proven standalone Open-Meteo data layer into a real, installable HA
integration that produces live pollen sensors — **one source only
(Open-Meteo/CAMS), no analytics, no second source.**

A user can install via HACS custom repo, configure a location through the UI,
and get per-allergen sensors whose state is the current grains/m³ value and
whose attributes carry the forecast.

### Files needing real implementation

| File | Work |
| --- | --- |
| `const.py` | Add config keys (`CONF_*`), defaults (update interval, allergens), platform list. |
| `sources/open_meteo.py` | Add an **async** fetch path (reusing the existing pure `parse()`); see Risk 1. |
| `config_flow.py` | `ConfigFlow` user step: location + allergen multi-select, runs a coverage probe and aborts if out-of-coverage. Minimal options flow (see Q3). Multi-instance via unique_id. |
| `__init__.py` | `async_setup_entry` / `async_unload_entry`; create coordinator, store in `entry.runtime_data`, forward to the sensor platform. |
| `coordinator.py` | `OpenMeteoCoordinator(DataUpdateCoordinator)`, 1-hour update interval, async fetch, error → `UpdateFailed`. (Meta-coordinator is milestone 3.) |
| `sensor.py` | One `SensorEntity` per selected allergen. State = current value; attributes = forecast + snapped coords + attribution. Device + unique_id per Q1/Q2. |
| `translations/en.json`, `de.json` + `strings.json` | Flesh out to match the real config/options flow fields (Silver requires `strings.json`). |
| `manifest.json` | Add `codeowners: ["@TheDave94"]`, bump `version` 0.0.1 → 0.1.0 (first version that does something in HA; 0.2.0 reserved for the second source). `requirements` stays `[]` (Open-Meteo needs no third-party lib). |
| `tests/` | Config-flow test (success + out-of-coverage abort), coordinator test, sensor test. Adds the HA test harness — see Risk 5. |
| `README.md` | Add a "Install via HACS custom repository" section. |

**Deferred to later milestones (NOT in milestone 2):** `analytics.py`,
meta-coordinator, `diagnostics.py` (Gold-tier, optional), personal sensitivity,
`polleninformation.py`, `dwd.py`.

## 2. Implementation order (bottom-up, so each layer has a real thing to build on)

1. **`const.py`** — config keys/defaults everything imports.
2. **Async fetch in `open_meteo.py`** — the data path the coordinator needs;
   reuses `parse()`, so it's small. Verify against live Graz before moving on.
3. **`config_flow.py`** — needed before anything loads (no YAML setup), and lets
   us unit-test entry creation + the coverage-probe abort early.
4. **`coordinator.py`** — the hourly fetch loop.
5. **`__init__.py`** — wire coordinator + forward to sensor platform.
6. **`sensor.py`** — entities (the visible payoff).
7. **`translations` / `strings.json`** — once flow fields are final.
8. **`manifest.json`** — codeowners + version bump.
9. **Tests + README** — lock it in.

Rationale: build the data path before the UI surface, so by the time
`sensor.py` exists the data is already known-good. Config flow comes early only
because nothing can load without it.

## 3. What "done" looks like

- `pollenwatch` installs cleanly via **HACS custom repository** on a **test HA**
  (not your live instance).
- Add Integration → PollenWatch → form pre-filled with HA's lat/lon (editable),
  allergen multi-select.
- Setup runs a coverage probe; a non-European location is rejected with a clear
  "outside CAMS European coverage" message (via the HTTP-400 signal, not
  all-zeros).
- After setup with Graz: sensors `sensor.pollenwatch_graz_grass` (+ other
  selected species) exist, state = current grains/m³, attributes = forecast +
  requested/snapped coords + CAMS attribution + last updated.
- Hourly auto-refresh works; reload/unload works without errors.
- `pytest`, `ruff`, hassfest, and HACS validate all green in CI.

Explicitly **not** in the done state: consensus/divergence/percentile, personal
scoring, a second source, the pollenprognos-card actually rendering us.

## 4. Risks / unknowns to flag before starting

1. **Sync → async — APPROVED.** Add an async fetch using HA's shared `aiohttp`
   session and reusing the pure `parse()`; keep the sync `fetch()` too. The
   source module was designed for this split.
2. **`past_days` payload — resolved.** Coordinator fetches `past_days=0,
   forecast_days=5` to keep the hourly request small; bump only when the
   milestone-3 percentile needs history.
3. **Forecast attribute shape — resolved (see Q4).** Aggregate hourly → a 4-day
   **daily peak** forecast to avoid recorder bloat.
4. **No native HA pollen `device_class`.** Plan: `state_class=measurement`,
   `native_unit="grains/m³"`, custom icon. Low risk, just noting it.
5. **HA test harness.** Integration tests need
   `pytest-homeassistant-custom-component`, which pins a HA core version. Adds CI
   install time and a version to keep current. Unavoidable for Silver.

## 5. Design decisions (approved 2026-05-29)

- **Q1 — Device model: PER-SOURCE.** Each source gets its own HA device. With
  multi-source as the integration's defining feature, source-per-device makes
  data lineage visible (users see which source each sensor belongs to), which
  pays off when analytics arrive in milestone 3+. Milestone 2 creates the
  "Open-Meteo (CAMS)" device.
- **Q2 — Entity naming / pollenprognos-card: RESEARCH FIRST.** Read
  krissen/pollenprognos-card's adapter pattern for its supported integrations
  and learn the convention before deciding whether to constrain our naming now
  or accept a v1.1 alias. **No sensor code is written until the card docs are
  read and a findings summary is added to §7 below.**
- **Q3 — Options flow: MINIMAL, included.** Options flow can change selected
  allergens + update interval (delete+re-add to change those would be bad UX).
  Personal sensitivity stays in milestone 3 with analytics.
- **Q4 — Forecast aggregation: DAILY PEAK, 4 DAYS.** Peaks drive allergic
  reactions; day 5 is partially null. Mean / day-5 best-effort can become
  options later if anyone asks.
- **Q5 — lat/lon: LOCKED AT SETUP.** Changing location mid-life invalidates the
  recent-percentile feature and creates "same instrument?" ambiguity the
  recorder handles poorly. README documents: remove + re-add to change location.

**Still deferred (carried forward, not auto-resolved):** kickoff **Q2** source
weighting (milestone 3 analytics; equal weighting for v1.0) and kickoff **Q4**
languages beyond en/de (staying en + de for v1.0).

## 7. pollenprognos-card naming — findings (TBD before sensor.py)

_To be filled in from the card research task, before `sensor.py` is written._

## 6. Estimated size

- **~9–11 commits**, one logical change each (roughly mirroring §2 + the CI/test
  wiring).
- **Medium**: ~600–900 lines of real implementation + ~200–300 lines of tests.
- The async fetch, coordinator, and `__init__` are small; `config_flow.py` and
  `sensor.py` are the bulk.
