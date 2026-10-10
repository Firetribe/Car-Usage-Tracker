"""Websocket API used by the panel."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_UPDATED


def _get_coordinator(hass: HomeAssistant):
    for key, value in hass.data.get(DOMAIN, {}).items():
        if not key.startswith("_"):
            return value
    return None


def _payload(coordinator) -> dict:
    return {
        "drivers": coordinator.drivers,
        "trips": sorted(
            coordinator.trips, key=lambda t: t["start"], reverse=True
        ),
        "totals": coordinator.totals(),
        "unassigned": coordinator.unassigned_distance(),
        "open_trip": coordinator.open_trip,
    }


@callback
def async_register(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_subscribe)
    websocket_api.async_register_command(hass, ws_assign)
    websocket_api.async_register_command(hass, ws_delete)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe"})
@callback
def ws_subscribe(hass, connection, msg) -> None:
    coordinator = _get_coordinator(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_loaded", "Integration not loaded")
        return

    @callback
    def _send() -> None:
        connection.send_message(
            websocket_api.event_message(msg["id"], _payload(coordinator))
        )

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(
        hass, SIGNAL_UPDATED, _send
    )
    connection.send_result(msg["id"])
    _send()


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/assign",
        vol.Required("trip_id"): str,
        vol.Required("drivers"): [str],
    }
)
@websocket_api.require_admin
@callback
def ws_assign(hass, connection, msg) -> None:
    coordinator = _get_coordinator(hass)
    if coordinator is None or not coordinator.set_drivers_for_trip(
        msg["trip_id"], msg["drivers"]
    ):
        connection.send_error(msg["id"], "not_found", "Trip not found")
        return
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/delete", vol.Required("trip_id"): str}
)
@websocket_api.require_admin
@callback
def ws_delete(hass, connection, msg) -> None:
    coordinator = _get_coordinator(hass)
    if coordinator is None or not coordinator.delete_trip(msg["trip_id"]):
        connection.send_error(msg["id"], "not_found", "Trip not found")
        return
    connection.send_result(msg["id"])