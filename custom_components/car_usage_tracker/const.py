"""Constants for Car Usage Tracker."""

DOMAIN = "car_usage_tracker"

CONF_ODOMETER = "odometer_entity"
CONF_IDLE_MINUTES = "idle_minutes"
CONF_DRIVERS = "drivers"

DEFAULT_ODOMETER = "sensor.opel_mokka_e_kilometer"
DEFAULT_IDLE_MINUTES = 10
DEFAULT_DRIVERS = ["Andreas", "Nathalie", "Johannes", "Verschiedene"]

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.data"

SIGNAL_UPDATED = f"{DOMAIN}_updated"

PANEL_URL = "car-usage"
PANEL_TITLE = "Car Usage"
PANEL_ICON = "mdi:car-electric"
STATIC_URL = f"/{DOMAIN}_static"