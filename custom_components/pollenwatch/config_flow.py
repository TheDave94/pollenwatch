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
    ALLERGENS,
    CONF_ALLERGENS,
    CONF_API_KEY,
    CONF_COUNTRY,
    CONF_ENABLED,
    CONF_SENSITIVITY,
    CONF_SOURCES,
    CONF_UPDATE_INTERVAL,
    DEFAULT_ALLERGENS,
    DEFAULT_SENSITIVITY,
    DEFAULT_UPDATE_INTERVAL_MIN,
    DOMAIN,
    MAX_SENSITIVITY,
    MAX_UPDATE_INTERVAL_MIN,
    MIN_SENSITIVITY,
    MIN_UPDATE_INTERVAL_MIN,
    SOURCE_OPEN_METEO,
    SOURCE_POLLENINFORMATION,
    new_sources_config,
)
from .coordinator import PollenWatchConfigEntry, _entry_option
from .sources.base import SourceAuthError, SourceError, SourceStatus
from .sources.open_meteo import OpenMeteoSource
from .sources.polleninformation import SUPPORTED_COUNTRIES, PolleninformationSource

CONF_LOCATION = "location"
CONF_ENABLE_PI = "enable_polleninformation"

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

# HA's built-in country selector: ISO-2 values, names localised automatically,
# bounded to the countries polleninformation serves. No translation keys needed.
_COUNTRY_SELECTOR = selector.CountrySelector(
    selector.CountrySelectorConfig(countries=list(SUPPORTED_COUNTRIES))
)

_API_KEY_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)

_SENSITIVITY_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=MIN_SENSITIVITY,
        max=MAX_SENSITIVITY,
        step=0.1,
        mode=selector.NumberSelectorMode.SLIDER,
    )
)


def _sensitivity_field(species: str) -> str:
    return f"{CONF_SENSITIVITY}_{species}"


async def _async_probe_polleninformation(
    hass, latitude: float, longitude: float, country: str, api_key: str,
    allergens: list[str],
) -> str | None:
    """Return a config-flow error key if polleninformation can't be used."""
    source = PolleninformationSource(
        latitude, longitude, country, api_key, allergens
    )
    try:
        result = await source.async_fetch(session=async_get_clientsession(hass))
    except SourceAuthError:
        return "invalid_api_key"
    except SourceError:
        return "cannot_connect"
    if result.status is SourceStatus.OUT_OF_COVERAGE:
        return "out_of_coverage"
    return None


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
    """Edit allergens, interval, and the polleninformation source after setup.

    Location is fixed (remove + re-add to change it).
    """

    def _supported_default_country(self) -> str | None:
        country = (self.hass.config.country or "").upper()
        return country if country in SUPPORTED_COUNTRIES else None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self.config_entry
        pi_cfg = _entry_option(entry, CONF_SOURCES, {}).get(
            SOURCE_POLLENINFORMATION, {}
        )

        if user_input is not None:
            allergens = user_input[CONF_ALLERGENS]
            enable_pi = user_input.get(CONF_ENABLE_PI, False)
            country = user_input.get(CONF_COUNTRY)
            api_key = user_input.get(CONF_API_KEY, "")

            if not allergens:
                errors[CONF_ALLERGENS] = "no_allergens"
            if enable_pi:
                if not country:
                    errors[CONF_COUNTRY] = "country_required"
                if not api_key:
                    errors[CONF_API_KEY] = "api_key_required"
                if not errors:
                    error = await _async_probe_polleninformation(
                        self.hass,
                        entry.data[CONF_LATITUDE],
                        entry.data[CONF_LONGITUDE],
                        country,
                        api_key,
                        allergens,
                    )
                    if error:
                        errors["base"] = error

            if not errors:
                sensitivity = {
                    species: user_input[_sensitivity_field(species)]
                    for species in ALLERGENS
                    if _sensitivity_field(species) in user_input
                }
                return self.async_create_entry(
                    data={
                        CONF_ALLERGENS: allergens,
                        CONF_UPDATE_INTERVAL: user_input[CONF_UPDATE_INTERVAL],
                        CONF_SENSITIVITY: sensitivity,
                        CONF_SOURCES: {
                            SOURCE_OPEN_METEO: {CONF_ENABLED: True},
                            SOURCE_POLLENINFORMATION: {
                                CONF_ENABLED: enable_pi,
                                CONF_API_KEY: api_key if enable_pi else "",
                                CONF_COUNTRY: country if enable_pi else "",
                            },
                        },
                    }
                )

        current_allergens = _entry_option(entry, CONF_ALLERGENS, DEFAULT_ALLERGENS)
        current_interval = _entry_option(
            entry, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MIN
        )
        default_country = pi_cfg.get(CONF_COUNTRY) or self._supported_default_country()
        current_sensitivity = _entry_option(entry, CONF_SENSITIVITY, {})
        schema_dict = {
            vol.Required(
                CONF_ALLERGENS, default=current_allergens
            ): _ALLERGEN_SELECTOR,
            vol.Required(
                CONF_UPDATE_INTERVAL, default=current_interval
            ): _INTERVAL_SELECTOR,
            vol.Required(
                CONF_ENABLE_PI, default=pi_cfg.get(CONF_ENABLED, False)
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_COUNTRY,
                description={"suggested_value": default_country},
            ): _COUNTRY_SELECTOR,
            vol.Optional(
                CONF_API_KEY,
                description={"suggested_value": pi_cfg.get(CONF_API_KEY) or None},
            ): _API_KEY_SELECTOR,
        }
        # Personal sensitivity multipliers (one per species).
        for species in ALLERGENS:
            schema_dict[
                vol.Optional(
                    _sensitivity_field(species),
                    default=current_sensitivity.get(species, DEFAULT_SENSITIVITY),
                )
            ] = _SENSITIVITY_SELECTOR
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema_dict), errors=errors
        )
