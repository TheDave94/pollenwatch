# PollenWatch — deferred ideas (post-v1.0)

Anything that is **not** in the settled v1.0 scope lands here, not in the code.
Keep this list as the pressure-release valve so v1.0 actually ships.

## v1.1 candidates
- Google Pollen as an optional source (commercial; add on user demand).
- Source weighting in the consensus algorithm (station > model). v1.0 uses
  equal weighting.
- Gold quality scale: full translation coverage beyond en/de.
- True multi-year seasonal percentile (needs persistent backend storage).

## Community-contribution candidates
- Additional sources: MeteoSwiss, Atmo France, Kleenex, pollen.hu, pollen.lu,
  pollens.fr.

## Explicitly out of scope (do not build)
- SILAM as a standalone source (CAMS via Open-Meteo already includes it as an
  ensemble member).
- Custom Lovelace card (use krissen/pollenprognos-card; keep our entity naming
  compatible so it auto-detects us).
- Symptom logging / hayfever diary.
- Air-quality (PM/AQI) sensors — overlaps with WAQI.

## Open design questions (decide before the relevant build step)
- Single device with all allergens, or one device per source? (Leaning single
  device, multiple entities.)
- Options flow when user changes lat/lon after data exists: wipe / migrate?
- Translation languages beyond en/de?

## Findings from the build (spec deltas to confirm)
- **Out-of-coverage detection:** Open-Meteo returns HTTP 400 with
  `{"error": true, "reason": "No data is available for this location"}` for
  non-European coords — NOT null-filled arrays. And a valid European location
  off-season returns HTTP 200 with all `0.0`. So the config flow must detect
  coverage via the **HTTP 400 / error body**, not via "all species null/zero"
  (which would wrongly reject a valid location set up in winter).
