"""Websocket API used by the Car Usage Tracker panel."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, SIGNAL_ANY


def _cars(hass: HomeAssistant) -> dict:
    return hass.data.get(DOMAIN, {}).get("cars", {})


@callback
def async_register(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_get_data)
    websocket_api.async_register_command(hass, ws_assign)
    websocket_api.async_register_command(hass, ws_delete)
    websocket_api.async_register_command(hass, ws_subscribe)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/get_data"})
@callback
def ws_get_data(hass, connection, msg):
    connection.send_result(
        msg["id"], {"cars": [car.as_dict() for car in _cars(hass).values()]}
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/assign_drivers",
        vol.Required("entry_id"): str,
        vol.Required("trip_id"): str,
        vol.Required("drivers"): [str],
    }
)
@websocket_api.require_admin
@callback
def ws_assign(hass, connection, msg):
    car = _cars(hass).get(msg["entry_id"])
    if car is None:
        connection.send_error(msg["id"], "not_found", "not_found_car")
        return
    if not car.assign_drivers(msg["trip_id"], msg["drivers"]):
        connection.send_error(msg["id"], "not_found", "not_found_trip")
        return
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/delete_trip",
        vol.Required("entry_id"): str,
        vol.Required("trip_id"): str,
    }
)
@websocket_api.require_admin
@callback
def ws_delete(hass, connection, msg):
    car = _cars(hass).get(msg["entry_id"])
    if car is None or not car.delete_trip(msg["trip_id"]):
        connection.send_error(msg["id"], "not_found", "not_found_trip")
        return
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe"})
@callback
def ws_subscribe(hass, connection, msg):
    """Push a signal to the panel whenever any car's data changes."""
    from homeassistant.helpers.dispatcher import async_dispatcher_connect

    @callback
    def forward(entry_id=None):
        connection.send_message(
            websocket_api.event_message(msg["id"], {"entry_id": entry_id})
        )

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(
        hass, SIGNAL_ANY, forward
    )
    connection.send_result(msg["id"])