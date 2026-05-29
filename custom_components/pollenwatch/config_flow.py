"""Config and options flow for PollenWatch.

Stub — implemented in a later milestone. The flow will:
- collect lat/lon, allergen multi-select, per-source enable/disable, and an
  optional polleninformation.at API key;
- run an Open-Meteo coverage probe during setup and refuse to register when the
  location is outside CAMS European coverage (detected via the HTTP 400
  ``error`` response, NOT via all-zero values — an off-season European location
  legitimately returns all zeros);
- expose personal sensitivity multipliers in the options flow only.
"""

from __future__ import annotations
