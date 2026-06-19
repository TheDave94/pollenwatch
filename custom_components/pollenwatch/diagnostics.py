"""Diagnostics support for PollenWatch.

Dumps the config entry's data + options plus a per-coordinator summary of each
source's last fetch result — without leaking location OR credentials. Location
coordinates and any source ``api_key`` (polleninformation / Google live under
``options[sources][<source>][api_key]``) are redacted; ``async_redact_data``
recurses, so nested keys are covered.

(AirWatch's diagnostics was ported from this shape; this implements it here. The
api_key redaction is PollenWatch-specific — AirWatch's sources are all keyless.)
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY
from .coordinator import PollenWatchConfigEntry
from .sources.base import SourceResult

TO_REDACT = {CONF_LATITUDE, CONF_LONGITUDE, CONF_API_KEY}


def _summarise_result(result: SourceResult | None) -> dict[str, Any] | None:
    """Compact, location-free summary of a source's last fetch result."""
    if result is None:
        return None
    return {
        "source": result.source,
        "status": result.status.value,
        "timezone": result.timezone,
        "current_time": result.current_time,
        "generated_at": result.generated_at,
        "station": result.station,
        "times": len(result.times),
        "allergens": {
            key: {
                "unit": series.unit,
                "current": series.current,
                "native": series.native,
                "values": len(series.values),
            }
            for key, series in result.allergens.items()
        },
        "message": result.message,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PollenWatchConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry (location + credentials redacted)."""
    data = entry.runtime_data
    coordinators = data.coordinators if data else {}
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinators": {
            source_key: {
                "last_update_success": coordinator.last_update_success,
                "update_interval": (
                    coordinator.update_interval.total_seconds()
                    if coordinator.update_interval
                    else None
                ),
                "result": _summarise_result(coordinator.data),
            }
            for source_key, coordinator in coordinators.items()
        },
    }
