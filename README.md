# Car Usage Tracker

A Home Assistant custom integration that automatically records driving
trips from an odometer entity (and optional battery / SoC entity) and
breaks them down by driver.

This README covers version **0.4.0**. For installation, sensor list
and configuration options see the HACS page rendered from this repo.

## What's new in 0.4.0

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

- takes the earliest `start` and `end_km` / latest `end` and `end_km`
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

## Validation

A stub test suite for the end-trip and merge logic lives under
`tests/test_coordinator_merge_end.py` and can be run with:

```bash
python -m unittest tests.test_coordinator_merge_end
```

The test file ships stubs for the Home Assistant runtime so it can
execute in any Python 3 environment without installing
`homeassistant`.
