# Home Assistant compatibility

The declared minimum Home Assistant version (`hacs.json` → `homeassistant`) is
the **maximum** of the introduction versions of every HA-specific API the
integration relies on. This file is the paper trail so the floor is defensible
and future bumps are deliberate.

## Minimum: **2024.11.0**

| API / pattern | Used in | Introduced | Notes |
| --- | --- | --- | --- |
| `OptionsFlow.config_entry` auto-set property (we do **not** assign it in `__init__`) | `config_flow.py` | **2024.11** | **Gating.** Assigning `self.config_entry` in `OptionsFlow.__init__` was deprecated in 2024.11; the auto-set property is the supported pattern from then on. |
| `ConfigEntry` generic + `entry.runtime_data` (`type ...ConfigEntry = ConfigEntry[Coordinator]`) | `__init__.py`, `coordinator.py`, `sensor.py` | 2024.6 | Typed runtime storage. |
| `DataUpdateCoordinator(config_entry=...)` | `coordinator.py` | 2024.8 | Explicit config-entry binding. |
| `ConfigFlowResult` return type | `config_flow.py` | 2024.4 | |
| `selector.{Location,Select,Number}Selector` | `config_flow.py` | ≤ 2023.x | |
| `DeviceInfo`, `DeviceEntryType`, `CoordinatorEntity`, `has_entity_name`, `translation_key` | `sensor.py` | ≤ 2023.x | |

Maximum of the above = **2024.11.0**.

We deliberately do **not** use `AddConfigEntryEntitiesCallback` (added after
2025.1) — it would raise the floor without making milestone 2 cleaner. We use
`AddEntitiesCallback`.

## Testing vs. production vs. floor

These tell one coherent story (each ≥ the declared floor):

- **Declared floor:** 2024.11.0 (by the audit above).
- **Automated tests:** Home Assistant **2025.1.4**, via the pinned
  `pytest-homeassistant-custom-component==0.13.205`. 2025.1.4 ≥ the floor.
- **Production / live verification:** Home Assistant **2026.5.4** — the
  maintainer's instance, exercised end-to-end (config flow, sensors, options
  flow, coverage rejection) during the v0.1 deployment pass. This closes the gap
  between the test harness and the latest HA.

### Why the harness sits above the floor (deliberate)

The harness pins to 2025.1.4 rather than to the 2024.11.0 floor **on purpose**,
not by accident:

- The dev/CI package index available here only offers
  `pytest-homeassistant-custom-component` builds that install **HA 2025.1.x** —
  there is no harness build that installs 2024.11.x, so testing exactly at the
  floor is not possible in this environment.
- We therefore pin to the **newest HA the index offers** (2025.1.4): a single,
  reproducible version that is ≥ the floor and closest to production.
- The floor itself is established **by audit** (the table above — introduction
  versions read from the HA source), not by what the harness happens to install.
- Production (**2026.5.4**) brackets the tested version from above via the live
  deployment pass. So the floor is justified by audit and the *range we actually
  run on* (2025.1.4 → 2026.5.4) sits comfortably above it.

If a harness build that installs ~2024.11.x becomes available, add a CI matrix
entry pinned there to catch floor regressions directly.

## Future

Milestone 3 (multi-source + cross-source analytics) is expected to adopt the
**HA 2026.5 per-source DataUpdateCoordinator pattern** (cf. UniFi PR 166806),
which fits the multi-source architecture. Adopting it will raise this floor to
2026.5; update this file and `hacs.json` at that point.
