"""Driver total sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_UPDATED


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        DriverTotalSensor(entry, coordinator, driver)
        for driver in coordinator.drivers
    ]
    entities.append(UnassignedSensor(entry, coordinator))
    async_add_entities(entities)


class _Base(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:map-marker-distance"

    def __init__(self, entry: ConfigEntry, coordinator) -> None:
        self._entry = entry
        self._coordinator = coordinator
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Car Usage Tracker",
            manufacturer="Car Usage Tracker",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATED, self._handle_update
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


class DriverTotalSensor(_Base):
    def __init__(self, entry, coordinator, driver: str) -> None:
        super().__init__(entry, coordinator)
        self._driver = driver
        self._attr_name = f"{driver} total"
        self._attr_unique_id = f"{entry.entry_id}_total_{driver.lower()}"

    @property
    def native_value(self) -> float:
        return self._coordinator.totals().get(self._driver, 0.0)


class UnassignedSensor(_Base):
    _attr_name = "Unassigned"

    def __init__(self, entry, coordinator) -> None:
        super().__init__(entry, coordinator)
        self._attr_unique_id = f"{entry.entry_id}_unassigned"

    @property
    def native_value(self) -> float:
        return self._coordinator.unassigned_distance()