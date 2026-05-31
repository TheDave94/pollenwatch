# PollenWatch clean-room migration test

Repeatable, mostly-unattended end-to-end test that proves a previously-released version of PollenWatch upgrades cleanly to HEAD with **no entity churn, no schema regressions, no silent option resets**.

**Run before tagging a release. ~5 min wall-clock. The verifier output IS the gate.**

```
make cleanroom-pretag
```

Sole prerequisite: a fine-grained GitHub PAT (read-only, public-repo) at `~/.config/pollenwatch-cleanroom/github-pat`. See **First-time setup** below.

## What it does

1. **Bootstrap** (`cleanroom/bootstrap.py`)
   - Mints a fresh run directory under `cleanroom/runs/<timestamp>/`.
   - Pre-seeds a fresh HA config dir: HACS extracted in place; `.storage/core.config_entries` written with a HACS entry holding your pre-seeded GitHub PAT. **No device-flow wall.**
   - Starts a new HA container `pw-cleanroom-<timestamp>` on port 8200 against that config dir.
   - Walks the onboarding API (creates owner, sets core config to AT / Vienna / Graz coords, mints long-lived access token). **No browser.**
   - Polls for HACS ready, adds `TheDave94/pollenwatch`, downloads the pinned baseline version (default `v1.3.0`).
   - Restarts container; creates the two diagnostic config entries from `cleanroom/config/matrix.json`:
     - **Entry A** — Munich, all 6 canonical allergens, multi-source.
     - **Entry B** — Graz, subset `[grass, birch]`, single source.
   - Polls until every pollenwatch entity has its first real state (90s ceiling, WARN+proceed on ceiling).
   - Takes a BEFORE snapshot under `runs/<timestamp>/snapshots/before/`.

2. **Upgrade** (`cleanroom/upgrade.py`)
   - rsyncs HEAD `custom_components/pollenwatch/` over the cleanroom's installed copy (`--delete` mirrors HEAD exactly).
   - Restarts the container; polls until HA up; polls until coordinator-refresh-complete.
   - Takes AFTER snapshot.

3. **Verify** (`cleanroom/verify.py`)
   - Runs the 4 gates (below).
   - Prints the report in full. **Never piped through `tail` / `head`** — verification output is the signal.
   - Exits 0 if all gates pass; exits with the failed gate's number otherwise.

## Gates

| Gate | Asserts |
|---|---|
| **A. Schema migrated** | Entry `version` / `minor_version` correctly bumped; legacy `data.allergens` / `options.allergens` keys absent post-upgrade; `options.selected_species` present; `options.sources` present. (HEAD→HEAD smoke: version unchanged, no `allergens` key in either snapshot — passes trivially.) |
| **B. Entity preservation** | **`(entity_id, unique_id)` PAIRS** before == after for every `platform=="pollenwatch"` entity. **Pair equality is load-bearing** — a changed unique_id with entity_id surviving by luck is exactly the failure mode the canonical-key work guards against. Asserting both halves catches it. |
| **C. Integration healthy** | No `ERROR.*pollenwatch` / `Traceback.*pollenwatch` lines in container logs since the upgrade timestamp (after allowlist). Every pre-existing entity has a state object (`state.state == "unavailable"` is OK — sources may have no current data; missing state object is not). |
| **D. Subset preserved** | Entry B's selected species is **exactly** `["grass", "birch"]` post-upgrade. No additions, no replacements with the default-6, no canonical-name renames. The diagnostic that distinguishes "migration preserved selection" from "reset to default-6." |

## The HACS pin — DELIBERATE, not tracked

`cleanroom/assets/hacs-2.0.5.zip` is **vendored on purpose**. The cleanroom test is about **our** migration story — that pollenwatch users on our last release can upgrade to HEAD. It is **not** a HACS-version compatibility test.

- **Do NOT routinely refresh the HACS zip** to track upstream HACS releases. That's noise that adds churn to the test without adding signal.
- **Refresh ONLY if** a HACS upstream change has materially broken bootstrap (a renamed WS command, a new storage-key requirement, a new onboarding step we have to walk). The trigger is a broken bootstrap, not a calendar date.
- The pin is recorded in `assets/hacs.lock.json` (version + sha256). Replacing the zip without updating the lock fails `lint.py`.
- The HACS install path bootstrap exercises is the user-facing one — that's the only HACS interaction the test cares about.

## The log allowlist — CAGED on purpose

`cleanroom/config/log_allowlist.json` is the one knob in this system that could quietly defeat Gate C. **It is caged.**

- The allowlist exists for **source-side network noise ONLY** — a pollen API returning a 5xx, a transient connection error to Open-Meteo / DWD / EPIN / Google / polleninformation.at.
- **NEVER allowlist anything matching** (case-insensitive): `migration`, `migrate`, `entity_id`, `registry`, `config_entry`, `selected_species`. These are the words that describe what the gate is built to catch. **Silencing them defeats the test.**
- `lint.py` enforces this rule. It runs before bootstrap and aborts with the exact pattern that violated the rule.
- Every allowlist entry requires a `reason` (free-form, what source / what error class) and an `added` ISO date. Lint enforces non-empty.
- A migration-related ERROR is **never** muted. If a real error trips Gate C, **investigate or fix the flake at the source** — don't paper over it in the allowlist.

The allowlist starts empty. It earns entries only with reason + date + a clean pass through lint.

## Settle steps — poll, don't sleep

Wherever the original manual run had `time.sleep(60)` or similar, this system **polls for a specific condition** instead and uses the fixed time only as a **timeout ceiling** with WARN+proceed on hit:

| Settle point | Poll condition | Ceiling |
|---|---|---|
| HA up after `docker start` / `docker restart` | `GET /api/` returns 200 (or 401 before onboarding — both mean HTTP serving) | 90s |
| HACS ready post-boot | WS `hacs/repositories/list` returns `{success: true}` with non-empty result | 90s |
| HACS finished downloading repo | WS `hacs/repositories/list` shows the repo with `downloaded == true` and `installed_version == <pinned>` | 60s |
| Pollenwatch loaded post-restart | REST `/api/config` shows `pollenwatch` in `components` | 60s |
| Coordinator first refresh complete | All pollenwatch entities have `state != null` (any value, including `unavailable`) | 90s — WARN on ceiling |

Ceiling-hit on the last one is not a failure; the test proceeds and the verifier will catch any real downstream issue.

## First-time setup

1. **Generate the GitHub PAT** (one-time per 90 days):
   - GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token.
   - Token name: `pollenwatch-cleanroom`.
   - Expiration: 90 days (rotate on expiry).
   - Resource owner: your account.
   - Repository access: **Public repositories (read-only)** — no other scope needed.
   - Permissions: leave at default (no specific permissions required for public-repo reads).
   - Generate, copy the token.

2. **Store the PAT** (one-time, never commit, never echo):
   ```bash
   mkdir -p ~/.config/pollenwatch-cleanroom
   chmod 700 ~/.config/pollenwatch-cleanroom
   # Paste the PAT directly into the file via $EDITOR — NOT `echo $PAT > ...` (bash-history leak).
   $EDITOR ~/.config/pollenwatch-cleanroom/github-pat
   chmod 600 ~/.config/pollenwatch-cleanroom/github-pat
   ```

3. **Install runtime deps** (one-time):
   ```bash
   python3 -m venv ~/.cache/pollenwatch-cleanroom/venv
   ~/.cache/pollenwatch-cleanroom/venv/bin/pip install -r requirements-cleanroom.txt
   ```

4. **Confirm docker + port 8200 free**:
   ```bash
   docker --version
   ss -tln | grep ":8200" || echo "port 8200 free"
   ```

## Running

Full cycle (default baseline `v1.3.0`):
```bash
make cleanroom-pretag
```

Override baseline for the next release:
```bash
make cleanroom-pretag BASELINE=v1.4.0
```

Step-by-step (debugging):
```bash
python3 cleanroom/bootstrap.py                    # creates runs/<ts>/, prints the run dir
python3 cleanroom/upgrade.py cleanroom/runs/<ts>/
python3 cleanroom/verify.py cleanroom/runs/<ts>/
```

Cleanup after a run:
```bash
python3 cleanroom/cleanup.py cleanroom/runs/<ts>/   # stops container, leaves snapshots/report
# Or trash everything:
rm -rf cleanroom/runs/
docker ps -a --filter "name=pw-cleanroom-" --format '{{.Names}}' | grep -v '^pw-cleanroom$' | xargs -r docker rm -f
```

(The `grep -v '^pw-cleanroom$'` guard prevents touching the maintainer's pre-existing `pw-cleanroom` container.)

## Baseline ↔ flow-version map

The HA config-entry version that the baseline pollenwatch installs at, and the field name that version's config-flow expects. Used by bootstrap to submit the right field name when creating entries:

| Pollenwatch tag | Flow `VERSION` | Species field |
|---|---|---|
| `v1.3.0` | 2 | `allergens` (legacy) |
| `v2.0.0` | 3 | `selected_species` |

Maintained in `cleanroom/config/pinned_release.json`. Add new versions there as releases happen; bootstrap errors loudly on unknown baseline.

## What this test does NOT do

- It is **not** a feature test — entity correctness is not asserted, only entity preservation.
- It is **not** a source-correctness test — if Open-Meteo returns wrong numbers, this passes.
- It is **not** a UI test — the bundled Lovelace card is not exercised.
- It is **not** a HACS test — HACS is the install vehicle, not the SUT.
- It is **not** run on every PR — see Phase 2.

## Phase 2 — CI (deferred)

`.github/workflows/cleanroom.yml` is intentionally **out of scope** for Phase 1. The local `make cleanroom-pretag` proves the harness. CI inherits its assertions once local proves itself on a real release migration. Phase 2 plumbing will be a separate PR.

## Operational safety — what this system does NOT touch

The new system is **physically separated** from the maintainer-operated runtimes by three layers:

| Layer | Existing (don't touch) | This system |
|---|---|---|
| Container name | `pw-cleanroom`, `throwaway-pollenwatch` | `pw-cleanroom-<timestamp>` |
| Host port | 8125, 8124 | **8200** |
| Bind-mount | `/home/thedave/cleanroom-pollenwatch/config/` | `cleanroom/runs/<timestamp>/config/` |

The Hermes-driven throwaway watch (separate runtime, separate orchestration) is also never touched. See repo `CLAUDE.md` "DO NOT — protected runtimes."

## File layout

```
cleanroom/
├── README.md                    (this file)
├── bootstrap.py                 (idempotent: seed → boot → onboarding → HACS install → 2 entries → BEFORE snapshot)
├── upgrade.py                   (rsync HEAD → restart → settle → AFTER snapshot)
├── verify.py                    (4 gates → structured report → exit code)
├── lint.py                      (allowlist sanity; runs first in bootstrap)
├── cleanup.py                   (stop run's container; keep snapshots)
├── assets/
│   ├── hacs-2.0.5.zip           (the deliberate pin)
│   └── hacs.lock.json           (version + sha256)
├── config/
│   ├── pinned_release.json      (baseline tag + flow-version map)
│   ├── matrix.json              (the 2 entries; subset entry is non-optional)
│   └── log_allowlist.json       (caged; lint enforces honesty)
├── lib/
│   ├── __init__.py
│   ├── ha_api.py                (REST helpers — list entries, core config, components)
│   ├── ha_ws.py                 (WS client; max_size=20MiB pinned)
│   ├── ha_flow.py               (config_flow + options_flow over REST)
│   ├── hacs.py                  (HACS WS commands — institutional knowledge: add / download / list / max_size)
│   ├── onboarding.py            (first-user via /api/onboarding/*; kills the manual UI step)
│   └── snapshot.py              (config_entries + entity_registry + device_registry + states + logs)
└── runs/                        (gitignored — per-run output dirs)
    └── <timestamp>/
        ├── config/              (bind-mount target; gets the pre-seed)
        ├── snapshots/{before,after}/
        ├── logs/
        ├── access-token.txt     (mode 0600; long-lived HA token for this run)
        └── report.txt           (verifier output, verbatim)
```
