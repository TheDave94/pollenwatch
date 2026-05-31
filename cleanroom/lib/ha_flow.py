"""Config-flow + options-flow over REST.

The species-field name AND flow shape vary by installed pollenwatch VERSION:

  * VERSION 1, 2 (e.g. v1.3.0) — SINGLE-step user form:
      submit {location, allergens} → create_entry
  * VERSION 3+ (e.g. v2.0.0, v2.1.0) — TWO-step flow:
      step "user":    submit {location} → form step_id="species"
      step "species": submit {selected_species} → create_entry

Bootstrap looks up `flow_version` and `species_field` from
cleanroom/config/pinned_release.json and passes them in.
"""
from __future__ import annotations

from typing import Any

from .ha_api import HAClient


def create_pollenwatch_entry(
    client: HAClient,
    *,
    latitude: float,
    longitude: float,
    species: list[str],
    species_field: str,
    flow_version: int,
) -> str | None:
    """Walk the pollenwatch config-flow. Returns the new entry_id, or None on failure.

    Branches on `flow_version`: single-step for v1/v2, two-step for v3+."""
    st, init = client.request(
        "/api/config/config_entries/flow",
        method="POST",
        data={"handler": "pollenwatch", "show_advanced_options": False},
    )
    if st != 200 or not isinstance(init, dict) or init.get("type") != "form":
        print(f"  ! config_flow init failed: HTTP {st}: {init}")
        return None
    flow_id = init["flow_id"]

    if flow_version <= 2:
        # Single-step (v1.x): submit location + species together.
        submit = {
            "location": {"latitude": latitude, "longitude": longitude},
            species_field: species,
        }
        st, result = client.request(
            f"/api/config/config_entries/flow/{flow_id}",
            method="POST", data=submit, timeout=60,
        )
        if isinstance(result, dict) and result.get("type") == "create_entry":
            return result["result"]["entry_id"]
        print(f"  ! config_flow (v1/v2) did not create entry: HTTP {st}: {result}")
        return None

    # Two-step (v3+): submit location only, then submit species.
    st, step1 = client.request(
        f"/api/config/config_entries/flow/{flow_id}",
        method="POST",
        data={"location": {"latitude": latitude, "longitude": longitude}},
        timeout=60,
    )
    if not isinstance(step1, dict):
        print(f"  ! step 'user' returned non-dict: HTTP {st}: {step1}")
        return None
    if step1.get("type") == "create_entry":
        # Some v3 schemas may complete in one step; tolerate it.
        return step1["result"]["entry_id"]
    if step1.get("type") != "form" or step1.get("step_id") != "species":
        print(f"  ! step 'user' did not advance to 'species': HTTP {st}: {step1}")
        return None

    st, step2 = client.request(
        f"/api/config/config_entries/flow/{flow_id}",
        method="POST",
        data={species_field: species},
        timeout=60,
    )
    if isinstance(step2, dict) and step2.get("type") == "create_entry":
        return step2["result"]["entry_id"]
    print(f"  ! step 'species' did not create entry: HTTP {st}: {step2}")
    return None


def submit_pollenwatch_options(
    client: HAClient,
    entry_id: str,
    *,
    species: list[str],
    species_field: str,
    options: dict[str, Any],
    update_interval: int = 60,
) -> bool:
    """Walk the pollenwatch options-flow for an existing entry. Returns True on
    create_entry."""
    st, init = client.request(
        "/api/config/config_entries/options/flow",
        method="POST",
        data={"handler": entry_id},
    )
    if st != 200 or not isinstance(init, dict) or init.get("type") != "form":
        print(f"  ! options_flow init failed: HTTP {st}: {init}")
        return False
    flow_id = init["flow_id"]

    submit: dict[str, Any] = {
        species_field: species,
        "update_interval": update_interval,
        "enable_polleninformation": options.get("enable_polleninformation", False),
        "enable_dwd": options.get("enable_dwd", False),
        "enable_meteoswiss": options.get("enable_meteoswiss", False),
        "enable_epin": options.get("enable_epin", False),
        "enable_google": options.get("enable_google", False),
    }
    # NOTE: Open-Meteo is the always-on default source in pollenwatch — there
    # is no `enable_open_meteo` field in the options schema (v1 or v3+). The
    # matrix.json may carry it as a no-op for human readability; we deliberately
    # don't forward it (voluptuous rejects extra keys).
    if options.get("enable_dwd"):
        submit["region"] = options.get("dwd_region", "121")
    # Sensitivity defaults — required by some VERSION schemas.
    for sp in species:
        submit[f"sensitivity_{sp}"] = 1.0

    st, result = client.request(
        f"/api/config/config_entries/options/flow/{flow_id}",
        method="POST",
        data=submit,
        timeout=60,
    )
    if isinstance(result, dict) and result.get("type") == "create_entry":
        return True
    print(f"  ! options_flow submit did not create entry: HTTP {st}: {result}")
    return False
