// Synthetic dataset for the PollenWatch card screenshot harness.
//
// This is deliberately synthetic (no live source, no location) but shaped to
// exercise every distinctive rendering path of the card:
//   - consensus states: high / low / none / mixed / unknown
//   - provenance basis:  species / family / estimated (drives the threshold note)
//   - source coverage:   1..3 of 3 possible sources (drives the "N/M sources" line
//     and the single-source "unknown/degraded" rendering)
//   - native source values in mixed units (grains/m³ + DWD 0-7 textual bands)
//
// Edit the SPECIES table to add/retune scenarios. Each entry:
//   st  consensus state (none|low|high|mixed|unknown)
//   c   source_count        m  max_possible_sources
//   b   threshold_basis     (species|family|estimated)
//   sl  source_levels       {source: int level 0/1/2}
//   raw per-source raw sensors [value, unit, nativeBandText?]

export const SPECIES = {
  grass:   { st: 'high',    c: 3, m: 3, b: 'species',   sl: { open_meteo: 2, polleninformation: 2, dwd: 2 }, raw: { open_meteo: [82, 'grains/m³'], polleninformation: [78, 'grains/m³'], dwd: [6, '', '7/7 very high'] } },
  birch:   { st: 'mixed',   c: 2, m: 3, b: 'species',   sl: { open_meteo: 0, polleninformation: 2 },        raw: { open_meteo: [11, 'grains/m³'], polleninformation: [176, 'grains/m³'] } },
  alder:   { st: 'low',     c: 2, m: 3, b: 'species',   sl: { open_meteo: 1, dwd: 1 },                       raw: { open_meteo: [46, 'grains/m³'], dwd: [3, '', '3/7 moderate'] } },
  ragweed: { st: 'high',    c: 1, m: 3, b: 'species',   sl: { open_meteo: 2 },                               raw: { open_meteo: [28, 'grains/m³'] } },
  mugwort: { st: 'low',     c: 2, m: 3, b: 'family',    sl: { open_meteo: 1, polleninformation: 1 },         raw: { open_meteo: [14, 'grains/m³'], polleninformation: [9, 'grains/m³'] } },
  olive:   { st: 'high',    c: 2, m: 3, b: 'estimated', sl: { open_meteo: 2, polleninformation: 2 },         raw: { open_meteo: [212, 'grains/m³'], polleninformation: [188, 'grains/m³'] } },
  ash:     { st: 'none',    c: 2, m: 3, b: 'family',    sl: { open_meteo: 0, dwd: 0 },                       raw: { open_meteo: [1, 'grains/m³'], dwd: [0, '', '0/7 none'] } },
  oak:     { st: 'low',     c: 1, m: 3, b: 'estimated', sl: { open_meteo: 1 },                               raw: { open_meteo: [38, 'grains/m³'] } },
  hazel:   { st: 'unknown', c: 1, m: 3, b: 'species',   sl: { open_meteo: 0 },                               raw: { open_meteo: ['unknown', 'grains/m³'] } },
};

// Build the hass.states map the card reads. Timestamp is passed in (the harness
// can't call Date.now() deterministically), defaulting to a fixed instant.
export function buildStates(now = '2026-06-19T17:00:00+00:00') {
  const s = {};
  for (const [sp, d] of Object.entries(SPECIES)) {
    s[`sensor.pollenwatch_analytics_${sp}_consensus`] = {
      entity_id: `sensor.pollenwatch_analytics_${sp}_consensus`,
      state: d.st, last_changed: now, last_updated: now,
      attributes: {
        source_levels: d.sl, source_count: d.c, max_possible_sources: d.m,
        threshold_basis: d.b, level_label: d.st, friendly_name: `${sp} consensus`,
      },
    };
    for (const [src, [val, unit, native]] of Object.entries(d.raw)) {
      s[`sensor.pollenwatch_${src}_${sp}`] = {
        entity_id: `sensor.pollenwatch_${src}_${sp}`,
        state: String(val), last_changed: now, last_updated: now,
        attributes: { unit_of_measurement: unit || '', ...(native ? { native_value: native } : {}), friendly_name: `${src} ${sp}` },
      };
    }
  }
  return s;
}
