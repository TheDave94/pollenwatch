"""The PollenWatch integration.

Home Assistant setup wiring (config entries, coordinators, platforms) is added
in a later milestone. For now this package primarily hosts the source data
layer under ``sources/``, which is usable standalone (see
``sources/open_meteo.py``).
"""

from __future__ import annotations

from .const import DOMAIN

__all__ = ["DOMAIN"]
