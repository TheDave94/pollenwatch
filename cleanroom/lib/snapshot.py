"""Snapshot helpers — write a structured JSON dump of HA state at a point in
time. Used for the BEFORE / AFTER snapshots that the verifier diffs.

A snapshot is a directory containing:

  config_entries.json   — all pollenwatch entries (data, options, version, etc.)
  entity_registry.json  — pollenwatch entities (entity_id, unique_id, platform, ...)
  device_registry.json  — all devices (filtered to those with pollenwatch entities)
  states.json           — current state object for each pollenwatch entity
  logs.txt              — container logs since the snapshot point
  meta.json             — snapshot timestamp, HA version, pollenwatch version, run_id
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from .ha_api import HAClient
from .ha_ws import HAWebSocket


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


async def _take_async(client: HAClient, ws: HAWebSocket, out_dir: Path,
                      container_name: str, since: str | None,
                      run_id: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Pollenwatch config entries
    pw_entries_summary = client.list_config_entries(domain="pollenwatch")
    full_entries: list[dict] = []
    for summary in pw_entries_summary:
        full = await ws.config_entry_get(summary["entry_id"])
        if full:
            full_entries.append(full)
        else:
            # Fall back to the summary; data/options may be missing but
            # version + entry_id + title are there.
            full_entries.append(summary)
    (out_dir / "config_entries.json").write_text(json.dumps(full_entries, indent=2))

    # 2. Entity registry (filter to pollenwatch)
    all_entities = await ws.entity_registry_list()
    pw_entities = [e for e in all_entities if e.get("platform") == "pollenwatch"]
    (out_dir / "entity_registry.json").write_text(json.dumps(pw_entities, indent=2))

    # 3. Device registry (full — verifier filters per use)
    devices = await ws.device_registry_list()
    (out_dir / "device_registry.json").write_text(json.dumps(devices, indent=2))

    # 4. States for each pollenwatch entity
    states = []
    for ent in pw_entities:
        st = client.get_state(ent["entity_id"])
        states.append({"entity_id": ent["entity_id"], "state": st})
    (out_dir / "states.json").write_text(json.dumps(states, indent=2))

    # 5. Container logs since `since` (if provided, else full log)
    log_cmd = ["docker", "logs"]
    if since:
        log_cmd += ["--since", since]
    log_cmd.append(container_name)
    try:
        logs = subprocess.run(
            log_cmd, capture_output=True, text=True, timeout=30, check=False,
        )
        log_text = (logs.stdout or "") + (logs.stderr or "")
    except Exception as e:
        log_text = f"<docker logs failed: {e}>"
    (out_dir / "logs.txt").write_text(log_text)

    # 6. Meta
    ha_info = client.request("/api/config")[1] or {}
    meta = {
        "snapshot_iso": _iso_now(),
        "snapshot_monotonic": time.monotonic(),
        "run_id": run_id,
        "container_name": container_name,
        "ha_version": ha_info.get("version") if isinstance(ha_info, dict) else None,
        "components_count": len(ha_info.get("components", [])) if isinstance(ha_info, dict) else None,
        "pw_entity_count": len(pw_entities),
        "pw_config_entry_count": len(full_entries),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    return meta


def take_snapshot(
    client: HAClient,
    ws: HAWebSocket,
    out_dir: Path,
    container_name: str,
    run_id: str,
    since: str | None = None,
) -> dict:
    """Synchronous wrapper. `since` is a docker --since value (RFC3339 or
    relative like '5m'); None = full container log."""
    return asyncio.run(_take_async(client, ws, out_dir, container_name, since, run_id))


def load_snapshot(snapshot_dir: Path) -> dict:
    """Read a snapshot dir into a dict of {config_entries, entity_registry,
    device_registry, states, logs, meta}."""
    return {
        "config_entries": json.loads((snapshot_dir / "config_entries.json").read_text()),
        "entity_registry": json.loads((snapshot_dir / "entity_registry.json").read_text()),
        "device_registry": json.loads((snapshot_dir / "device_registry.json").read_text()),
        "states": json.loads((snapshot_dir / "states.json").read_text()),
        "logs": (snapshot_dir / "logs.txt").read_text(),
        "meta": json.loads((snapshot_dir / "meta.json").read_text()),
    }
