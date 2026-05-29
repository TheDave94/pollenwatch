# PollenWatch

The multi-source European pollen aggregator for Home Assistant — with derived
analytics (consensus, divergence, recent percentile, personal sensitivity).

> **Status:** early development (pre-v0.1). The data layer (Open-Meteo / CAMS)
> is the first piece being built; Home Assistant integration plumbing follows.

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

## Data sources (v1.0)

| Source | Coverage | API key | Notes |
| --- | --- | --- | --- |
| Open-Meteo (CAMS) | All of Europe | none | Primary. 6 species, hourly, 5-day forecast, up to 92 past days. |
| polleninformation.at | 14 EU countries | required | Optional. More species (country-dependent). |
| DWD Pollenflug | Germany (27 zones) | none | Optional. |

## Attribution

PollenWatch's primary data comes from the **Copernicus Atmosphere Monitoring
Service (CAMS)** via **[Open-Meteo.com](https://open-meteo.com/)**:

> Generated using Copernicus Atmosphere Monitoring Service information.
> Pollen data via Open-Meteo.com.

## License

[MIT](LICENSE)
