# PollenWatch — Severity Gauge Spec (categorical)

The signature dashboard component. This spec supersedes the brand guide's
continuous 0–10 assumption. Build it from this document; `gauge/gauge-gen.js`
is the reference implementation (vanilla, returns SVG strings) and
`gauge/PollenWatch Gauge.html` renders every state.

---

## Data model

The combined "consensus" reading is **categorical**, not a number:

| State | Meaning | Color | Needle |
|---|---|---|---|
| `none` | level 0 — below onset / no pollen | green `#3DAE5A` | points to green segment center |
| `low` | level 1 — in season | amber `#F2A516` | points to amber segment center |
| `high` | level 2 — at / above peak | red `#E0492E` | points to red segment center |
| `mixed` | sources disagree by > 1 level | — (neutral) | **hidden** — no single value |
| `unknown` | entity exists, not enough history yet | gray `#AEB7C0` | hidden |
| `nodata` | source absent / disconnected | gray `#E6E9ED` | hidden |

**Core honesty rules**
1. The needle only ever rests at a **segment center** — never an interpolated
   "value." There is no continuous position.
2. For `mixed`, `unknown`, `nodata` the needle is **removed entirely**.
3. `unknown` / `nodata` are **gray, never green**. An empty reading must never
   read as a safe "low/none."
4. "Higher is worse." No celebratory motion, ever.

### State resolution (suggested)
```
if (no entity present)             -> 'nodata'
else if (value == null/unknown ||
         not enough history)       -> 'unknown'
else if (sources span > 1 level)   -> 'mixed'
else                               -> ['none','low','high'][consensusLevel]
```

---

## Geometry (SVG viewBox `0 0 120 92`)

```
center (CX, CY)        = (60, 60)
arc radius R           = 44
base stroke width W    = 11      (active segment draws at W + 3 = 14)
arc half-span H        = 78°     (≈156° total sweep, opening downward)

3 segments (with 2° gaps), measured in degrees where 0 = straight up,
negative = left, positive = right:
  green  (none): -78  ..  -28
  amber  (low) : -24  ..   24
  red    (high):  28  ..   78

segment centers (needle targets): [-52, 0, +52]  -> [none, low, high]
needle length          = R - 7 = 37, stroke 3.6, slate #33414F, round cap
hub dot                = r 4.5
bloom (flower)          = 6 petals, petalR 13 (rx 6, ry 8.8), center r 5.5,
                          group opacity 0.6
pollen grain ring       = up to 5 spiky grains around the lower bloom
```

Polar helper (matches the generator):
```js
const pt = (cx, cy, r, deg) => {
  const a = (deg - 90) * Math.PI / 180;            // 0° = up
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
};
```

---

## State → render mapping

| State | Segments | Hub + bloom center | Needle | Pollen grains | Extra |
|---|---|---|---|---|---|
| `none` | all 3 full; green thickened | **green** | → −52° | **0** | — |
| `low` | all 3 full; amber thickened | **amber** | → 0° | **3** | — |
| `high` | all 3 full; red thickened | **red** | → +52° | **5** | — |
| `mixed` | all 3 full, equal width | hollow (white + slate ring) | none | 5 | slate dots at all 3 segment centers on the rim |
| `unknown` | single **dashed** gray track (`1.5 5`) | hollow gray | none | 0 | bloom desaturated gray @ 0.3 |
| `nodata` | single **faint** gray track `#E6E9ED` | hollow gray | none | 0 | bloom gray @ 0.3 + diagonal slash `#8B96A1` |

**Active emphasis (Dir 3 — "status hub"):** the active segment is drawn at
`W+3`, and **both** the needle hub and the bloom's center circle take the active
level's color — so the flower itself signals the state, not just the needle.

**Pollen grains scale with severity** (decision: by level): `none` sheds
nothing (no pollen in the air), `low` = 3 grains, `high` = 5. This reinforces
"more pollen = worse" beyond color alone. The grain ring positions (viewBox
coords): `[(87,64),(78,82),(60,90),(42,82),(33,64)]`; subsets used —
3 → indices [0,2,4], 5 → all.

---

## Caption (text, rendered in the card — not the SVG)

| State | Primary (Bricolage 600) + color | Sub-caption (Hanken, muted) |
|---|---|---|
| `none` | **None** · green | Below onset |
| `low` | **In season** · amber | Pollen active |
| `high` | **At peak** · red | At / above peak |
| `mixed` | **Sources disagree** · slate | `No single level` **or** `Low–High · across N sources` |
| `unknown` | **Unknown** · muted | Not enough history yet |
| `nodata` | **No data** · muted | Source unavailable |

**Decision left open (b):** whether `mixed` names the conflicting span. Build it
behind a config flag, e.g. `show_mixed_span: boolean` (default `false`). When on,
render the sub-caption as `${minLevelLabel}–${maxLevelLabel} · across ${n} sources`.
The big label stays "Sources disagree" either way — never a number.

---

## Behavior

- **Needle move** (level change between none/low/high): rotate around the hub,
  `transform: transform 320ms cubic-bezier(.32,.72,.30,1)` (calm; no bounce/overshoot).
- **Entering mixed / missing:** fade the needle out (~160ms) rather than
  swinging it to a fake position.
- **Color change:** cross-fade the caption color ~200ms.
- **No celebratory motion** on any transition — a rising level is a warning.
- Respect `prefers-reduced-motion`: snap instead of animate.

---

## Reference SVGs

All six states come from `pwGauge(state)` in `gauge/gauge-gen.js`. Two concrete
examples below (the rest are structurally identical).

### `high`
```html
<svg viewBox="0 0 120 92" xmlns="http://www.w3.org/2000/svg">
  <path d="M16.96 50.85 A44 44 0 0 1 39.34 21.15" stroke="#3DAE5A" stroke-width="11" fill="none" stroke-linecap="round"/>
  <path d="M42.1 19.8 A44 44 0 0 1 77.9 19.8" stroke="#F2A516" stroke-width="11" fill="none" stroke-linecap="round"/>
  <path d="M80.66 21.15 A44 44 0 0 1 103.04 50.85" stroke="#E0492E" stroke-width="14" fill="none" stroke-linecap="round"/>
  <g opacity="0.6">
    <g>
      <ellipse cx="60" cy="47" rx="6" ry="8.8" transform="rotate(0 60 47)" fill="#F2B705"/>
      <ellipse cx="71.26" cy="53.5" rx="6" ry="8.8" transform="rotate(60 71.26 53.5)" fill="#EC7A1C"/>
      <ellipse cx="71.26" cy="66.5" rx="6" ry="8.8" transform="rotate(120 71.26 66.5)" fill="#E0492E"/>
      <ellipse cx="60" cy="73" rx="6" ry="8.8" transform="rotate(180 60 73)" fill="#D94F87"/>
      <ellipse cx="48.74" cy="66.5" rx="6" ry="8.8" transform="rotate(240 48.74 66.5)" fill="#7FB23E"/>
      <ellipse cx="48.74" cy="53.5" rx="6" ry="8.8" transform="rotate(300 48.74 53.5)" fill="#F2B705"/>
    </g>
    <circle cx="60" cy="60" r="5.5" fill="#E0492E"/>
  </g>
  <!-- 5 pollen grains (sunbursts) omitted here for brevity — see gauge-gen.js -->
  <path d="M60 60 L89.16 37.22" stroke="#33414F" stroke-width="3.6" stroke-linecap="round"/>
  <circle cx="60" cy="60" r="4.5" fill="#E0492E"/>
</svg>
```

### `mixed`
```html
<svg viewBox="0 0 120 92" xmlns="http://www.w3.org/2000/svg">
  <path d="M16.96 50.85 A44 44 0 0 1 39.34 21.15" stroke="#3DAE5A" stroke-width="11" fill="none" stroke-linecap="round"/>
  <path d="M42.1 19.8 A44 44 0 0 1 77.9 19.8" stroke="#F2A516" stroke-width="11" fill="none" stroke-linecap="round"/>
  <path d="M80.66 21.15 A44 44 0 0 1 103.04 50.85" stroke="#E0492E" stroke-width="11" fill="none" stroke-linecap="round"/>
  <!-- bloom @0.6 + 5 pollen grains (see gauge-gen.js) -->
  <!-- rim marks at all three segment centers: -->
  <circle cx="25.33" cy="32.91" r="3.4" fill="#33414F"/>
  <circle cx="60" cy="16" r="3.4" fill="#33414F"/>
  <circle cx="94.67" cy="32.91" r="3.4" fill="#33414F"/>
  <!-- hollow hub -->
  <circle cx="60" cy="60" r="4.5" fill="#fff" stroke="#33414F" stroke-width="2"/>
</svg>
```

> To emit any state verbatim: open `gauge/PollenWatch Gauge.html` in a browser
> console and call `PWGauge.pwGauge('high')` (or any state name), or port the
> ~120-line `gauge-gen.js` into your component.

---

## Building it as a Lovelace card
- Render the SVG inline (not an `<img>`) so the needle can animate and colors can
  use theme variables. Map the tokens (`GAUGE_SPEC` colors) onto your card's CSS
  custom properties.
- Drive everything off one `state` prop from the integration's combined sensor;
  derive `level`, `grainCount`, `needleAngle`, and caption from the tables above.
- The card chrome (icon + title + meta + caption) is in the brand guide's
  dashboard-card section; reuse it.

---

## Multi-species card — plant-signifier icons

When the card breaks the combined reading into per-allergen rows (or a hero +
strip / mini-gauge strip layout), **the single-species flower icon is replaced
by a plant-signifier icon per species** (catkin, nut, seed-head, leaf, fruit —
whatever distinguishes the plant). Files in `assets/species/` — one SVG per
canonical species key; see the **Species icons** section of `README.md` for the
full key→signifier list and morphology notes.

- The icons are **color-neutral** (`--pw-grain-stroke` / `--pw-grain-fill`);
  inline them so each row inherits the theme and its own severity tint. A row's
  state still follows the same `none/low/high/mixed/unknown/nodata` model and the
  same "higher = worse" ramp defined above — the icon identifies *which* species
  the row is, while the row's gauge/pill carries the level.
- A per-species row that is `mixed` / `unknown` / `nodata` uses the same
  needle-less, gray treatments from this spec; the icon stays neutral and does
  not imply a value.
- `alternaria` is a fungal spore, not a plant, and is drawn as a deliberate
  odd-one-out (muriform spore + beak) so the category honesty is visual, not
  just label-only. It is opt-in (never default-checked) for that reason.

> **Pollen-grain micrographs (deprecated).** Earlier iterations used
> botanical pollen-grain micrographs (a 6-grain set). That approach was
> retired before v2.0: pollen morphology is not distinguishable enough
> across 24 species at icon size (oak/beech/ash/hornbeam/elm are all
> near-identical tricolporate tree pollen). The repo ships only
> `assets/species/`; there is no `assets/grains/`.
