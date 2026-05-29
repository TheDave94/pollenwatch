"""Pytest configuration for PollenWatch tests.

Ensures the repository root is importable so ``custom_components.pollenwatch``
resolves regardless of pytest's import mode.
"""

from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
