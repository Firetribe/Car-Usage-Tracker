"""Constants for Car Usage Tracker."""

DOMAIN = "car_usage_tracker"
VERSION = "1.0.0"

CONF_NAME = "name"
CONF_ODOMETER = "odometer_entity"
CONF_BATTERY = "battery_entity"
CONF_CAPACITY = "battery_capacity"
CONF_IDLE_MINUTES = "idle_minutes"
CONF_DRIVERS = "drivers"
CONF_LEGACY_STORAGE = "legacy_storage"

# Neutral technical defaults only, no car- or user-specific values
DEFAULT_IDLE_MINUTES = 10
FALLBACK_NAME = "Car"

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}.car."
LEGACY_STORAGE_KEY = f"{DOMAIN}.data"

SIGNAL_UPDATED = f"{DOMAIN}_updated"   # + "_<entry_id>", for sensors
SIGNAL_ANY = f"{DOMAIN}_any_update"     # carries entry_id, for the panel

PANEL_URL = "car-usage"
PANEL_TITLE = "Car Usage"
PANEL_ICON = "mdi:car-electric"
PANEL_COMPONENT = "car-usage-tracker-panel"
PANEL_FILE = "car-usage-tracker-panel.js"
STATIC_URL = f"/{DOMAIN}_static"