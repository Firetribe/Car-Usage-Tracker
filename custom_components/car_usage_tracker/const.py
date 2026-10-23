"""Constants for Car Usage Tracker."""

DOMAIN = "car_usage_tracker"
<<<<<<< Updated upstream
VERSION = "1.0.0"
=======
VERSION = "0.4.1"
>>>>>>> Stashed changes

CONF_NAME = "name"
CONF_ODOMETER = "odometer_entity"
CONF_BATTERY = "battery_entity"
CONF_CAPACITY = "battery_capacity"
CONF_IDLE_MINUTES = "idle_minutes"
CONF_DRIVERS = "drivers"
CONF_LEGACY_STORAGE = "legacy_storage"

DEFAULT_IDLE_MINUTES = 10
FALLBACK_NAME = "Car"

# Storage schema version. 0.4.1 keeps trips even when new fields are missing
# (e.g. "drivers" missing or "start_odometer" instead of "start_km") so that
# previously-recorded trips are never silently dropped during a load.
STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}.car."
LEGACY_STORAGE_KEY = f"{DOMAIN}.data"

# A handful of older pre-multi-car builds wrote the full data blob under the
# bare domain key with no version suffix. Reading it on first load makes
# recovery transparent if the user upgraded from very early versions.
EXTRA_LEGACY_KEYS = (
    f"{DOMAIN}",
    f"{DOMAIN}.storage",
)

SIGNAL_UPDATED = f"{DOMAIN}_updated"
SIGNAL_ANY = f"{DOMAIN}_any_updated"

PANEL_URL = "car-usage"
PANEL_TITLE = "Car Usage"
PANEL_ICON = "mdi:car-electric"
PANEL_COMPONENT = "car-usage-tracker-panel"
PANEL_FILE = "car-usage-tracker-panel.js"
STATIC_URL = f"/{DOMAIN}_static"