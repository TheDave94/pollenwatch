# Handoff: PollenWatch Brand & Design System

## Overview
**PollenWatch** is a Home Assistant integration that aggregates pollen/allergy
forecasts from multiple sources into one **combined severity reading** (a 0–10
index mapped to a four-step scale: Low / Moderate / High / Very High).

This package contains the brand identity and the visual system that should drive
any UI you build for it: the app icon, the color palette, typography, the
severity scale, and the core components (severity gauge, status pills, dashboard
card, sidebar entry). The defining idea: **higher is worse**. Color and motion
use a green→amber→red *warning* ramp — never a "filling up = good / signal
strength" feel.

## About the Design Files
The files in this bundle are **design references created in HTML** — a brand
guide and a vector/PNG icon — showing the intended look, tokens, and component
anatomy. They are **not production code to copy verbatim**.

Your task is to **recreate this design system in the target codebase's existing
environment** using its established patterns and libraries:
- If it's a **Home Assistant frontend / Lovelace card** → Lit/TypeScript web
  components and HA's theme CSS variables.
- If it's a **React/Vue/Svelte app** → that framework's component model + its
  styling solution (CSS modules, Tailwind, styled-components, etc.).
- If **no environment exists yet** → choose the most appropriate stack for the
  project and implement there.

Translate the tokens and component specs below into the codebase's own
primitives. Reuse existing components where they exist; only add new ones where
the design needs them.

## Fidelity
**High-fidelity.** Colors, typography, spacing, the icon geometry, and the
severity ramp are final. Recreate them precisely. The one intentional
soft spot — see *Icon* — is the 60%-opacity flower, which is a deliberate brand
choice, not an approximation.

---

## Design Tokens

### Color
```
/* Core */
--pw-gold:        #E8920C;   /* primary brand / pollen */
--pw-gold-light:  #F6D45E;   /* flower center, dark-mode needle alt */
--pw-slate:       #33414F;   /* needle, gauge hub */
--pw-ink:         #2A3540;   /* primary text */
--pw-paper:       #FBF7F0;   /* warm background */
--pw-cloud:       #FFFFFF;   /* card surface */
--pw-edge:        #ECE4D6;   /* borders / dividers */
--pw-muted:       #7C8794;   /* secondary text */

/* Severity ramp — the warning scale. Order is meaningful: green=safe, red=worst */
--pw-low:         #3DAE5A;   /* Low      (index 0–2.4)  */
--pw-moderate:    #F2A516;   /* Moderate (index 2.5–4.9)*/
--pw-high:        #EC7A1C;   /* High     (index 5.0–7.4)*/
--pw-very-high:   #E0492E;   /* Very High(index 7.5–10) */

/* Petal accents (decorative, icon only) */
--pw-petal-yellow:#F2B705;
--pw-petal-orange:#EC7A1C;
--pw-petal-red:   #E0492E;
--pw-petal-pink:  #D94F87;
--pw-petal-green: #7FB23E;
```

**Rule:** any severity-bearing surface (needle, pill, number, status dot) MUST
use the ramp above and MUST map higher index → warmer color. Do not introduce a
blue/teal "good progress" treatment.

### Typography
Both families are on Google Fonts (free, OFL):
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,600;12..96,700&family=Hanken+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
```
| Role | Family | Weight | Notes |
|---|---|---|---|
| Wordmark / display | Bricolage Grotesque | 700 | letter-spacing −0.02em |
| Headings | Bricolage Grotesque | 600 | letter-spacing −0.015em |
| Body / UI | Hanken Grotesk | 400 / 500 | line-height 1.6 |
| Numeric / status | Hanken Grotesk | 600 | `font-variant-numeric: tabular-nums` |

Type scale used in the guide: display 76 / 40, h2 34, h3 17–19, body 16–18,
caption 11–13.

### Radius, spacing, surfaces
```
--pw-r-pill: 999px;   /* pills, chips */
--pw-r-card: 16–18px; /* cards */
--pw-r-sw:   14px;    /* swatches / small tiles */
Cards: 1px solid var(--pw-edge) on var(--pw-cloud); no heavy shadows.
Section rhythm: 72px vertical padding, 1px --pw-edge dividers.
```

### Wordmark
Two-tone: **"Pollen"** in `--pw-ink`, **"Watch"** in `--pw-gold` (on dark, use
white + `--pw-gold-light`). Set in Bricolage Grotesque 700. Keep it one
typographic unit; don't add a space or change the weights between the two words.

---

## Assets

In `assets/`:
| File | Size | Use |
|---|---|---|
| `icon.png` | 256×256 | Home Assistant brand icon (`icon.png` spec) |
| `icon@2x.png` | 512×512 | Home Assistant `icon@2x.png` spec |
| `icon.svg` | vector | App UI, any scalable use — **prefer this in-app** |

The PNGs are transparent and trimmed to the artwork bounding box per the
[Home Assistant brands](https://github.com/home-assistant/brands) requirements.
For submission, place them at `custom_integrations/pollenwatch/icon.png` and
`icon@2x.png` (or `core_integrations/` if merging into core).

### Icon — inline SVG source
Use this directly in markup (it's background-independent and crisp at any size).
viewBox is `0 0 100 100`. Anatomy: three-segment warning arc (green→amber→red),
a 60%-opacity six-petal multi-color bloom, five spiky pollen grains, and a slate
needle whose pivot sits at the bloom's center and points into the red zone.

```svg
<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <path d="M24.32 41.66 A27 27 0 0 1 37.95 25.84" stroke="#3DAE5A" stroke-width="8" fill="none" stroke-linecap="round"/>
  <path d="M40.1 24.88 A27 27 0 0 1 59.9 24.88" stroke="#F2A516" stroke-width="8" fill="none" stroke-linecap="round"/>
  <path d="M62.05 25.84 A27 27 0 0 1 75.68 41.66" stroke="#E0492E" stroke-width="8" fill="none" stroke-linecap="round"/>
  <g opacity="0.6">
    <g>
      <ellipse cx="50" cy="36" rx="6.44" ry="9.52" transform="rotate(0 50 36)" fill="#F2B705"/>
      <ellipse cx="62.12" cy="43" rx="6.44" ry="9.52" transform="rotate(60 62.12 43)" fill="#EC7A1C"/>
      <ellipse cx="62.12" cy="57" rx="6.44" ry="9.52" transform="rotate(120 62.12 57)" fill="#E0492E"/>
      <ellipse cx="50" cy="64" rx="6.44" ry="9.52" transform="rotate(180 50 64)" fill="#D94F87"/>
      <ellipse cx="37.88" cy="57" rx="6.44" ry="9.52" transform="rotate(240 37.88 57)" fill="#7FB23E"/>
      <ellipse cx="37.88" cy="43" rx="6.44" ry="9.52" transform="rotate(300 37.88 43)" fill="#F2B705"/>
    </g>
    <circle cx="50" cy="50" r="5.6" fill="#F6D45E"/>
  </g>
  <g fill="#E8920C"><path d="M76.34 51.8 L77 49.4 L77.66 51.8 Z"/><path d="M77.91 51.89 L79.96 50.48 L78.92 52.74 Z"/><path d="M79.06 52.97 L81.53 53.2 L79.28 54.27 Z"/><path d="M79.24 54.53 L80.98 56.3 L78.58 55.67 Z"/><path d="M78.37 55.84 L78.57 58.32 L77.13 56.3 Z"/><path d="M76.87 56.3 L75.43 58.32 L75.63 55.84 Z"/><path d="M75.42 55.67 L73.02 56.3 L74.76 54.53 Z"/><path d="M74.72 54.27 L72.47 53.2 L74.94 52.97 Z"/><path d="M75.08 52.74 L74.04 50.48 L76.09 51.89 Z"/><circle cx="77" cy="54" r="2.7"/></g>
  <g fill="#E8920C"><path d="M68.36 69.11 L69 66.9 L69.64 69.11 Z"/><path d="M69.88 69.21 L71.9 68.1 L70.79 70.12 Z"/><path d="M70.89 70.36 L73.1 71 L70.89 71.64 Z"/><path d="M70.79 71.88 L71.9 73.9 L69.88 72.79 Z"/><path d="M69.64 72.89 L69 75.1 L68.36 72.89 Z"/><path d="M68.12 72.79 L66.1 73.9 L67.21 71.88 Z"/><path d="M67.11 71.64 L64.9 71 L67.11 70.36 Z"/><path d="M67.21 70.12 L66.1 68.1 L68.12 69.21 Z"/><circle cx="69" cy="71" r="2.4"/></g>
  <g fill="#E8920C"><path d="M49.32 78.01 L50 75.7 L50.68 78.01 Z"/><path d="M50.93 78.12 L53.04 76.96 L51.88 79.07 Z"/><path d="M51.99 79.32 L54.3 80 L51.99 80.68 Z"/><path d="M51.88 80.93 L53.04 83.04 L50.93 81.88 Z"/><path d="M50.68 81.99 L50 84.3 L49.32 81.99 Z"/><path d="M49.07 81.88 L46.96 83.04 L48.12 80.93 Z"/><path d="M48.01 80.68 L45.7 80 L48.01 79.32 Z"/><path d="M48.12 79.07 L46.96 76.96 L49.07 78.12 Z"/><circle cx="50" cy="80" r="2.5"/></g>
  <g fill="#E8920C"><path d="M30.36 69.11 L31 66.9 L31.64 69.11 Z"/><path d="M31.88 69.21 L33.9 68.1 L32.79 70.12 Z"/><path d="M32.89 70.36 L35.1 71 L32.89 71.64 Z"/><path d="M32.79 71.88 L33.9 73.9 L31.88 72.79 Z"/><path d="M31.64 72.89 L31 75.1 L30.36 72.89 Z"/><path d="M30.12 72.79 L28.1 73.9 L29.21 71.88 Z"/><path d="M29.11 71.64 L26.9 71 L29.11 70.36 Z"/><path d="M29.21 70.12 L28.1 68.1 L30.12 69.21 Z"/><circle cx="31" cy="71" r="2.4"/></g>
  <g fill="#E8920C"><path d="M22.34 51.8 L23 49.4 L23.66 51.8 Z"/><path d="M23.91 51.89 L25.96 50.48 L24.92 52.74 Z"/><path d="M25.06 52.97 L27.53 53.2 L25.28 54.27 Z"/><path d="M25.24 54.53 L26.98 56.3 L24.58 55.67 Z"/><path d="M24.37 55.84 L24.57 58.32 L23.13 56.3 Z"/><path d="M22.87 56.3 L21.43 58.32 L21.63 55.84 Z"/><path d="M21.42 55.67 L19.02 56.3 L20.76 54.53 Z"/><path d="M20.72 54.27 L18.47 53.2 L20.94 52.97 Z"/><path d="M21.08 52.74 L20.04 50.48 L22.09 51.89 Z"/><circle cx="23" cy="54" r="2.7"/></g>
  <path d="M50 50 L67.84 33.94" stroke="#33414F" stroke-width="4.5" stroke-linecap="round"/>
  <circle cx="50" cy="50" r="3" fill="#33414F"/>
</svg>
```

**Icon rules:** keep clearspace ≥ the dial stroke weight on all sides; min size
16px; never recolor the dial ramp, restretch, or rotate. The slate needle is
intentionally low-contrast on dark themes — swap it to `#F6D45E` for a
high-contrast dark lockup if needed, but keep the silhouette identical.

---

## Components

### 1. Severity gauge (the signature element) — SEE `GAUGE_SPEC.md`
**The data model is categorical, not continuous.** The brand guide's 0–10 dial
was superseded — build the gauge from **`GAUGE_SPEC.md`**, which defines the four
real states (`none` / `low` / `high` / `mixed`) plus first-class `unknown` /
`nodata`, full geometry, the state→render mapping, and reference SVGs.
`gauge/gauge-gen.js` is the working generator; `gauge/states/*.svg` are the six
states as standalone files; `gauge/PollenWatch Gauge.html` renders them all.
Key rule: the needle rests at a **segment center**, never an interpolated value,
and is removed for mixed/missing. Missing states are **gray, never green**.

### 2. Status pill
`display:inline-flex; gap:8px; padding:8px 16px 8px 12px; border-radius:999px;`
background = the level's ramp color, text white 600, with a 10px white-ish dot.
Labels: `Low` · `Moderate` · `High` · `Very High`.

### 3. Severity card (level reference)
Card on `--pw-cloud`, 1px `--pw-edge`, radius 16: an 18px colored dot, the level
name (Bricolage 600, 19px), the index range (`--pw-muted`, 13px), and a short
description.

### 4. Dashboard card
Header row = icon (≈44px) + title (Bricolage 600, 18px) + meta (`N sources ·
updated …`, `--pw-muted` 13px). Body = the big gauge, then the numeric reading
in the active color and `COMBINED · <LEVEL>` caption.

### 5. Sidebar / integration entry
Icon at 24px + label (Hanken 500, ~14.5px). Active state: subtle light overlay +
3px inset `--pw-gold` left accent bar. Works on HA's dark sidebar; the icon's
bright dial/pollen carry it.

---

## Interactions & Behavior
- **Needle**: animate to a new angle on data update — `transition: transform
  320ms cubic-bezier(.32,.72,.30,1)` (a calm ease; no bounce). Rotate around the
  hub.
- **Level change**: cross-fade the reading number/caption color over ~200ms. No
  celebratory motion — a rising index is a warning, not an achievement.
- **Sources/loading**: while fetching, show the gauge in a neutral resting state
  (needle far-left or a muted track) rather than implying a value.
- **Hover** (pointer themes): cards lift to a subtle shadow; sidebar row gets the
  light overlay. No color shift on hover.

## State Management
Minimum state for a PollenWatch surface:
- `index: number` (0–10), `level: 'low'|'moderate'|'high'|'very_high'` derived
  from index thresholds (2.5 / 5.0 / 7.5).
- `sources: string[]` and `updatedAt: timestamp` for the meta line.
- Per-allergen breakdown (optional) if you expose tree/grass/weed sub-readings —
  reuse the same ramp + pill per allergen.
- `loading` / `error` states for the fetch.

## Files in this bundle
- `GAUGE_SPEC.md` — **authoritative** categorical gauge spec (states, geometry, behavior)
- `gauge/gauge-gen.js` — reference SVG generator (`PWGauge.pwGauge(state)`)
- `gauge/states/*.svg` — the six gauge states as standalone SVGs
- `gauge/PollenWatch Gauge.html` — renders every state + the in-context cards
- `assets/icon.svg` — vector icon (use in-app)
- `assets/icon.png` (256), `assets/icon@2x.png` (512) — HA brand-spec PNGs
- `assets/repo-banner.png` — README hero, 2000×500
- `assets/social-preview.png` — og:image, 1280×640
- `PollenWatch Brand Guide.html` — the full visual reference (open in a browser)

---

## How to drive an implementation with Claude Code / browser Claude
1. Put this whole folder in (or alongside) your repo and open it with Claude Code.
2. Prompt, e.g.:
   > "Read `design_handoff_pollenwatch_brand/README.md` and the brand guide.
   > Implement a PollenWatch severity card + gauge as a `<Lit/React/…>` component
   > in this codebase, using our existing component and theming patterns. Wire the
   > tokens into our theme. Start with the gauge, then the card, then the sidebar
   > entry."
3. Tell it your stack and any house rules (styling lib, file layout, design-token
   location) so it maps the tokens into your system rather than hard-coding hex.
4. Have it reference `assets/icon.svg` for in-app use and register the PNGs for
   the Home Assistant brands repo.
5. Iterate component-by-component; verify the **higher = worse** ramp survives in
   your theme (especially dark mode).
```
