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

## Milestone 3a audit (2026-05-29) — floor unchanged at 2024.11.0

3a added the per-source coordinator pattern, a multi-source runtime container,
config-entry migration (v1 → v2), and `SourceAuthError`. **None of these raise
the API floor:**

| 3a change | API | Introduced |
| --- | --- | --- |
| `entry.runtime_data` holds a container of multiple coordinators | `runtime_data` | 2024.6 |
| `async_migrate_entry` + `ConfigFlow.VERSION` | migration hooks | ≤ 2023.x |
| Several `DataUpdateCoordinator`s per entry (the "per-source pattern") | DataUpdateCoordinator | ≤ 2023.x (structural convention, not a new API) |
| `TextSelector(PASSWORD)` / `BooleanSelector` / `SelectSelector` | selectors | ≤ 2024.x |

**Correction to the earlier "Future" note:** the HA 2026.5 "per-source
DataUpdateCoordinator pattern" (UniFi PR 166806) is a *code-organisation
convention*, **not a 2026.5-only API** — running several coordinators with typed
`runtime_data` has worked since 2024.6. So adopting it does **not** technically
gate the integration to 2026.5. The honest, audit-derived floor remains
**2024.11.0**.

If the maintainer wants to declare **2026.5.0** anyway, that is legitimate but it
is a **support-policy** decision ("we only support current HA"), not an
API-required floor — and it should be labelled as such here rather than as an
audit result, and weighed against excluding users on 2024.11–2026.4 for no
technical reason. Left at the honest 2024.11.0 pending that call.
