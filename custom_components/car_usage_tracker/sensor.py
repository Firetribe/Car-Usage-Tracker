"""Sensors for Car Usage Tracker."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_UPDATED
from .coordinator import CarTracker


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    car: CarTracker = hass.data[DOMAIN]["cars"][entry.entry_id]

    entities: list[CarSensor] = [
        CarSensor(car, "total_km", "total_km", "km", "mdi:counter", lambda c: c.totals()["total_km"]),
        CarSensor(car, "unassigned_km", "unassigned_km", "km", "mdi:map-marker-question", lambda c: c.totals()["unassigned_km"]),
        CarSensor(
            car, "open_trip_km", "open_trip_km", "km", "mdi:car-clock",
            lambda c: round((c.open_trip["end_km"] - c.open_trip["start_km"]), 1)
            if c.open_trip and c.open_trip.get("end_km") is not None else 0.0,
            state_class=None,
        ),
    ]

    if car.battery_entity and car.capacity:
        entities.append(
            CarSensor(
                car, "avg_consumption", "avg_consumption", "kWh/100km", "mdi:lightning-bolt",
                lambda c: c.totals()["consumption"],
            )
        )

    for driver in car.drivers:
        driver_id = driver.lower().replace(" ", "_")
        entities.append(
            CarSensor(
                car, f"driver_{driver_id}_km", "driver_km", "km", "mdi:account-route",
                lambda c, d=driver: c.totals()["drivers"].get(d, {}).get("km", 0.0),
                translation_placeholders={"driver": driver},
            )
        )
        if car.battery_entity and car.capacity:
            entities.append(
                CarSensor(
                    car, f"driver_{driver_id}_energy", "driver_energy", "kWh", "mdi:battery-charging",
                    lambda c, d=driver: c.totals()["drivers"].get(d, {}).get("kwh", 0.0),
                    translation_placeholders={"driver": driver},
                )
            )

    async_add_entities(entities)


class CarSensor(SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self, car: CarTracker, key: str, name: str, unit: str, icon: str, value_fn,
        state_class=SensorStateClass.MEASUREMENT, translation_placeholders: dict[str, str] | None = None,
    ) -> None:
        self._car = car
        self._value_fn = value_fn
        self._attr_translation_key = name
        self._attr_translation_placeholders = translation_placeholders or {}
        self._attr_name = None
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        self._attr_unique_id = f"{car.entry.entry_id}_{key}"
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
                self.hass, f"{SIGNAL_UPDATED}_{self._car.entry.entry_id}", _update
            )
        )