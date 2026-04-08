"""Config flow for Meal Planner."""
from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol

from .const import DOMAIN

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

        current_lang = self._config_entry.options.get("lang", "de")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("lang", default=current_lang): vol.In(LANG_OPTIONS),
            }),
        )
