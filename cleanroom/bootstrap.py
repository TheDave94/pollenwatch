#!/usr/bin/env python3
"""Clean-room bootstrap: fresh container → onboarding → HACS install →
2 diagnostic entries → BEFORE snapshot. Idempotent at the per-run-dir level.

Reads:
  cleanroom/config/pinned_release.json   (baseline tag, flow VERSION map)
  cleanroom/config/matrix.json            (the 2 entries; subset enforced)
  cleanroom/assets/hacs-<v>.zip           (vendored HACS)
  cleanroom/assets/hacs.lock.json         (sha pin)
  ~/.config/pollenwatch-cleanroom/github-pat

Writes:
  cleanroom/runs/<timestamp>/config/      (HA bind-mount)
  cleanroom/runs/<timestamp>/access-token.txt
  cleanroom/runs/<timestamp>/snapshots/before/
  cleanroom/runs/<timestamp>/logs/
  cleanroom/runs/<timestamp>/meta.json

Container name pattern: pw-cleanroom-<timestamp>. Port: 8200.
NEVER touches the maintainer's pw-cleanroom container (different name + port).
"""
from __future__ import annotations

import argparse
import json
import secrets
import socket
import subprocess
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

# Allow `from lib.X import Y` when invoked as `python3 cleanroom/bootstrap.py`
sys.path.insert(0, str(Path(__file__).parent))

import asyncio  # noqa: E402

from lib import hacs as hacs_ws  # noqa: E402
from lib.ha_api import HAClient  # noqa: E402
from lib.ha_flow import create_pollenwatch_entry, submit_pollenwatch_options  # noqa: E402
from lib.ha_ws import HAWebSocket  # noqa: E402
from lib.onboarding import walk_onboarding  # noqa: E402
from lib.snapshot import take_snapshot  # noqa: E402

ROOT = Path(__file__).parent
REPO_ROOT = ROOT.parent
PAT_PATH = Path.home() / ".config" / "pollenwatch-cleanroom" / "github-pat"
HA_IMAGE = "ghcr.io/home-assistant/home-assistant:stable"
PORT = 8200
PROTECTED_CONTAINER_NAMES = {"pw-cleanroom", "throwaway-pollenwatch"}


# ---------- helpers ----------

def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def die(msg: str, code: int = 1) -> None:
    print(f"FATAL: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def run(cmd: list[str], *, check: bool = True, capture: bool = False,
        timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, check=check, capture_output=capture, text=True, timeout=timeout,
    )


def _iso_ts() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _container_name(run_id: str) -> str:
    name = f"pw-cleanroom-{run_id}"
    assert name not in PROTECTED_CONTAINER_NAMES, "refusing to use a protected name"
    assert name.startswith("pw-cleanroom-") and len(name) > len("pw-cleanroom-"), \
        f"container name must have a non-empty suffix: {name}"
    return name


# ---------- preflight ----------

def preflight() -> dict:
    log("preflight:")
    # 1. Lint (HACS pin + allowlist sanity).
    log("  running lint.py (HACS pin + allowlist)")
    lint_rc = subprocess.call([sys.executable, str(ROOT / "lint.py")])
    if lint_rc != 0:
        die("lint failed; refusing to bootstrap")

    # 2. PAT file.
    if not PAT_PATH.exists():
        die(
            f"PAT not found at {PAT_PATH}\n"
            f"  Generate a fine-grained GitHub PAT (public-repo read-only) and store it\n"
            f"  there with `chmod 600`. See cleanroom/README.md §'First-time setup'."
        )
    mode = PAT_PATH.stat().st_mode & 0o777
    if mode & 0o077:
        die(
            f"PAT at {PAT_PATH} has mode {oct(mode)}; must be 0600 "
            f"(no group/other read). Run: chmod 600 {PAT_PATH}"
        )
    pat = PAT_PATH.read_text().strip()
    if not pat or len(pat) < 20:
        die(f"PAT at {PAT_PATH} is empty or implausibly short")
    log(f"  ok   PAT loaded (len={len(pat)})")

    # 3. docker.
    try:
        ver = run(["docker", "--version"], capture=True).stdout.strip()
        log(f"  ok   docker present: {ver}")
    except FileNotFoundError:
        die("docker not found in PATH")

    # 4. Port free.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", PORT)) == 0:
            die(
                f"port {PORT} is already in use. The cleanroom system uses {PORT}; "
                f"the maintainer's existing pw-cleanroom uses 8125. If something else "
                f"is on {PORT}, stop it or pick a different port (edit bootstrap.py)."
            )
    log(f"  ok   port {PORT} free")

    return {"pat": pat}


# ---------- config dir pre-seed ----------

def preseed_config_dir(run_dir: Path, pat: str) -> None:
    config_dir = run_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    # 1. Extract HACS zip into custom_components/hacs/
    lock = json.loads((ROOT / "assets" / "hacs.lock.json").read_text())
    zip_path = ROOT / "assets" / lock["zip_filename"]
    hacs_dir = config_dir / "custom_components" / "hacs"
    hacs_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(hacs_dir)
    log(f"  ok   HACS {lock['hacs_version']} extracted → {hacs_dir.relative_to(run_dir)}")

    # 2. Pre-write .storage/core.config_entries with the HACS entry holding the PAT.
    storage = config_dir / ".storage"
    storage.mkdir(exist_ok=True)
    entry_id = secrets.token_hex(16)
    iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
    hacs_entry = {
        "entry_id": entry_id,
        "version": 1,
        "minor_version": 1,
        "domain": "hacs",
        "title": "",
        "data": {"token": pat},
        "options": {"experimental": True},
        "pref_disable_new_entities": False,
        "pref_disable_polling": False,
        "source": "user",
        "unique_id": None,
        "disabled_by": None,
        "created_at": iso,
        "modified_at": iso,
        "discovery_keys": {},
    }
    core_entries = {
        "version": 1,
        "minor_version": 4,
        "key": "core.config_entries",
        "data": {"entries": [hacs_entry]},
    }
    (storage / "core.config_entries").write_text(json.dumps(core_entries, indent=2))
    log("  ok   .storage/core.config_entries pre-seeded with HACS entry (PAT baked)")

    # 3. configuration.yaml minimal — enables default_config (frontend, http,
    #    auth, etc.) and turns on debug logging for the components we care about.
    (config_dir / "configuration.yaml").write_text(
        "default_config:\n"
        "logger:\n"
        "  default: warning\n"
        "  logs:\n"
        "    custom_components.hacs: info\n"
        "    custom_components.pollenwatch: debug\n"
    )
    log("  ok   configuration.yaml written")


# ---------- container lifecycle ----------

def docker_run(container_name: str, run_dir: Path) -> None:
    config_dir = (run_dir / "config").resolve()
    cmd = [
        "docker", "run", "-d",
        "--name", container_name,
        "-p", f"{PORT}:8123",
        "-v", f"{config_dir}:/config",
        "--restart", "no",
        HA_IMAGE,
    ]
    log(f"  starting container: {' '.join(cmd)}")
    run(cmd, capture=True)


def docker_restart(container_name: str) -> None:
    log(f"  restarting container {container_name}")
    run(["docker", "restart", container_name], capture=True)


# ---------- pollers ----------

def wait_for_ha(client: HAClient, timeout: int = 90) -> None:
    log(f"  polling HA up (timeout {timeout}s)...")
    t0 = time.monotonic()
    if not client.wait_until_up(timeout=timeout):
        die(f"HA did not come up within {timeout}s")
    log(f"  ok   HA up in {time.monotonic() - t0:.1f}s")


def wait_for_component(client: HAClient, domain: str, timeout: int = 60) -> None:
    log(f"  polling for component '{domain}' loaded (timeout {timeout}s)...")
    t0 = time.monotonic()
    if not client.wait_for_component(domain, timeout=timeout):
        die(f"component '{domain}' did not load within {timeout}s")
    log(f"  ok   '{domain}' loaded in {time.monotonic() - t0:.1f}s")


async def _wait_for_hacs_ready(ws: HAWebSocket, timeout: int) -> bool:
    return await hacs_ws.wait_for_hacs_ready(ws, timeout=timeout)


async def _hacs_install(ws: HAWebSocket, full_name: str, version: str) -> None:
    log(f"  HACS: add repository {full_name}")
    resp = await hacs_ws.add_repository(ws, full_name)
    if not resp.get("success"):
        die(f"hacs/repositories/add failed: {resp!r}")
    repo = await hacs_ws.wait_for_repository_registered(ws, full_name, timeout=60)
    if not repo:
        die(f"HACS did not register {full_name} within 60s")
    log(f"  ok   registered: id={repo['id']} available={repo.get('available_version')}")
    log(f"  HACS: download {full_name} version={version}")
    resp = await hacs_ws.download_version(ws, repo["id"], version)
    if not resp.get("success"):
        die(f"hacs/repository/download failed: {resp!r}")
    if not await hacs_ws.wait_for_downloaded(ws, full_name, version, timeout=180):
        die(f"HACS download did not complete within 180s for {full_name}@{version}")
    log(f"  ok   {full_name}@{version} downloaded to /config/custom_components/pollenwatch/")


def wait_for_coordinator_refresh(client: HAClient, timeout: int = 90) -> bool:
    """Poll until every pollenwatch entity has a non-null state object. Returns
    True on success, False on timeout (caller decides whether ceiling-hit is
    fatal — for the v1 cleanroom it is WARN+proceed)."""
    log(
        f"  polling for coordinator first-refresh (every pw entity has a state); "
        f"ceiling {timeout}s..."
    )
    t0 = time.monotonic()
    deadline = t0 + timeout
    last_unready = -1
    while time.monotonic() < deadline:
        all_states = client.all_states()
        pw_states = [
            s for s in all_states
            if s.get("entity_id", "").startswith(
                ("sensor.pollenwatch_", "binary_sensor.pollenwatch_")
            )
        ]
        if not pw_states:
            time.sleep(2)
            continue
        # All states have at least an `state` key; we want != "unknown" (or
        # "unavailable", which means the coordinator ran but the source had no
        # data — that's a legitimate refresh-complete state).
        unready = [s for s in pw_states if s.get("state") in (None, "unknown")]
        if len(unready) != last_unready:
            log(
                f"    {len(pw_states) - len(unready)}/{len(pw_states)} ready "
                f"(waiting on {len(unready)})"
            )
            last_unready = len(unready)
        if not unready:
            log(
                f"  ok   coordinator refresh complete in "
                f"{time.monotonic() - t0:.1f}s ({len(pw_states)} entities)"
            )
            return True
        time.sleep(3)
    log(f"  WARN coordinator first-refresh did not complete within {timeout}s; proceeding")
    return False


# ---------- entry creation ----------

def _assert_matrix_invariants(matrix: dict) -> None:
    entries = matrix.get("entries", [])
    if len(entries) < 2:
        die(
            "matrix.json must define at least TWO entries. The subset entry is "
            "the load-bearing diagnostic; see cleanroom/README.md §Gate D."
        )
    canonical = set(matrix.get("canonical_v1_species", []))
    if not canonical:
        die("matrix.json missing 'canonical_v1_species'")
    if not any(set(e.get("species", [])) < canonical for e in entries):
        die(
            "matrix.json must include AT LEAST ONE entry whose species is a "
            "strict subset of canonical_v1_species. An all-6-only test proves "
            "nothing about migration preserving subset selections. See "
            "cleanroom/README.md §Gate D."
        )


def create_entries(
    client: HAClient, matrix: dict, species_field: str, flow_version: int,
) -> list[dict]:
    log("creating diagnostic entries:")
    created: list[dict] = []
    for e in matrix["entries"]:
        log(f"  entry {e['name']} ({e['location_label']}) species={e['species']}")
        entry_id = create_pollenwatch_entry(
            client,
            latitude=e["latitude"],
            longitude=e["longitude"],
            species=e["species"],
            species_field=species_field,
            flow_version=flow_version,
        )
        if not entry_id:
            die(f"failed to create entry {e['name']}")
        # Apply options-flow (sources etc).
        if e.get("options"):
            log("    applying options-flow")
            if not submit_pollenwatch_options(
                client, entry_id,
                species=e["species"],
                species_field=species_field,
                options=e["options"],
            ):
                log(
                    f"    WARN options-flow did not create_entry for {e['name']}; "
                    f"entry exists but options may be defaults"
                )
        created.append({"name": e["name"], "entry_id": entry_id, "species": e["species"]})
        log(f"  ok   created {e['name']} entry_id={entry_id}")
    return created


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description="Clean-room bootstrap for PollenWatch migration test")
    ap.add_argument("--baseline", default=None,
                    help="Override pinned baseline pollenwatch version tag (e.g. v1.3.0, v2.0.0)")
    ap.add_argument("--run-id", default=None,
                    help="Override run timestamp (default: ISO Zulu)")
    args = ap.parse_args()

    # Load configs early so a bad config fails before any docker noise.
    pinned = json.loads((ROOT / "config" / "pinned_release.json").read_text())
    matrix = json.loads((ROOT / "config" / "matrix.json").read_text())
    _assert_matrix_invariants(matrix)
    baseline = args.baseline or pinned["default_baseline"]
    if baseline not in pinned["versions"]:
        die(
            f"baseline '{baseline}' is not in pinned_release.json 'versions'. "
            f"Add a flow_version / species_field entry for it (see README "
            f"§'Baseline ↔ flow-version map')."
        )
    baseline_spec = pinned["versions"][baseline]
    species_field = baseline_spec["species_field"]
    log(
        f"baseline: {baseline} (flow_version={baseline_spec['flow_version']}, "
        f"species_field={species_field!r})"
    )

    info = preflight()

    run_id = args.run_id or _iso_ts()
    run_dir = ROOT / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    container_name = _container_name(run_id)
    log(
        f"run_id={run_id}  run_dir={run_dir.relative_to(REPO_ROOT)}  "
        f"container={container_name}  port={PORT}"
    )

    # Persist run meta early — upgrade.py + verify.py + cleanup.py read it.
    meta = {
        "run_id": run_id,
        "started_iso": datetime.now(UTC).isoformat(),
        "container_name": container_name,
        "port": PORT,
        "baseline": baseline,
        "baseline_spec": baseline_spec,
        "head_flow_version": pinned["head_flow_version"],
        "matrix": matrix,
        "ha_image": HA_IMAGE,
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2))

    # Pre-seed.
    log("pre-seeding config dir:")
    preseed_config_dir(run_dir, info["pat"])

    # Boot.
    log("starting container:")
    docker_run(container_name, run_dir)
    base_url = f"http://127.0.0.1:{PORT}"
    pre_client = HAClient(base_url, token=None)
    wait_for_ha(pre_client, timeout=120)

    # Onboarding.
    log("onboarding walk:")
    onboarding = walk_onboarding(
        base_url,
        owner_name="Cleanroom",
        owner_username="cleanroom",
        owner_password=secrets.token_urlsafe(24),
        language="en",
        country="AT",
        location_name="Clean Room (Graz)",
        latitude=47.0707,
        longitude=15.4395,
        elevation=353,
        time_zone="Europe/Vienna",
    )
    token_path = run_dir / "access-token.txt"
    token_path.write_text(onboarding.long_lived_token)
    token_path.chmod(0o600)
    log(f"  ok   long-lived token minted, stored at {token_path.relative_to(REPO_ROOT)} (mode 600)")
    client = HAClient(base_url, token=onboarding.long_lived_token)
    ws = HAWebSocket(base_url, onboarding.long_lived_token)

    # Wait for HACS to be ready (the pre-seeded entry will have loaded on boot,
    # but HACS does its initial GitHub-side repo discovery async).
    log("waiting for HACS ready:")
    if not asyncio.run(_wait_for_hacs_ready(ws, timeout=120)):
        die("HACS did not become ready within 120s — check container logs and the pre-seeded token")
    log("  ok   HACS ready")

    # HACS: add + download pollenwatch baseline.
    log(f"installing pollenwatch {baseline} via HACS:")
    asyncio.run(_hacs_install(ws, "TheDave94/pollenwatch", baseline))

    # Restart container so HA loads the newly-downloaded integration. We
    # deliberately do NOT poll for `pollenwatch in components` here —
    # pollenwatch is config_flow-only, so its domain doesn't appear in
    # `components` until the first config_entry exists, which is the very next
    # step. The config_flow handler is registered at boot once the files are
    # on disk; that's what creating an entry actually exercises.
    log("restarting container so HA loads pollenwatch's config_flow handler:")
    docker_restart(container_name)
    wait_for_ha(client, timeout=120)

    # Create the diagnostic entries.
    create_entries(
        client, matrix,
        species_field=species_field,
        flow_version=baseline_spec["flow_version"],
    )
    # Now that entries exist, the component should be loaded — sanity check.
    wait_for_component(client, "pollenwatch", timeout=30)

    # Settle.
    wait_for_coordinator_refresh(client, timeout=90)

    # Snapshot.
    log("taking BEFORE snapshot:")
    before_dir = run_dir / "snapshots" / "before"
    snap_meta = take_snapshot(client, ws, before_dir, container_name, run_id,
                              config_dir=run_dir / "config", since=None)
    log(
        f"  ok   snapshot: {snap_meta['pw_entity_count']} entities, "
        f"{snap_meta['pw_config_entry_count']} entries"
    )

    # Final summary.
    log("bootstrap complete.")
    print(f"\nRUN_DIR: {run_dir}")
    print(f"NEXT:    python3 cleanroom/upgrade.py {run_dir.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
