"""Home Assistant services for Car Usage Tracker."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_TRIP_IDS, DOMAIN

SERVICE_ASSIGN_DRIVERS = "assign_drivers"
SERVICE_END_TRIP = "end_trip"
SERVICE_MERGE_TRIPS = "merge_trips"

ASSIGN_DRIVERS_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): str,
        vol.Required("trip_id"): str,
        vol.Required("drivers"): vol.Any([str], str),
    }
)

END_TRIP_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): str,
    }
)

MERGE_TRIPS_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): str,
        vol.Required(CONF_TRIP_IDS): vol.All([str], vol.Length(min=2)),
    }
)


def async_register(hass: HomeAssistant) -> None:
    """Register Car Usage Tracker services."""
    if not hass.services.has_service(DOMAIN, SERVICE_ASSIGN_DRIVERS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_ASSIGN_DRIVERS,
            _async_assign_drivers,
            schema=ASSIGN_DRIVERS_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_END_TRIP):
        hass.services.async_register(
            DOMAIN,
            SERVICE_END_TRIP,
            _async_end_trip,
            schema=END_TRIP_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_MERGE_TRIPS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_MERGE_TRIPS,
            _async_merge_trips,
            schema=MERGE_TRIPS_SCHEMA,
        )


def _get_car(hass: HomeAssistant, entry_id: str):
    cars = hass.data.get(DOMAIN, {}).get("cars", {})
    car = cars.get(entry_id)
    if car is None:
        raise HomeAssistantError("Car Usage Tracker config entry not found")
    return car


async def _async_assign_drivers(call: ServiceCall) -> None:
    car = _get_car(call.hass, call.data["entry_id"])

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


async def _async_end_trip(call: ServiceCall) -> None:
    car = _get_car(call.hass, call.data["entry_id"])
    if car.open_trip is None:
        raise HomeAssistantError(f"No active trip for {car.name}")
    trip = car.end_open_trip()
    if trip is None:
        # Nothing happened: there was a trip but it was too short to record.
        raise HomeAssistantError(
            f"Active trip for {car.name} was too short to be recorded"
        )


async def _async_merge_trips(call: ServiceCall) -> None:
    car = _get_car(call.hass, call.data["entry_id"])
    ids = call.data[CONF_TRIP_IDS]
    unique_ids = list(dict.fromkeys(ids))
    if len(unique_ids) < 2:
        raise HomeAssistantError("Provide at least two distinct trip IDs to merge")
    merged = car.merge_trips(unique_ids)
    if merged is None:
        raise HomeAssistantError(
            "Could not merge trips: make sure all IDs belong to this car and have valid km values"
        )