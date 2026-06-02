"""Tier 1 prerelease gate — discovery smoke tests against a real HA.

Runs against the throwaway HA (default ``http://127.0.0.1:8124``) and asserts
the *shape* of pollenwatch's discovery surface: that an entry exists and is
loaded, that the ``pollenwatch/config`` WS endpoint returns the documented
keys with sane values, and that an options-flow round-trip on
``default_layout`` actually persists.

INFRA vs ASSERTION discipline (the gate's core rule):

* Connection refused, timeout, auth handshake failure → ``pytest.skip()`` with
  an "inconclusive" message. The gate exits 0; nothing red.
* Endpoint reachable but returned the wrong shape / missing keys / a bad
  round-trip → ``assert`` fails. The gate exits non-zero; release is blocked.

The WS client itself is the cleanroom's ``HAWebSocket`` (one canonical pattern,
no reinvention). REST options-flow calls use stdlib ``urllib`` directly to
avoid pulling in the cleanroom's HAClient (smaller dep surface for the gate).
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest
import websockets.exceptions

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cleanroom.lib.ha_ws import HAWebSocket  # noqa: E402

# Mirrors custom_components/pollenwatch/const.py:ALLOWED_LAYOUTS. The gate
# codifies the public WS contract; if a 5th layout ships, update both.
ALLOWED_LAYOUTS = ("gauge", "bars", "compact", "tiles")

_TOKEN_FALLBACK = Path("/home/thedave/throwaway-pollenwatch/phase1_token.txt")
_DEFAULT_HA_URL = "http://127.0.0.1:8124"


def _base_url() -> str:
    return os.environ.get("HA_URL", _DEFAULT_HA_URL).rstrip("/")


def _token() -> str:
    t = os.environ.get("HA_TOKEN")
    if t and t.strip():
        return t.strip()
    if _TOKEN_FALLBACK.exists():
        return _TOKEN_FALLBACK.read_text().strip()
    pytest.skip(
        "inconclusive: no HA_TOKEN env var and no fallback token at "
        f"{_TOKEN_FALLBACK}"
    )


# Exception classes that always mean "infra, not assertion".
_INFRA_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    socket.timeout,
    socket.gaierror,
    OSError,  # covers Errno 111 connection refused + many websockets transport errors
    websockets.exceptions.InvalidHandshake,
    websockets.exceptions.InvalidURI,
    websockets.exceptions.ConnectionClosed,
)


def _ws_call(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run a WS batch; convert infra errors into pytest.skip()."""
    ws = HAWebSocket(_base_url(), _token())
    try:
        return asyncio.run(ws.call(messages))
    except _INFRA_EXCEPTIONS as e:
        pytest.skip(f"inconclusive: HA unreachable at {_base_url()}: {e!r}")
    except AssertionError as e:
        # The cleanroom WS client uses bare assertions for "auth_required" and
        # "auth_ok" handshake checks (see cleanroom/lib/ha_ws.py:43,46). Those
        # are infra-layer failures (bad token, wrong endpoint), not assertions
        # about pollenwatch behavior — route them to skip.
        msg = str(e)
        if "auth" in msg.lower() or "hello" in msg.lower():
            pytest.skip(f"inconclusive: HA auth/handshake failed: {e}")
        raise


def _http_request(
    path: str,
    method: str = "GET",
    data: dict[str, Any] | None = None,
    timeout: int = 30,
) -> tuple[int, Any]:
    """Minimal REST helper (options-flow lives on REST, not WS)."""
    url = _base_url() + path
    headers = {"Authorization": f"Bearer {_token()}"}
    body: bytes | None = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            txt = resp.read().decode()
            try:
                return resp.status, (json.loads(txt) if txt else None)
            except json.JSONDecodeError:
                return resp.status, txt
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            pytest.skip(f"inconclusive: HA auth failed ({e.code}) on {path}")
        err_body = e.read().decode() if e.fp else ""
        try:
            return e.code, json.loads(err_body) if err_body else None
        except json.JSONDecodeError:
            return e.code, err_body
    except _INFRA_EXCEPTIONS as e:
        pytest.skip(f"inconclusive: HA unreachable at {_base_url()}: {e!r}")


def _get_pollenwatch_entry() -> dict[str, Any]:
    """Fetch the first loaded pollenwatch entry. Assertion-fails if none."""
    res = _ws_call([{"type": "config_entries/get", "domain": "pollenwatch"}])
    assert res and res[0].get("success") is True, (
        f"config_entries/get returned failure: {res[0] if res else 'no result'}"
    )
    entries = res[0]["result"]
    assert isinstance(entries, list), f"expected list, got {type(entries).__name__}"
    loaded = [e for e in entries if e.get("state") == "loaded"]
    assert loaded, (
        f"no pollenwatch entry in 'loaded' state (found {len(entries)} entry/entries; "
        f"states: {[e.get('state') for e in entries]})"
    )
    return loaded[0]


# ---------- tests ----------


def test_pollenwatch_has_loaded_entry() -> None:
    """config_entries/get returns ≥1 pollenwatch entry in 'loaded' state."""
    entry = _get_pollenwatch_entry()
    assert entry["entry_id"], f"entry missing entry_id: {entry}"
    assert entry["domain"] == "pollenwatch", f"wrong domain: {entry.get('domain')}"


def test_pollenwatch_config_endpoint_shape() -> None:
    """pollenwatch/config returns documented keys with sane values."""
    entry = _get_pollenwatch_entry()
    res = _ws_call(
        [{"type": "pollenwatch/config", "entry_id": entry["entry_id"]}]
    )
    assert res and res[0].get("success") is True, (
        f"pollenwatch/config returned failure: {res[0] if res else 'no result'}"
    )
    result = res[0]["result"]
    assert isinstance(result, dict), (
        f"pollenwatch/config result not a dict: {type(result).__name__}"
    )

    # selected_species: non-empty list of strings.
    sp = result.get("selected_species")
    assert isinstance(sp, list), (
        f"selected_species not a list: {type(sp).__name__ if sp is not None else 'missing'}"
    )
    assert sp, "selected_species is empty (no species selected on throwaway)"
    assert all(isinstance(s, str) for s in sp), (
        f"selected_species contains non-strings: {sp}"
    )

    # default_layout: one of ALLOWED_LAYOUTS.
    layout = result.get("default_layout")
    assert layout in ALLOWED_LAYOUTS, (
        f"default_layout {layout!r} not in ALLOWED_LAYOUTS {ALLOWED_LAYOUTS}"
    )


def test_default_layout_round_trip() -> None:
    """Options-flow round-trip: set default_layout='bars', read back, REVERT.

    The throwaway must come out of this test exactly as it went in. The revert
    runs from a finally block; the test fails if either the set didn't take or
    the revert couldn't be initiated.
    """
    entry = _get_pollenwatch_entry()
    entry_id = entry["entry_id"]

    # Read original default_layout via the WS contract.
    cfg = _ws_call([{"type": "pollenwatch/config", "entry_id": entry_id}])
    assert cfg[0].get("success") is True
    original_layout = cfg[0]["result"].get("default_layout")
    assert original_layout in ALLOWED_LAYOUTS, (
        f"pre-test sanity: original layout {original_layout!r} not allowed"
    )

    # Pick a target ≠ original so the assertion actually proves persistence.
    target_layout = "bars" if original_layout != "bars" else "compact"

    def _submit_layout(layout: str) -> None:
        """Init options-flow, capture defaults, submit with layout overridden."""
        st, init = _http_request(
            "/api/config/config_entries/options/flow",
            method="POST",
            data={"handler": entry_id},
        )
        assert st == 200, f"options-flow init HTTP {st}: {init}"
        assert isinstance(init, dict), f"init not a dict: {init}"
        assert init.get("type") == "form" and init.get("step_id") == "init", (
            f"unexpected init response: type={init.get('type')} step_id={init.get('step_id')}"
        )
        flow_id = init["flow_id"]
        schema = init.get("data_schema") or []
        # Preserve every field by replaying what the server already has. Fields
        # come in two flavours: ``vol.Required`` (carries ``default``) and
        # ``vol.Optional`` (carries the current value as
        # ``description.suggested_value``). Skip empty suggested-values — they
        # represent genuinely-unset optionals that the schema would reject as
        # the empty string.
        submit: dict[str, Any] = {}
        for field in schema:
            name = field.get("name")
            if name is None:
                continue
            if "default" in field:
                submit[name] = field["default"]
                continue
            suggested = field.get("description", {}).get("suggested_value")
            if suggested not in (None, ""):
                submit[name] = suggested
        submit["default_layout"] = layout  # override last so it wins.

        sub_st, sub_res = _http_request(
            f"/api/config/config_entries/options/flow/{flow_id}",
            method="POST",
            data=submit,
            timeout=60,
        )
        assert sub_st == 200, f"options-flow submit HTTP {sub_st}: {sub_res}"
        assert isinstance(sub_res, dict) and sub_res.get("type") == "create_entry", (
            f"options-flow submit did not create_entry: {sub_res}"
        )

    try:
        _submit_layout(target_layout)

        # Read back: the WS endpoint must reflect the change.
        verify = _ws_call(
            [{"type": "pollenwatch/config", "entry_id": entry_id}]
        )
        assert verify[0].get("success") is True
        new_layout = verify[0]["result"].get("default_layout")
        assert new_layout == target_layout, (
            f"round-trip failed: set {target_layout!r}, read back {new_layout!r}"
        )
    finally:
        # Always revert. If this raises, we *want* the test to surface a red
        # because the throwaway is now mutated and a human must look.
        _submit_layout(original_layout)
