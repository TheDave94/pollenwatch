# PollenWatch

[![Validate](https://github.com/TheDave94/pollenwatch/actions/workflows/validate.yml/badge.svg)](https://github.com/TheDave94/pollenwatch/actions/workflows/validate.yml)
[![Lint & Test](https://github.com/TheDave94/pollenwatch/actions/workflows/lint.yml/badge.svg)](https://github.com/TheDave94/pollenwatch/actions/workflows/lint.yml)
[![hacs](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)

The multi-source European pollen aggregator for Home Assistant — with derived
analytics (consensus, divergence, recent percentile, personal sensitivity).

> **Status:** v0.1 (milestone 2). The **Open-Meteo (CAMS)** source works
> end-to-end in Home Assistant — configurable in the UI, with per-allergen
> sensors and a daily-peak forecast. The polleninformation.at and DWD sources
> and the cross-source analytics layer are upcoming.

## What makes PollenWatch different

The Home Assistant ecosystem already has ~10 *single-source* pollen
integrations. PollenWatch instead **combines multiple European sources** and
adds an analytics layer on top:

- **Raw per-allergen sensors** from each configured source (grains/m³ or scaled
  index, with a multi-day forecast in attributes).
- **Consensus** — when ≥2 sources cover the same allergen, a single agreed
  level (very_low → very_high).
- **Divergence flag** — surfaces when sources disagree.
- **Recent percentile** — today vs. the recent past (Open-Meteo backfills up to
  ~90 days, so no recorder dependency for day-one baselining).
- **Personal sensitivity** — optional per-allergen multipliers for
  personal-threshold automations.

## Data sources (v1.0 plan)

| Source | Coverage | API key | Status |
| --- | --- | --- | --- |
| Open-Meteo (CAMS) | All of Europe | none | **Implemented (v0.1).** 6 species, hourly, 5-day forecast. |
| polleninformation.at | 14 EU countries | required | Planned. More species (country-dependent). |
| DWD Pollenflug | Germany (27 zones) | none | Planned. |

## Installation

PollenWatch is not yet in the default HACS store. Add it as a custom repository:

1. In Home Assistant, open **HACS → Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/TheDave94/pollenwatch` with category **Integration**.
3. Install **PollenWatch**, then restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration** and search for
   **PollenWatch**.

## Setup

- **Location:** pick the point to monitor on the map (defaults to your Home
  Assistant location). Open-Meteo snaps it to the nearest ~10 km CAMS grid cell.
  A setup probe rejects locations outside CAMS European coverage.
- **Allergens:** choose from alder, birch, grass, mugwort, olive, and ragweed.
- **Options** (after setup): change the selected allergens and the update
  interval (hourly minimum, to be a good citizen on a free public API).
- **Changing location:** the location is fixed once set, to keep history and
  the upcoming recent-percentile baseline coherent. To move it, remove and
  re-add the integration.
- **Multiple instances:** add PollenWatch more than once for several locations
  (home, office, cabin).

## Entities

Each allergen becomes a sensor under a per-source device ("PollenWatch
Open-Meteo"):

- Entity ID: `sensor.pollenwatch_open_meteo_<allergen>` (e.g.
  `sensor.pollenwatch_open_meteo_grass`).
- State: current concentration in grains/m³.
- Attributes: a 4-day daily-peak `forecast`, requested vs. snapped coordinates,
  grid shift, and the source's last-update time.

### Using the pollenprognos-card

[pollenprognos-card](https://github.com/krissen/pollenprognos-card) does not yet
auto-detect PollenWatch. Until a dedicated adapter exists, map our sensors with
the card's manual configuration using the entity prefix
`pollenwatch_open_meteo_`.

## Attribution

PollenWatch's primary data comes from the **Copernicus Atmosphere Monitoring
Service (CAMS)** via **[Open-Meteo.com](https://open-meteo.com/)**:

> Generated using Copernicus Atmosphere Monitoring Service information.
> Pollen data via Open-Meteo.com.

## License

[MIT](LICENSE)
