# Tier 1 prerelease gate

The Tier 1 gate is a small e2e suite that runs against a real HA whenever a
GitHub **prerelease** is published. It is the first line of defence between
"release-please cut a prerelease tag" and "we promote it to a full release".

It deliberately does NOT replace the cleanroom-pretag harness (which gates
PRs by exercising a v1.3.0 → HEAD upgrade in a disposable docker container).
Cleanroom catches *migration regressions before merge*; the prerelease gate
catches *discovery-surface regressions after tagging, against the deployed
artifact*.

## What it asserts

Pointed at the throwaway HA (`http://127.0.0.1:8124` by default), it asserts:

1. `config_entries/get {domain: "pollenwatch"}` returns ≥1 entry with
   `state == "loaded"`.
2. `pollenwatch/config {entry_id}` returns
   `{success: true, result: {selected_species: [str, ...non-empty], default_layout: <one of gauge|bars|compact|tiles>}}`.
3. An options-flow round-trip on `default_layout` actually persists: set to
   `bars`, read back `bars` via the WS endpoint, then revert to the original
   in a `finally` block. The throwaway is left in the state it started in.

Assertions deliberately validate **shape + sane values**, not exact species
lists or layout values — that would make the gate brittle to reconfiguring
the throwaway.

## Blocking vs inconclusive

The gate distinguishes two failure modes:

| Failure                              | pytest action         | Job exit | Meaning                |
| ------------------------------------ | --------------------- | -------- | ---------------------- |
| HA unreachable, timeout, auth fail   | `pytest.skip()`       | 0        | inconclusive — infra   |
| Endpoint returned wrong shape / bad round-trip | `assert` fails | non-zero | real red — block release |

Read a red as: "the prerelease build's discovery surface is broken; do NOT
promote the tag". Read a skip as: "the throwaway was down or the runner
couldn't reach it; re-run when infra is back, or investigate the host".

## David's setup (one-time)

### 1. Register the self-hosted runner

The runner must live on the VM that already hosts the throwaway (port 8124),
so the test can reach `http://127.0.0.1:8124`.

```
# On the VM, in a working directory you control:
gh api -X POST repos/TheDave94/pollenwatch/actions/runners/registration-token --jq .token
# (copy the token)

mkdir actions-runner && cd actions-runner
curl -o actions-runner.tar.gz -L \
    https://github.com/actions/runner/releases/latest/download/actions-runner-linux-x64.tar.gz
tar xzf actions-runner.tar.gz

./config.sh \
    --url https://github.com/TheDave94/pollenwatch \
    --token <token-from-step-1> \
    --labels pollenwatch-throwaway \
    --name "$(hostname)-pollenwatch-throwaway" \
    --unattended

# Run as a systemd service so it survives reboots:
sudo ./svc.sh install
sudo ./svc.sh start
```

The `--labels pollenwatch-throwaway` flag is the **load-bearing piece** — it's
what `runs-on: [self-hosted, pollenwatch-throwaway]` in
`.github/workflows/prerelease-gate.yml` matches against. The `--name` is free
(use anything that identifies the host). If you re-register without `--labels`
the runner comes up with only the auto-assigned `self-hosted, Linux, X64` and
the gate sits in queue forever.

Verify labels EITHER via the GitHub API (works headless, scriptable):

```
gh api /repos/TheDave94/pollenwatch/actions/runners \
    --jq '.runners[] | {name, status, labels: [.labels[].name]}'
# Expect: {"name":"...","status":"online","labels":["self-hosted","Linux","X64","pollenwatch-throwaway"]}
```

…OR in the UI: **Settings → Actions → Runners** — the new runner should show
as **Idle** with all four labels. Labels are server-side in runner v2.x; they
are NOT in the local `.runner` file.

### 2. Set the token secret (recommended)

```
gh secret set THROWAWAY_HA_TOKEN \
    --body "$(cat /home/thedave/throwaway-pollenwatch/phase1_token.txt)"
```

The test prefers `HA_TOKEN` from the environment (sourced from this secret).
If the secret is unset, it falls back to reading
`/home/thedave/throwaway-pollenwatch/phase1_token.txt` directly on the
runner host — so the gate still works without the secret as long as the
file is readable by the runner's user. The secret path is preferred because
it survives token rotation with a single `gh secret set` (the file path
requires SSH'ing to the VM).

### 3. Trigger a test run

The gate fires automatically on `release: prereleased`. To smoke-test the
setup without cutting a tag:

```
gh workflow run prerelease-gate.yml -f reason="initial runner verification"
gh run watch
```

A green run on a healthy throwaway means the runner is wired up. A skip
result with "inconclusive: HA unreachable" means the runner can't reach
`:8124` — investigate the throwaway, not the gate.

## When the gate fires

- **Real**: `release-please` (or you) publishes a GitHub prerelease tag.
- **Manual**: `workflow_dispatch` from the Actions UI or `gh workflow run`.

It does NOT fire on PRs, branch pushes, or full releases (those are covered
by `cleanroom.yml` and `lint.yml` respectively).

## Reading results

```
gh run list --workflow=prerelease-gate.yml --limit 5
gh run view <run-id> --log
```

In the log:
- `PASSED` for all three tests → discovery surface clean, prerelease promotable.
- `SKIPPED` with `inconclusive: ...` → infra; re-run after fixing the host.
- `FAILED` with an `AssertionError` → real regression; investigate the
  prerelease build BEFORE promoting.

## Future work (not in scope here)

Tier 2 (browser-level Lovelace card render via Playwright) is the next layer
up. It would catch card-rendering regressions that Tier 1's WS-only suite
can't see. Out of scope for this gate; tracked separately.
