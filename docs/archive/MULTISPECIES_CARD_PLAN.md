# Multi-species bundled card — design plan

> **Status: SHIPPED in v2.4.0 — preserved for design rationale; implementation
> is the source of truth.** All four stages (1: options-flow + WS endpoint;
> 2: bars; 3: compact; 4: tiles) landed in v2.4.0 (PRs #17/#19/#21/#22) on top
> of the v2.3.0 single-species gauge card. The shipped card is
> `custom_components/pollenwatch/frontend/pollenwatch-card.js` at
> `CARD_VERSION = '0.6.0'`. This document captured the design decisions and
> open questions before the build; the answers now live in code + code
> comments. Kept here so a future reader can trace why the implementation
> looks the way it does — deliberate-oriel-overlap on tiles, integration-
> options-flow as the layout picker (not card YAML), render-branch
> architecture in one custom element, etc.

## Honest reason this exists

The **no-oriel HACS user.** A user installs PollenWatch on its own, has N
pollen allergies, and today is forced to stack N copies of the gauge card —
one per species — to see their full allergy picture. The single-species
gauge does not scale: a 12-gauge stack is both visually absurd and ~3000 px
tall before any breakdown is expanded.

oriel-dashboard *already* solves multi-species (`consensus_tiles`,
`severity_chips`, `raw_grid` in `src/cards/PollenCard.ts`) — but oriel is a
**separate HACS Plugin** that a PollenWatch user may never install. This
mode makes the bundled card a complete standalone multi-species
experience for that user.

### No shared code with oriel — parity is by intent

The two cards share **zero code** and live in different toolchains:

| | PollenWatch bundled | oriel PollenCard |
|---|---|---|
| Language | Vanilla JS, no build step | TypeScript |
| Framework | `HTMLElement` + Shadow DOM | LitElement |
| Delivery | `add_extra_js_url` from integration | esbuild bundle in oriel-core |
| HACS item | Integration (bundled card auto-served) | Plugin (separate install) |

Where the two surfaces overlap (e.g. the v2.3.0 provenance marker strings),
parity is enforced **by intent** — semantically identical user-facing prose
— not by a shared module. The same discipline applies here: any new
overview layout in the bundled card is its own implementation, not a port
of oriel's TS.

## Config schema + how the user picks the layout

### New key

```yaml
type: custom:pollenwatch-card
species: grass        # still required for `layout: gauge`; optional for overview layouts
layout: gauge         # NEW. 'gauge' | 'bars' | 'compact' | 'tiles'
```

- `layout: gauge` is **today's single-species view, unchanged.** Every
  existing `{species: 'x'}` config keeps working without edits. Full
  backward compatibility is non-negotiable — auto-registered card, users
  did not opt into this YAML and many never see it.
- `layout: bars | compact | tiles` are the three overview (multi-species)
  layouts. See **Overview layouts** below.
- In overview mode `species` becomes **optional** — discovery (see
  **Discovery architecture**) provides the list. An explicit
  `species: [...]` array, if given, overrides discovery (curated subset,
  multi-config-entry disambiguation, or pin-the-order use cases).

### Picker model — decided: integration options flow, not card YAML

The layout dropdown is presented in the **integration's options flow** (HA
Settings → Devices & Services → PollenWatch → Configure), alongside the
species picker the user already uses there.

**Rationale.** The auto-card user never opens raw Lovelace YAML — the card
auto-registers via `add_extra_js_url` and just appears on the dashboard.
Sending them to YAML to flip a layout key is exactly the friction this
card was built to spare them. The options flow is the path they already
know and already use to manage species. Also: the card is *already* going
to call the integration (over WS) for the species list (see **Discovery
architecture**) — adding the layout preference to that same payload is
nearly free.

### Resolution order (layered)

When the card resolves which layout to render, it picks the first that
exists:

1. **Explicit per-card YAML `layout:`** — power user, per-card control.
2. **Integration's configured default layout** (from the WS payload) — the
   90% friendly path.
3. **`gauge`** — final fallback, preserves today's behavior when no
   preference is set anywhere (e.g. pre-upgrade card config or endpoint
   unreachable).

This mirrors **exactly** the species override pattern already in the
overview-mode plan (explicit `species: [...]` overrides discovery). Same
concept — explicit YAML wins over integration default wins over hard
fallback — not a new mental model.

### Tradeoff documented honestly

The integration-level default is **global per config entry.** A user who
wants `bars` in one dashboard and `compact` in another must add the
per-card YAML override.

**Accepted.** This card's audience wants one good allergy card; the
"composed across multiple dashboards" use case is oriel's territory. Per-
user simplicity wins; per-card flexibility is preserved via the YAML
override for the minority that needs it.

## Discovery architecture (WS endpoint + fallback)

### Primary — new HA WebSocket API command

A new `websocket_api` command on the integration, registered alongside the
existing platforms, returns per-config-entry data:

```json
{
  "type": "pollenwatch/config",
  "entry_id": "<config_entry_id>"
}
→
{
  "selected_species": ["grass", "birch", "alder", ...],
  "default_layout": "bars"
}
```

- Reads `entry.options[CONF_SELECTED_SPECIES]` (already stored) and a new
  `entry.options[CONF_DEFAULT_LAYOUT]` option written by the layout
  dropdown in the options flow.
- Scoped **per config entry** — clean for multi-entry setups (e.g. two
  PollenWatch entries for two locations); the card chooses an entry or
  the user disambiguates via YAML `species: [...]` / a future
  `entry_id:` config key.
- This is authoritative — **not** a `hass.states` scan. The integration
  knows its own configuration; the card does not need to infer.

This touches `custom_components/` (Python), so it rides the **cleanroom
gate** (`cleanroom.yml` path filter catches it) and needs **unit tests** on
the WS handler. It also creates a **card ↔ integration version contract**:
the card's expectation of the payload shape becomes a compatibility
surface that future schema changes must respect (or migrate cleanly).

### Fallback — JS-side scan

If the WS command is absent (older integration version, version skew with
the card) or errors, the card falls back to:

- **Species list:** scan `hass.states` for entity IDs matching
  `^sensor\.pollenwatch_analytics_(.+)_consensus$` and use the captured
  species keys. Multi-entry caveat: this fallback **merges species across
  all entries** (it cannot distinguish), so the user with two entries
  should set an explicit `species: [...]` list.
- **Default layout:** no fallback available pre-endpoint — use the YAML
  `layout:` if present, else `gauge`. The integration-default tier
  disappears under version skew; this is the price of a graceful
  degradation path.

Graceful degradation across card↔integration version skew is **required,
not optional.** A user can update PollenWatch (and its bundled card)
independently of any HACS dashboard, and may sit on a stale card cached
by the browser for a session.

### Multi-config-entry behavior

- WS endpoint: per-entry, returns clean data for one entry.
- Scan fallback: merges across entries (documented as a limitation;
  explicit `species: [...]` disambiguates).
- Card-side entry selection (which entry's species + layout to render
  when several exist) is **deferred**; an explicit `species: [...]`
  override is the workaround until that design is needed.

## Overview layouts (the three)

All three render the provenance marker by reusing the **existing**
`provenanceMarker()` helper + `PROVENANCE_MESSAGES` constants already in
the card from v2.3.0 (`frontend/pollenwatch-card.js:208-217`). No new
provenance logic. Per-species click on any overview item dispatches
`hass-more-info` (baseline drill-down, same delegation pattern as
today's per-source breakdown's missing-data row).

Theme rule (carried from gauge): `--secondary-text-color` for muted /
provenance elements; severity colours never collide with provenance
colour; the v2.3.0 "gray-never-green for empty readings" honesty rule
applies in every layout for `unknown` / `nodata`.

### `bars` — flagship, build first

One row per species, top-to-bottom:

```
[icon] Grass    ████████████████░░░░  At peak
[icon] Birch    ████░░░░░░░░░░░░░░░░  In season
[icon] Hazel    ░░░░░░░░░░░░░░░░░░░░  None
[icon] Mugwort     [unknown / nodata treatment]
```

- Bar **length encodes severity tier via fixed enum→fill steps** — there
  is no continuous numeric mapping, because the underlying consensus is a
  4-state enum. The bar is "tier as rough fill," **labelled** with the
  level word so the bar is decoration, not the load-bearing channel.
- Defensible fill fractions (open question, exact values TBD by visual
  pass — see **Open questions**): `none → ~0`, `low → ~⅓`, `high → ~full`.
  `mixed` gets its own treatment (split bar / hatched / two-tone — TBD).
- **Doc must say explicitly:** the bar is severity-tier-fill, not a
  measurement. No false precision. This is the honest version of
  "show me how bad it is" — the same character the single-species
  gauge has, scaled to many species.
- Most differentiated from oriel (oriel has no bar layout) — clear
  reason to exist beyond "we duplicated tiles."

### `compact` — build second

Dense dot-grid, multi-column:

```
● Grass   At peak     ○ Hazel   None
● Birch   In season   ● Olive   At peak
● Alder   In season   ○ Ragweed None
```

- Severity dot (filled circle, severity-tinted) + species name + level
  word.
- Multi-column auto-layout (`grid-template-columns: repeat(auto-fill,
  minmax(?, 1fr))`; column width TBD).
- **Maximum density** for users with many configured species.

### `tiles` — build last

Severity-tinted icon + species name + level word, in a tile grid.

```
[ icon ]   [ icon ]   [ icon ]
 Grass      Birch      Hazel
At peak    In season    None
```

- **Knowingly overlaps oriel's `consensus_tiles`.** Included for
  standalone-completeness: the no-oriel HACS user gets the familiar
  tile view without installing oriel.
- **Deliberate overlap — David's call, not drift.** Documented here so
  a future session does not "fix" the redundancy by removing it.
- **Built last** so it is the cheapest layout to drop if `bars` +
  `compact` prove sufficient in real use.

## Shared-with-gauge elements

The overview layouts and the existing gauge share, by reuse rather than
re-implementation:

- **Header** — same species icon loader (with module-scoped `ICON_CACHE`),
  card title, theme-aware `ha-card` chrome.
- **Severity model** — `none / low / high / mixed` plus `unknown / nodata`
  fallbacks, sourced from `sensor.pollenwatch_analytics_<species>_consensus`
  exactly as today.
- **Provenance marker** — `provenanceMarker()` helper + `PROVENANCE_MESSAGES`,
  unchanged from v2.3.0. Each layout picks its visual variant (dot vs
  glyph) but the basis→tooltip mapping has one source of truth.
- **Per-source reading** — same `perSourceRows()` shape if/when a layout
  decides to expose source attribution (deferred; not in the overview
  MVP).
- **Theme tokens** — `--ha-card-background`, `--divider-color`,
  `--primary-text-color`, `--secondary-text-color`, all already in use.
- **Cache-bust** — `add_extra_js_url(..., f"{base}?v={version}")` already
  reloads the card when `manifest.json` version bumps. No change needed.

**Architecturally: a render-branch in the existing card,** not a new
custom element. Rationale:

- One `add_extra_js_url` registration; no second static path.
- One custom element (`pollenwatch-card`); existing user configs
  `{type: 'custom:pollenwatch-card', species: 'x'}` keep working with
  zero churn.
- Card-internal `_render()` dispatches on `_config.layout` to one of
  the four `_render<Layout>()` methods; gauge stays in `_renderGauge()`
  with the current code essentially unchanged.

## Testing / verification reality

Two halves with sharply different test posture:

### Python — must be unit-tested

- **WS handler** (`websocket_api` command returning
  `{selected_species, default_layout}`) — pytest, mocked config entry,
  asserts payload shape + per-entry scoping + error path.
- **Options flow** — the new layout dropdown, including default value
  for upgrading entries that pre-date the option. pytest config-flow
  helper.
- Both run in the existing pytest suite and ride the cleanroom gate
  (`custom_components/pollenwatch/**` triggers it).

### JS — no automated coverage, by existing gap

The card has **no automated test suite** (a `REVIEW_QUEUE` gap noted
before v2.3.0). Each overview layout's visual + interaction correctness
is verified by:

- **Throwaway HTML harness** (the same approach used for the v2.3.0
  provenance marker stage-2 verification), served via `python3 -m
  http.server` on the LAN; not deployed to a live HA install.
- **Eyeball pass** by the maintainer.
- Optional manual install into the maintainer's own throwaway HA dev
  box (NOT the Hermes-driven watch, NOT `pw-cleanroom`).

**Per-layout cost** of "one harness + one eyeball pass" is real and
non-trivial. Building `bars` + `compact` + `tiles` = three harness
cycles. The **build-last** decision for `tiles` (see above) is in part
a hedge against this cost: if the first two suffice, skip the third.

A standing TODO to give the card real automated tests is **out of
scope** for this plan but called out here as an underlying risk:
multi-layout grows the surface that the no-test-suite gap covers.

## Staged build plan

Each stage = its own branch + gated PR (cleanroom check active where
`custom_components/` is touched) + harness eyeball pass where any
card-visual change lands + STOP-before-merge for review. **Manual-merge
releases.** PollenWatch has **no auto-merge** on release-please chore
PRs (unlike oriel, which auto-merges them with green CI) — every
release PR is reviewed and merged by the maintainer.

### Stage 1 — Integration: options-flow layout option + WS endpoint

- Add `CONF_DEFAULT_LAYOUT` option to `const.py` with default `'gauge'`.
- Options flow: new dropdown (Gauge / Bars / Compact / Tiles).
- Migration: existing entries pick up the default `'gauge'` on first
  options-flow open — no entry version bump needed (additive option).
- New `websocket_api` command `pollenwatch/config` returning
  `{selected_species, default_layout}`.
- Python unit tests: options-flow option round-trip; WS handler payload
  shape + per-entry scoping + missing-entry error.
- **No card change in this stage.** Endpoint + option are testable
  standalone; the card on this stage still ships v0.3.0 behavior.
- `feat:` commit → MINOR bump via release-please.

### Stage 2 — Card: `layout: 'bars'` overview, flagship

- New `_renderBars()` method, dispatched from `_render()` when
  `_config.layout === 'bars'`.
- Calls the WS endpoint on `connectedCallback`-equivalent (early `hass`
  setter), caches the result; falls back to `hass.states` scan on
  endpoint absence/error.
- Implements resolution order: YAML `layout` > integration default >
  `gauge`.
- Provenance marker on each bar row.
- Per-species click → `hass-more-info`.
- Harness verification pass (severities, unknown/nodata, mixed split,
  N=1, N=12, light/dark theme, provenance marker on family/estimated).
- `feat:` commit → MINOR bump.

### Stage 3 — Card: `layout: 'compact'`

- New `_renderCompact()` method.
- Same discovery / fallback / resolution-order machinery from Stage 2
  is reused — no new infrastructure work.
- Harness verification pass.
- `feat:` commit → MINOR bump.

### Stage 4 — Card: `layout: 'tiles'`

- New `_renderTiles()` method.
- Cheapest layout to drop — decision to ship after Stage 3 reality
  check.
- Harness verification pass.
- `feat:` commit → MINOR bump.

## Open questions for future sessions

1. **Exact enum→fill fractions for `bars`.** `none / low / high` need
   defensible fill values from a visual pass; `mixed` needs its own
   treatment (split bar? hatched? two-tone? a third colour?). Decide
   at the start of Stage 2.
2. **`mixed` semantics across layouts.** The gauge already has a
   distinct mixed-mark treatment. `bars` needs a deliberate choice;
   `compact` and `tiles` may share whatever `bars` decides or render
   `mixed` as just another tier.
3. **N-large ceiling.** Does the card cap displayed species (top-N
   active, paginate, scroll) or render them all? Deferred to Stage 2 —
   real-world N is "the user's enabled species count," typically
   3-12, occasionally up to 24. May not need a cap.
4. **Options-flow dropdown semantics.** Does the dropdown need an
   explicit *"let each card decide (YAML)"* option, or does it just
   default to `gauge` when never touched (and YAML overrides anyway)?
   The latter is simpler; the former is more discoverable. Decide at
   the start of Stage 1.
5. **Multi-config-entry selection.** Two PollenWatch entries (e.g. two
   locations) — how does the card pick which entry's config to read?
   Today's implicit answer: an explicit `species: [...]` in YAML
   sidesteps the question entirely. A future `entry_id:` config key
   may be needed if real multi-entry users surface. Deferred.

## Anchors for a future session

- Current shipped state — `frontend/pollenwatch-card.js`, `CARD_VERSION
  = 0.3.0`, single-species gauge only.
- Provenance machinery to reuse — `PROVENANCE_MESSAGES` +
  `provenanceMarker()` at `frontend/pollenwatch-card.js:208-217`;
  marker CSS at `:367-399`; marker DOM in `_build()` and update logic
  in `_render()`.
- Species storage — `CONF_SELECTED_SPECIES` (`const.py:81`), written by
  config flow, read by coordinator; **not yet exposed to the card**
  (this plan adds the WS bridge).
- Oriel's parallel surface (read-only reference, do **not** import or
  port code) — `/opt/repos/oriel-dashboard/src/cards/PollenCard.ts`.
- Project memory anchor — `~/.claude/projects/-opt-repos-pollenwatch/
  memory/project_pollenwatch.md` (canonical "where are we").
