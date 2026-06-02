# CLAUDE.md — PollenWatch

HACS custom integration aggregating multiple EU pollen sources (CAMS / Open-Meteo, DWD, EPIN, others) with cross-source analytics (consensus, divergence flags, recent percentile, personal sensitivity) layered on top. Maintainer runs it live on his Home Assistant in Graz; distributed publicly as a HACS custom repository. MIT-licensed.

See `README.md` for the full feature surface. **Current phase state lives in `~/.claude/projects/-opt-repos-pollenwatch/memory/project_pollenwatch.md`** — that anchor is updated each session and is the canonical "where are we" source. Read it first.

## DO NOT — protected runtimes

This repo has two parallel live environments that DO NOT belong to any interactive session here:

1. **The throwaway HA (`throwaway-pollenwatch` :8124).** A long-lived dev HA the maintainer drives by hand (HACS upgrades, manual cleanup). Hermes **only reads from** it: `~/.hermes/scripts/pollenwatch_consensus_snapshot.py` runs every 6h (`13 */6 * * *`), does a read-only `GET /api/states` with the LL token at `/home/thedave/throwaway-pollenwatch/phase1_token.txt`, and appends consensus + divergence snapshots to `~/.hermes/state/pollenwatch-watch/snapshots.csv`. Hermes does **NOT** deploy, restart, or mutate this box. Even so, **do not touch it from this session unless the maintainer asks** — no deploys, no entity-registry surgery, no docker stops/restarts, no `ha.py` writes against it. The maintainer drives all changes there by hand; CC's role is to not race the human operator.
2. **The `pw-cleanroom` container** at `/home/thedave/cleanroom-pollenwatch/` (port 8125, host bind-mount `…/config` → `/config`). Used for pristine release-gate upgrade tests. **Do not touch its container, its config dir, or the `/tmp/cleanroom_*.py` helpers / `/tmp/cr-venv` from this session.** See `~/.claude/projects/-opt-repos-pollenwatch/memory/reference_cleanroom.md` for what it is, why it exists, and when the maintainer uses it.

Both environments are operated deliberately by the maintainer (Hermes' role on the throwaway is read-only snapshot-collection only — see above). Interactive sessions in this repo work on the code in `/opt/repos/pollenwatch` only — they do not actuate either runtime.

## Session boundaries — one phase per session

PollenWatch work is structured into phases (e.g. v2.0 phases A–G; v2.4 stages 1–4 for the multi-species card). Phases are natural session boundaries:

- **One phase = one session.** When a phase wraps (sign-off recorded in `project_pollenwatch.md`), summarise the deliverables into that memory anchor and start a fresh CC session for the next phase.
- The single biggest pollenwatch session to date was 19.4 MB / max input context ≈ 999k tokens / 13 `/compact`s — because phases A–G ran in one session. Don't repeat that.
- For sub-phase work (e.g. a single gate within a phase, or one stage of a multi-stage arc), the existing session is fine; for the next phase, split.

User-level `~/.claude/CLAUDE.md` has the general output discipline (Bash caps, ranged Reads, test-output verbatim) — it applies here.

## Architecture (orient — full detail in code + memory anchor)

- `custom_components/pollenwatch/` — HA integration code (Python).
  - `coordinator.py` — per-source `DataUpdateCoordinator`s.
  - `sensor.py` — raw + recent_percentile + personal_score + consensus sensor entities (one per species per source for the per-source ones; one per species for consensus).
  - `binary_sensor.py` — divergence binary_sensor entities (one per multi-source species; flags when sources disagree by >1 level).
  - `config_flow.py` — onboarding + options flow (region-aware species preselection).
  - `analytics.py` — cross-source consensus, divergence flagging, recent percentile, level/level_label bucketing.
  - `region_defaults.py` — per-PI-country species preselection table for the v2.0+ onboarding (Central EU vs Mediterranean vs Nordic vs UK).
  - `sources/species_registry.py` — canonical species keys (24 EU species, expanded from 6; 5-value threshold_status enum per v2.2 / issue #3).
  - `frontend/` — Lovelace card + 24 species duotone icons.
- `brand/assets/species/` — source SVGs for the icons (sync target: `frontend/icons/`).
- `tests/` — pytest unit + integration tests.

## Deploy / verify

`ha.py` (repo-tracked HA REST helper) plus the HACS-WS deploy path are the canonical deploy mechanism — see `reference_ha_deploy.md` in project memory. `custom_components/` in the running install is gitignored (the live install lives outside the repo). **All deploys go to the throwaway dev box (`throwaway-pollenwatch` :8124) only**, never to `pw-cleanroom`. Hermes' read-only snapshot pass against the throwaway is fine; deploys are still the maintainer's hand.

## Credentials

`HA_URL` + `HA_TOKEN` for HA REST access live in `.env.local` (gitignored). Same long-lived token also held by `~/.hermes/.env` and `/opt/repos/homeassistant-config/.env.local`. Rotation runbook at `/opt/autocoder/ROTATION_RUNBOOK.md`. Never `cat` / `echo` / `head` the token — verify by length or by API round-trip.

## DO NOT — code-side

- Don't deploy code without throwaway verification.
- Don't change canonical species keys without registry + migration consideration (entity_id rename is breaking for users' dashboards/automations).
- Don't add features outside the source / analytics / card / onboarding axis without explicit scope sign-off — see `feedback_scope_discipline.md` in project memory.
- Don't push back on EU species coverage being broad — that's a locked, eyes-open decision recorded in `project_pollenwatch.md`.
