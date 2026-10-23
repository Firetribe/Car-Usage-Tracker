"""Car Usage Tracker integration."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from . import websocket_api as cut_ws
from .const import (
    CONF_LEGACY_STORAGE,
    CONF_NAME,
    DOMAIN,
    FALLBACK_NAME,
    PANEL_COMPONENT,
    PANEL_FILE,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL,
    SIGNAL_ANY,
    STATIC_URL,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
    VERSION,
)
from .coordinator import CarTracker
from .services import async_register as async_register_services

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


def _domain_data(hass: HomeAssistant) -> dict:
    return hass.data.setdefault(
        DOMAIN, {"cars": {}, "static": False, "panel": False, "ws": False}
    )


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate v1 (single car) entries to v2."""
    if entry.version == 1:
        data = {**entry.data}
        data.setdefault(CONF_NAME, entry.title or FALLBACK_NAME)
        data[CONF_LEGACY_STORAGE] = True
        hass.config_entries.async_update_entry(
            entry, data=data, title=data[CONF_NAME], version=2
        )
        _LOGGER.info("Migrated Car Usage Tracker entry to version 2")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    dd = _domain_data(hass)

    tracker = CarTracker(hass, entry)
    await tracker.async_setup()
    dd["cars"][entry.entry_id] = tracker

    if not hass.services.has_service(DOMAIN, "assign_drivers"):
        async_register_services(hass)

    if not dd["ws"]:
        cut_ws.async_register(hass)
        dd["ws"] = True

    if not dd["static"]:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(Path(__file__).parent / "frontend"), False)]
        )
        dd["static"] = True

    if not dd["panel"]:
        await panel_custom.async_register_panel(
            hass,
            webcomponent_name=PANEL_COMPONENT,
            frontend_url_path=PANEL_URL,
            module_url=f"{STATIC_URL}/{PANEL_FILE}?v={VERSION}",
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            require_admin=False,
            config={},
        )
        dd["panel"] = True

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    async_dispatcher_send(hass, SIGNAL_ANY, entry.entry_id)
    return True


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    dd = _domain_data(hass)
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        tracker: CarTracker | None = dd["cars"].pop(entry.entry_id, None)
        if tracker:
            await tracker.async_unload()
        if not dd["cars"] and hass.services.has_service(DOMAIN, "assign_drivers"):
            hass.services.async_remove(DOMAIN, "assign_drivers")
        if not dd["cars"] and dd["panel"]:
            frontend.async_remove_panel(hass, PANEL_URL)
            dd["panel"] = False
        async_dispatcher_send(hass, SIGNAL_ANY, entry.entry_id)
    return ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete the trip storage when a car is removed."""
    await Store(
        hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}{entry.entry_id}"
    ).async_remove()