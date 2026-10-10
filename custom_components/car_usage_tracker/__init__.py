"""Car Usage Tracker integration."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import websocket_api as ws
from .const import (
    CONF_DRIVERS,
    CONF_IDLE_MINUTES,
    CONF_ODOMETER,
    DEFAULT_DRIVERS,
    DEFAULT_IDLE_MINUTES,
    DEFAULT_ODOMETER,
    DOMAIN,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL,
    STATIC_URL,
)
from .coordinator import TripCoordinator

PLATFORMS = ["sensor"]
PANEL_JS = "car-usage-tracker-panel.js"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    ws.async_register(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    cfg = {**entry.data, **entry.options}
    coordinator = TripCoordinator(
        hass,
        cfg.get(CONF_ODOMETER, DEFAULT_ODOMETER),
        int(cfg.get(CONF_IDLE_MINUTES, DEFAULT_IDLE_MINUTES)),
        list(cfg.get(CONF_DRIVERS, DEFAULT_DRIVERS)),
    )
    await coordinator.async_start()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Serve the frontend file and register the sidebar panel (once)
    if not hass.data[DOMAIN].get("_panel_registered"):
        frontend_dir = Path(__file__).parent / "frontend"
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(frontend_dir), False)]
        )
        await panel_custom.async_register_panel(
            hass,
            webcomponent_name="car-usage-tracker-panel",
            frontend_url_path=PANEL_URL,
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            module_url=f"{STATIC_URL}/{PANEL_JS}?v={entry.entry_id[:6]}",
            require_admin=False,
        )
        hass.data[DOMAIN]["_panel_registered"] = True

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload_on_update))
    return True


async def _reload_on_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: TripCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_stop()
    return unloaded