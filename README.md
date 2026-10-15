# Car Usage Tracker

Car Usage Tracker is a Home Assistant integration for recording how a shared car is used. It watches an odometer sensor, detects trips, and lets you allocate each trip to one or more drivers. An optional battery sensor can be used to estimate energy use and consumption.

Fuel costs and fuel tracking are not currently supported.

## Features

- Track multiple cars, each with its own odometer, driver list, and trip history.
- Detect a trip when the odometer increases. A trip ends after the configured period with no further odometer change.
- Attribute trips to one or more configured drivers from the Car Usage panel.
- View trip distance, total distance, unassigned distance, and per-driver totals.
- Optionally estimate trip energy use and kWh/100 km from a battery percentage sensor and the car's usable battery capacity.
- Filter panel history by recent trips, all trips, month, or a custom date range.
- Expose totals as Home Assistant sensors and store trip history across restarts.

## Installation

### HACS

1. In Home Assistant, open **HACS** and select **Integrations**.
2. Open the menu and choose **Custom repositories**.
3. Add `https://github.com/Firetribe/Car-Usage-Tracker` with the category **Integration**.
4. Find **Car Usage Tracker** in HACS and install it.
5. Restart Home Assistant.

### Manual

Copy the `custom_components/car_usage_tracker` directory into the `custom_components` directory in your Home Assistant configuration directory. Create the `custom_components` directory if it does not exist, then restart Home Assistant.

## Configuration

1. In Home Assistant, go to **Settings → Devices & services → Add integration**.
2. Search for **Car Usage Tracker**.
3. Configure one entry per car:
   - **Car name**: a name shown in the panel and device registry.
   - **Odometer sensor**: a numeric sensor whose state is the odometer reading in kilometers. Each odometer sensor can only be used once.
   - **Battery level sensor** (optional): a numeric sensor reporting state of charge as a percentage from 0 to 100.
   - **Usable battery capacity** (required when a battery sensor is selected): capacity in kWh.
   - **Minutes without odometer change before a trip ends**: the idle period used to close a trip. The default is 10 minutes.
   - **Drivers**: add at least one driver. These names are used for trip allocation.

The integration learns its initial odometer value as a baseline; it does not create a trip until the odometer increases. Trips shorter than 0.1 km are discarded. If Home Assistant restarts during a trip, the integration restores the in-progress trip from storage.

## Using the Integration

The **Car Usage** panel is added to the Home Assistant sidebar when at least one car is configured. Select a car to view its trips and totals. Choose driver names on a trip to split its distance (and estimated energy, when available) evenly among the selected drivers. Trips without an assigned driver contribute to the unassigned total. You can also delete trips from the panel.

The panel is available to regular Home Assistant users. Assigning drivers and deleting trips require an administrator account.

### Entities

The integration creates a device and the following sensors for each car:

| Sensor | Description |
| --- | --- |
| Total Kilometer | Total distance across recorded trips, in km. |
| Unassigned Kilometer | Distance from trips that have no assigned driver, in km. |
| Active trip | Distance accumulated by the trip currently in progress, in km. |
| Average energy consumption | Average estimated consumption in kWh/100 km. Available when battery tracking is configured. |
| Driver Kilometer | Distance allocated to a driver, in km. One entity is created per configured driver. |
| Driver Energy | Estimated energy allocated to a driver, in kWh. Available per driver when battery tracking is configured. |

Energy estimates use the change in battery percentage during a trip multiplied by the configured usable capacity. They are estimates, not vehicle-reported energy measurements. Charging during a trip or very small percentage changes can make an estimate unavailable or low-resolution.

### Service

The `car_usage_tracker.assign_drivers` service replaces the driver assignments for a recorded trip. Supply the config entry ID, trip ID, and a list of driver names. The service can be called from **Developer Tools → Actions** or an automation:

```yaml
action: car_usage_tracker.assign_drivers
data:
  entry_id: YOUR_CAR_CONFIG_ENTRY_ID
  trip_id: YOUR_TRIP_ID
  drivers:
    - Alex
    - Sam
```

Only drivers configured for that car are accepted. An empty list clears the assignment. The panel's driver controls are usually the easiest way to find and assign trips.

## Data and Privacy

Trip data is stored locally by Home Assistant in its integration storage. The integration reads the configured odometer and, if enabled, battery level entities; it does not require a cloud account or send trip data to an external service.

## Troubleshooting

- **No trips appear:** confirm the odometer sensor has a numeric state in kilometers and changes while the integration is loaded. The first value is used only as a baseline.
- **A trip stays open:** it closes only after the configured idle period has passed without another odometer increase.
- **Energy is missing:** verify the battery sensor reports percentage points (0–100), and that a usable battery capacity is configured.
- **A trip has no driver:** select one or more drivers for it in the Car Usage panel.

## Development

The integration source is in `custom_components/car_usage_tracker`. Contributions and bug reports are welcome. Please include your Home Assistant version, relevant log messages, and steps to reproduce when opening an issue.
