# PollenWatch

[![Validate](https://github.com/TheDave94/pollenwatch/actions/workflows/validate.yml/badge.svg)](https://github.com/TheDave94/pollenwatch/actions/workflows/validate.yml)
[![Lint & Test](https://github.com/TheDave94/pollenwatch/actions/workflows/lint.yml/badge.svg)](https://github.com/TheDave94/pollenwatch/actions/workflows/lint.yml)
[![hacs](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)

A multi-source European pollen aggregator for Home Assistant. The Home Assistant
ecosystem already has ~10 pollen integrations that each wrap a *single*
provider; PollenWatch instead **combines independent sources** and adds a
**cross-source analytics layer** on top. That combination is the point.

> **Status: release candidate (v1.0.0-rc1) — feature-complete, validating.**
> Not yet declared stable. Two things to know before you rely on it:
> - **DWD has never run in production.** Its data path is validated against the
>   live DWD feed and mocked tests, but the maintainer is outside DWD coverage
>   (Austria), so a German user enabling DWD is its first real-world run —
>   please [open an issue](https://github.com/TheDave94/pollenwatch/issues) if
>   anything looks off.
> - **Consensus has a known 3-source edge** ([#1](https://github.com/TheDave94/pollenwatch/issues/1)):
>   with ≥3 sources, a lone higher reading can pull the consensus up without
>   flagging divergence. Documented and deferred for a redesign.
>
> Minimum Home Assistant **2024.11.0** (see
> [HA_COMPATIBILITY.md](HA_COMPATIBILITY.md) for the API audit).

## Sources

Each source is optional except Open-Meteo, and **what you get depends on your
location**: outside Germany you get no DWD; outside the 13 polleninformation
countries you get only Open-Meteo (which covers all of Europe).

| Source | Coverage | API key | Notes |
| --- | --- | --- | --- |
| **Open-Meteo (CAMS)** | All of Europe | none | **Always-on primary.** 6 species, hourly, 5-day forecast, 92-day backfill. |
| **polleninformation.at** | 13 countries¹ | **free key required** | Optional. Daily 0–4 index; more species, country-dependent. |
| **DWD Pollenflug** | **Germany only** | none | Optional. Daily 7-point regional index; you pick your DWD region. |

¹ AT, CH, DE, ES, FR, GB, IT, LV, LT, PL, SE, TR, UA.

PollenWatch tracks six canonical allergens — **alder, birch, grass, mugwort,
olive, ragweed**. Not every source covers every one (e.g. DWD has no olive); a
source only produces sensors for the allergens it actually reports at your
location.

## Analytics

On top of the raw per-source sensors:

- **recent_percentile** — today's level versus the recent window (per source).
  Open-Meteo computes it on day one from its 92-day backfill; the other sources
  baseline on Home Assistant recorder history and honestly report
  "insufficient history" until ~2 weeks accrue (and "off_season" when the whole
  window is zero).
- **personal_score** — a source's raw value × your per-species sensitivity
  multiplier (0.0–2.0), for personal-threshold automations.
- **consensus + divergence** *(cross-source)* — for any allergen ≥2 sources
  cover. Sources are compared on a common **3-level scale derived from the
  EAACI / Copernicus CAMS thresholds** (each source's native scale is bucketed
  or collapsed onto it — see [ANALYTICS.md](ANALYTICS.md), where every threshold
  is sourced, not invented). **consensus** is categorical — `none` / `low` /
  `high` / `mixed` — and **divergence** is a binary flag that turns on when the
  sources genuinely disagree. Note the [#1](https://github.com/TheDave94/pollenwatch/issues/1)
  3-source edge above.

## Installation

PollenWatch is not in the default HACS store yet. Add it as a custom repository:

1. In Home Assistant, open **HACS → Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/TheDave94/pollenwatch` with category **Integration**.
3. Install **PollenWatch**, then restart Home Assistant (minimum HA 2024.11.0).
4. Go to **Settings → Devices & Services → Add Integration** and search for
   **PollenWatch**.

## Setup & configuration

Initial setup (Open-Meteo):

- **Location** — pick the point to monitor on the map (defaults to your Home
  Assistant location). Open-Meteo snaps it to the nearest ~10 km CAMS grid cell;
  setup is refused if the location is outside CAMS European coverage.
- **Allergens** — choose from alder, birch, grass, mugwort, olive, ragweed.
- **Location is fixed** once set (to keep recorder history and the percentile
  baseline coherent). To move it, remove and re-add the integration. You can add
  PollenWatch more than once for several locations.

In the integration's **options** (after setup) you can change allergens and the
update interval, set **personal sensitivity** multipliers, and enable the
optional sources:

- **polleninformation.at** — toggle on, pick your country, and paste a free API
  key (requested from polleninformation.at). Stored encrypted in HA.
- **DWD** — toggle on and pick your DWD region (Germany only; enabling it for a
  non-German location is rejected as out-of-coverage).

## Entities

Raw sensors live under a per-source device (e.g. "PollenWatch Open-Meteo"):
`sensor.pollenwatch_<source>_<allergen>` (state = that source's current value;
attributes include a daily-peak forecast and provenance). Source-specific
derived sensors sit alongside them:
`..._<allergen>_recent_percentile` and `..._<allergen>_personal_score`.

The cross-source metrics live under a separate **"PollenWatch Analytics"**
device: `sensor.pollenwatch_analytics_<allergen>_consensus` and
`binary_sensor.pollenwatch_analytics_<allergen>_divergence`.

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

## License

[MIT](LICENSE)
