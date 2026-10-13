"""Home Assistant services for Car Usage Tracker."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

SERVICE_ASSIGN_DRIVERS = "assign_drivers"
ASSIGN_DRIVERS_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): str,
        vol.Required("trip_id"): str,
        vol.Required("drivers"): vol.Any([str], str),
    }
)


def async_register(hass: HomeAssistant) -> None:
    """Register Car Usage Tracker services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_ASSIGN_DRIVERS,
        _async_assign_drivers,
        schema=ASSIGN_DRIVERS_SCHEMA,
    )


async def _async_assign_drivers(call: ServiceCall) -> None:
    cars = call.hass.data.get(DOMAIN, {}).get("cars", {})
    car = cars.get(call.data["entry_id"])
    if car is None:
        raise HomeAssistantError("Car Usage Tracker config entry not found")

    raw_drivers = call.data["drivers"]
    if isinstance(raw_drivers, str):
        drivers = [
            name.strip()
            for name in raw_drivers.replace("\n", ",").split(",")
            if name.strip()
        ]
    else:
        drivers = [name.strip() for name in raw_drivers if name.strip()]

    unknown_drivers = set(drivers) - set(car.drivers)
    if unknown_drivers:
        raise HomeAssistantError(
            f"Unknown driver(s) for {car.name}: {', '.join(sorted(unknown_drivers))}"
        )
    if not car.assign_drivers(call.data["trip_id"], drivers):
        raise HomeAssistantError("Trip not found")