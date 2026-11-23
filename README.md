# Car Usage Tracker

A Home Assistant custom integration that automatically records driving
trips from an odometer entity (and optional battery / SoC entity) and
breaks them down by driver.

This README covers version **1.1.0**.

## Installation

### Via HACS (recommended)

1. Open **HACS** in Home Assistant.
2. Open the menu (⋮) in the top right and choose **Custom repositories**.
3. Add `https://github.com/Firetribe/Car-Usage-Tracker` with the category
   **Integration**.
4. Search for **Car Usage Tracker** in HACS and download it.
5. Restart Home Assistant.

### Manual

1. Copy the folder `custom_components/car_usage_tracker` into the
   `custom_components` folder of your Home Assistant configuration.
2. Restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & services → Add integration**.
2. Search for **Car Usage Tracker** and follow the setup dialog.

The following options are available (one config entry per car):

| Option | Description |
| --- | --- |
| Name | Display name of the car |
| Odometer entity | Sensor reporting the odometer reading (km) |
| Battery entity | Optional sensor reporting the battery state of charge (%) |
| Battery capacity | Optional usable battery capacity (kWh), used to calculate energy and consumption |
| Idle minutes | Minutes without odometer change before a trip is closed automatically (default: 10) |
| Drivers | List of drivers that trips can be assigned to |

After setup, a **Car Usage** panel appears in the sidebar.

## What's new in 1.1.0

### End the current trip from the panel

If a trip is still flagged "in progress" (the odometer hasn't been idle
long enough to auto-close) you can now force it to close from the
Car Usage panel — useful right after you park the car.

The blue "Trip in progress" banner shows the running distance and an
**End trip now** button. Pressing it calls the new
`car_usage_tracker/end_trip` websocket command, which records the
trip with the current SoC and odometer values, then refreshes the
panel via the existing `car_usage_tracker/subscribe` push channel.

The same action is also exposed as a Home Assistant service:

```yaml
service: car_usage_tracker.end_trip
data:
  entry_id: <your config entry id>
```

### Merge two or more trips

Occasionally the integration will split a single real trip into two
records (for example because the idle threshold fired during a short
stop). The panel now lets you select multiple trips with checkboxes
and merge them into one. The merged trip:

- takes the earliest `start` and `start_km` / latest `end` and `end_km`
  from the selected trips,
- sums `distance`,
- preserves the union of `drivers` (order of first appearance),
- takes `soc_start` from the first trip with a value and `soc_end`
  from the last.

The action is exposed both in the panel (select rows → **Merge trips**)
and as a service:

```yaml
service: car_usage_tracker.merge_trips
data:
  entry_id: <your config entry id>
  trip_ids:
    - abc123
    - def456
```

Under the hood the panel calls `car_usage_tracker/merge_trips` over
the websocket, which delegates to `CarTracker.merge_trips()` in
`coordinator.py`. The merge is idempotent against duplicate IDs and
rejects requests with fewer than two distinct trips.

### Mobile-friendly layout

The Car Usage panel was tuned for phones:

- The start column shows **date on one line, time on a second line**,
  so it stays readable on narrow screens.
- Below **600 px** width the layout switches to a single responsive
  grid and the trip table no longer triggers a horizontal scrollbar
  — chips and energy cells wrap, and the cards collapse to a
  two-column grid instead of one wide row.
