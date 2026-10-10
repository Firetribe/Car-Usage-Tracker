"""Config flow for Car Usage Tracker."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_DRIVERS,
    CONF_IDLE_MINUTES,
    CONF_ODOMETER,
    DEFAULT_DRIVERS,
    DEFAULT_IDLE_MINUTES,
    DEFAULT_ODOMETER,
    DOMAIN,
)


def _schema(defaults: dict) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_ODOMETER, default=defaults.get(CONF_ODOMETER, DEFAULT_ODOMETER)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(
                CONF_IDLE_MINUTES,
                default=defaults.get(CONF_IDLE_MINUTES, DEFAULT_IDLE_MINUTES),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=240, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_DRIVERS, default=defaults.get(CONF_DRIVERS, DEFAULT_DRIVERS)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=defaults.get(CONF_DRIVERS, DEFAULT_DRIVERS),
                    multiple=True,
                    custom_value=True,
                )
            ),
        }
    )


class CarUsageTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title="Car Usage Tracker", data=user_input)
        return self.async_show_form(step_id="user", data_schema=_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlow()


class OptionsFlow(config_entries.OptionsFlow):
    """Options (change odometer, idle time, drivers)."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(current))