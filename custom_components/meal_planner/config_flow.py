"""Config flow for Meal Planner."""
from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol

from .const import (
    CONF_HOLIDAY_COUNTRY,
    CONF_HOLIDAY_STATE,
    CONF_LANG,
    DOMAIN,
    HOLIDAY_COUNTRIES,
    HOLIDAY_STATES_DE,
)

LANG_OPTIONS = {"de": "Deutsch", "en": "English"}


class MealPlannerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Meal Planner."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="Meal Planner", data={})

        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MealPlannerOptionsFlow(config_entry)


class MealPlannerOptionsFlow(config_entries.OptionsFlow):
    """Handle Meal Planner options."""

    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self._config_entry.options
        current_lang = opts.get(CONF_LANG, "de")
        current_country = opts.get(CONF_HOLIDAY_COUNTRY, "DE")
        current_state = opts.get(CONF_HOLIDAY_STATE, "")

        schema = {
            vol.Required(CONF_LANG, default=current_lang): vol.In(LANG_OPTIONS),
            vol.Optional(CONF_HOLIDAY_COUNTRY, default=current_country): vol.In(HOLIDAY_COUNTRIES),
        }
        # The federal-state field only applies to Germany — hide it for other countries
        if current_country == "DE":
            schema[vol.Optional(CONF_HOLIDAY_STATE, default=current_state)] = vol.In(HOLIDAY_STATES_DE)

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))
