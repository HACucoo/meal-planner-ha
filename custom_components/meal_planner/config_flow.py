"""Config flow for Meal Planner."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .const import (
    CONF_HOLIDAY_COUNTRY,
    CONF_HOLIDAY_STATE,
    CONF_LANG,
    DOMAIN,
    HOLIDAY_COUNTRIES,
    HOLIDAY_STATES_DE,
)

LANG_OPTIONS = {"de": "Deutsch", "en": "English"}


class MealPlannerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Meal Planner."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="Meal Planner", data={})

        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> MealPlannerOptionsFlow:
        """Return the options flow handler."""
        return MealPlannerOptionsFlow()


class MealPlannerOptionsFlow(OptionsFlow):
    """Handle Meal Planner options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self.config_entry.options
        current_country = opts.get(CONF_HOLIDAY_COUNTRY, "DE")

        schema: dict[Any, Any] = {
            vol.Required(CONF_LANG, default=opts.get(CONF_LANG, "de")): vol.In(
                LANG_OPTIONS
            ),
            vol.Optional(CONF_HOLIDAY_COUNTRY, default=current_country): vol.In(
                HOLIDAY_COUNTRIES
            ),
        }
        # The federal-state field only applies to Germany, hide it otherwise
        if current_country == "DE":
            schema[
                vol.Optional(
                    CONF_HOLIDAY_STATE, default=opts.get(CONF_HOLIDAY_STATE, "")
                )
            ] = vol.In(HOLIDAY_STATES_DE)

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))
