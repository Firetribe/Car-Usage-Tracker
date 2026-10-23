"""Sensors for Car Usage Tracker."""
from __future__ import annotations

from typing import Callable

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_UPDATED
from .coordinator import CarTracker


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    car: CarTracker = hass.data[DOMAIN]["cars"][entry.entry_id]

    entities: list[CarSensor] = [
        CarSensor(
            car, "total_km", "Total Kilometer", "km", "mdi:counter",
            lambda c: c.totals()["total_km"],
            fallback_name="Total Kilometer",
        ),
        CarSensor(
            car, "unassigned_km", "Unassigned Kilometer", "km", "mdi:map-marker-question",
            lambda c: c.totals()["unassigned_km"],
            fallback_name="Unassigned Kilometer",
        ),
        CarSensor(
            car, "open_trip_km", "Current trip", "km", "mdi:car-clock",
            lambda c: round(
                (c.open_trip["end_km"] - c.open_trip["start_km"]), 1
            ) if c.open_trip and c.open_trip.get("end_km") is not None else 0.0,
            fallback_name="Current trip",
            state_class=None,
        ),
    ]

    if car.battery_entity and car.capacity:
        entities.append(
            CarSensor(
                car, "avg_consumption", "Average energy consumption",
                "kWh/100km", "mdi:lightning-bolt",
                lambda c: c.totals()["consumption"],
                fallback_name="Average energy consumption",
            )
        )

    for driver in car.drivers:
        driver_id = driver.lower().replace(" ", "_")
        entities.append(
            CarSensor(
                car, f"driver_{driver_id}_km", f"{driver} Kilometer", "km",
                "mdi:account-route",
                lambda c, d=driver: c.totals()["drivers"].get(d, {}).get("km", 0.0),
                fallback_name=f"{driver} Kilometer",
            )
        )
        if car.battery_entity and car.capacity:
            entities.append(
                CarSensor(
                    car, f"driver_{driver_id}_energy", f"{driver} Energy",
                    "kWh", "mdi:battery-charging",
                    lambda c, d=driver: c.totals()["drivers"].get(d, {}).get("kwh", 0.0),
                    fallback_name=f"{driver} Energy",
                )
            )

    async_add_entities(entities)


class CarSensor(SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        car: CarTracker,
        key: str,
        translation_key: str,
        unit: str,
        icon: str,
        value_fn: Callable,
        *,
        state_class=SensorStateClass.MEASUREMENT,
        fallback_name: str,
    ) -> None:
        self._car = car
        self._value_fn = value_fn
        self._attr_translation_key = translation_key
        self._attr_name = fallback_name  # robust fallback if translation missing
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, car.entry.entry_id)},
            name=car.name,
            manufacturer="Car Usage Tracker",
        )

    @property
    def native_value(self):
        return self._value_fn(self._car)

    async def async_added_to_hass(self) -> None:
        @callback
        def _update() -> None:
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATED + "_" + self._car.entry.entry_id, _update
            )
        )