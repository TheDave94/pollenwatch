"""Config and options flow for PollenWatch.

Milestone 2: location + allergen selection for the Open-Meteo source, with a
coverage probe that refuses locations outside CAMS European coverage (detected
via the source's out-of-coverage status, which comes from Open-Meteo's HTTP 400
error body — not from all-zero values). Location is intentionally fixed after
setup (changing it would invalidate the future recent-percentile baseline);
allergens and the update interval are editable in the options flow.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ALLERGEN_NAMES,
    CONF_ALLERGENS,
    CONF_SOURCES,
    CONF_UPDATE_INTERVAL,
    DEFAULT_ALLERGENS,
    DEFAULT_UPDATE_INTERVAL_MIN,
    DOMAIN,
    MAX_UPDATE_INTERVAL_MIN,
    MIN_UPDATE_INTERVAL_MIN,
    new_sources_config,
)
from .coordinator import PollenWatchConfigEntry, _entry_option
from .sources.base import SourceError, SourceStatus
from .sources.open_meteo import OpenMeteoSource

CONF_LOCATION = "location"

_ALLERGEN_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(value=key, label=name)
            for key, name in ALLERGEN_NAMES.items()
        ],
        multiple=True,
        mode=selector.SelectSelectorMode.LIST,
        translation_key="allergen",
    )
)

_INTERVAL_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=MIN_UPDATE_INTERVAL_MIN,
        max=MAX_UPDATE_INTERVAL_MIN,
        step=15,
        unit_of_measurement="min",
        mode=selector.NumberSelectorMode.BOX,
    )
)


async def _async_probe_coverage(
    hass, latitude: float, longitude: float, allergens: list[str]
) -> str | None:
    """Return an error key if the location can't be used, else None."""
    source = OpenMeteoSource(
        latitude, longitude, allergens, past_days=0, forecast_days=1
    )
    try:
        result = await source.async_fetch(session=async_get_clientsession(hass))
    except SourceError:
        return "cannot_connect"
    if result.status is SourceStatus.OUT_OF_COVERAGE:
        return "out_of_coverage"
    return None


class PollenWatchConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup of a PollenWatch config entry."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            location = user_input[CONF_LOCATION]
            latitude = location[CONF_LATITUDE]
            longitude = location[CONF_LONGITUDE]
            allergens = user_input[CONF_ALLERGENS]

            if not allergens:
                errors[CONF_ALLERGENS] = "no_allergens"
            else:
                await self.async_set_unique_id(f"{latitude:.4f}_{longitude:.4f}")
                self._abort_if_unique_id_configured()
                error = await _async_probe_coverage(
                    self.hass, latitude, longitude, allergens
                )
                if error:
                    errors["base"] = error
                else:
                    return self.async_create_entry(
                        title=f"PollenWatch ({latitude:.3f}, {longitude:.3f})",
                        data={
                            CONF_LATITUDE: latitude,
                            CONF_LONGITUDE: longitude,
                            CONF_ALLERGENS: allergens,
                        },
                        options={CONF_SOURCES: new_sources_config()},
                    )

        suggested_location = {
            CONF_LATITUDE: self.hass.config.latitude,
            CONF_LONGITUDE: self.hass.config.longitude,
        }
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LOCATION, default=suggested_location
                ): selector.LocationSelector(
                    selector.LocationSelectorConfig(radius=False)
                ),
                vol.Required(
                    CONF_ALLERGENS, default=DEFAULT_ALLERGENS
                ): _ALLERGEN_SELECTOR,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: PollenWatchConfigEntry,
    ) -> PollenWatchOptionsFlow:
        return PollenWatchOptionsFlow()


class PollenWatchOptionsFlow(OptionsFlow):
    """Edit allergens and the update interval after setup (location is fixed)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            if not user_input[CONF_ALLERGENS]:
                errors[CONF_ALLERGENS] = "no_allergens"
            else:
                return self.async_create_entry(data=user_input)

        current_allergens = _entry_option(
            self.config_entry, CONF_ALLERGENS, DEFAULT_ALLERGENS
        )
        current_interval = _entry_option(
            self.config_entry, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MIN
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ALLERGENS, default=current_allergens
                ): _ALLERGEN_SELECTOR,
                vol.Required(
                    CONF_UPDATE_INTERVAL, default=current_interval
                ): _INTERVAL_SELECTOR,
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )
