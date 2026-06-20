# PollenWatch card screenshot harness

Reusable, committed tooling that regenerates the card screenshots embedded in the
project README. Re-run it after any visible change to `pollenwatch-card.js`.

## One command

```bash
cd tools/screenshots
npm install            # first time only — pulls Playwright (chromium is cached)
npx playwright install chromium   # first time only
npm run screenshots    # node shoot.mjs
```

Output → `docs/images/{bars,compact,tiles,gauge,...}-*.png` (the paths the README embeds).

## How it works

- **`fixtures.mjs` — synthetic dataset/generator.** A `SPECIES` table + `buildStates()`
  that produces a `hass.states` map exercising every distinctive render path: all
  consensus states (high/low/none/mixed/unknown), all three provenance tiers
  (species/family/estimated), 1–3 of 3 source coverage (incl. the degraded
  single-source "unknown" case), and mixed native units (grains/m³ + DWD 0–7 bands).
  Add or retune a scenario by editing the table.
- **`harness.html` — render host.** Stubs HA's `<ha-card>` wrapper and loads the real card bundle.
- **`shoot.mjs` — renderer.** Starts a tiny static server (serves `harness.html` and
  maps `/pollenwatch_card_static/*` to `custom_components/pollenwatch/frontend/*`,
  exactly as HA mounts it), then renders all four layouts + the provenance/divergence/
  degraded states and writes the PNGs. `node shoot.mjs gauge-mixed-light` renders one shot.

## Honesty & privacy properties (keep these)

- **Synthetic, location-free data.** No live source, no coordinates, no place names —
  just a synthetic dataset shaped to show real card behaviour. Keep it that way.
- **Faithful behaviour.** The fixture drives the card's real consensus/provenance/
  degraded rendering; it does not bypass or fake any of the card's logic.
