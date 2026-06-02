"""E2E test conftest — overrides the in-process HA fixture from tests/conftest.py.

The e2e suite talks to a *real* HA over the network (the throwaway on
127.0.0.1:8124), so it must NOT pull in pytest-homeassistant-custom-component
or any of the in-process HA machinery. Overriding the autouse fixture here
keeps these tests runnable with just pytest + websockets.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations():
    """Override the parent autouse fixture; e2e tests don't load an in-process HA."""
    yield


@pytest.fixture(autouse=True)
def _enable_network_for_e2e():
    """Re-enable real sockets for the e2e suite.

    ``pytest-socket`` is pulled in transitively by ``pytest-homeassistant-custom-component``
    and blocks all socket use by default — which is correct for the in-process
    HA tests but wrong here, since the whole point is to talk to a real HA.
    On the lean prerelease-gate runner ``pytest-socket`` isn't installed at
    all, so the import is best-effort.
    """
    try:
        from pytest_socket import enable_socket
    except ImportError:
        yield
        return
    enable_socket()
    yield
