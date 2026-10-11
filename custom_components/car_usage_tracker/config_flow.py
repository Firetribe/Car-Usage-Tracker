"""Config flow for Car Usage Tracker."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY,
    CONF_CAPACITY,
    CONF_DRIVERS,
    CONF_IDLE_MINUTES,
    CONF_NAME,
    CONF_ODOMETER,
    DEFAULT_IDLE_MINUTES,
    DOMAIN,
)


def _clean_drivers(raw) -> list[str]:
    if isinstance(raw, str):
        raw = raw.split(",")
    seen, result = set(), []
    for name in raw or []:
        name = str(name).strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            result.append(name)
    return result


def _validate(user_input: dict) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    data = dict(user_input)
    data[CONF_DRIVERS] = _clean_drivers(data.get(CONF_DRIVERS))
    if not data[CONF_DRIVERS]:
        errors[CONF_DRIVERS] = "no_drivers"
    if not data.get(CONF_BATTERY):
        data.pop(CONF_BATTERY, None)
        data.pop(CONF_CAPACITY, None)
    elif not data.get(CONF_CAPACITY):
        errors[CONF_CAPACITY] = "capacity_required"
    return data, errors


def _schema(cur: dict) -> vol.Schema:
    """Build the form; only pre-fill values the user has already entered."""

    def sv(key):
        return {"suggested_value": cur[key]} if cur.get(key) not in (None, "", []) else {}

    return vol.Schema(
        {
            vol.Required(CONF_NAME, description=sv(CONF_NAME)): selector.TextSelector(),
            vol.Required(CONF_ODOMETER, description=sv(CONF_ODOMETER)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_BATTERY, description=sv(CONF_BATTERY)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_CAPACITY, description=sv(CONF_CAPACITY)): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=250, step=0.1, unit_of_measurement="kWh",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_IDLE_MINUTES,
                default=cur.get(CONF_IDLE_MINUTES, DEFAULT_IDLE_MINUTES),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=240, step=1, unit_of_measurement="min",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(CONF_DRIVERS, description=sv(CONF_DRIVERS)): selector.TextSelector(
                selector.TextSelectorConfig(multiple=True)
            ),
        }
    )


class CarUsageTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _validate(user_input)
            if not errors:
                await self.async_set_unique_id(data[CONF_ODOMETER])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=data[CONF_NAME], data=data)
        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or {}), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return CarUsageTrackerOptionsFlow()


class CarUsageTrackerOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            data, errors = _validate(user_input)
            if not errors:
                # Keep the battery fields absent (not stale) if the user removed them
                for key in (CONF_BATTERY, CONF_CAPACITY):
                    data.setdefault(key, None)
                self.hass.config_entries.async_update_entry(
                    self.config_entry, title=data[CONF_NAME]
                )
                return self.async_create_entry(title="", data=data)
            current = user_input
        return self.async_show_form(
            step_id="init", data_schema=_schema(current), errors=errors
        )