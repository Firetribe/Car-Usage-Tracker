"""Trip detection and storage for one car."""
from __future__ import annotations

import logging
import uuid

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BATTERY,
    CONF_CAPACITY,
    CONF_DRIVERS,
    CONF_IDLE_MINUTES,
    CONF_LEGACY_STORAGE,
    CONF_NAME,
    CONF_ODOMETER,
    DEFAULT_IDLE_MINUTES,
<<<<<<< Updated upstream
=======
    DOMAIN,
    EXTRA_LEGACY_KEYS,
>>>>>>> Stashed changes
    FALLBACK_NAME,
    LEGACY_STORAGE_KEY,
    SIGNAL_ANY,
    SIGNAL_UPDATED,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)
MIN_TRIP_KM = 0.1


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _state_float(state: State | None) -> float | None:
    if state is None or state.state in ("unknown", "unavailable", ""):
        return None
    return _to_float(state.state)


def _normalize_trip(t: dict) -> dict:
<<<<<<< Updated upstream
    """Make trips from any earlier version consistent."""
=======
    """Make trips from any earlier version consistent.

    Critical (0.4.1): never drop a trip just because a new field is missing.
    Older builds wrote ``start_odometer``/``end_odometer`` instead of
    ``start_km``/``end_km`` and trips without drivers were valid. We default
    missing fields so the trip is preserved.
    """
    if not isinstance(t, dict):
        return None  # type: ignore[return-value]

>>>>>>> Stashed changes
    start_km = _to_float(t.get("start_km", t.get("start_odometer")))
    end_km = _to_float(t.get("end_km", t.get("end_odometer")))
    distance = _to_float(t.get("distance", t.get("km")))
    if distance is None and start_km is not None and end_km is not None:
        distance = end_km - start_km

    drivers = t.get("drivers")
    if drivers is None:
        # Older builds used a single "driver" string. Treat it as a list of one.
        single = t.get("driver")
        drivers = [single] if single else []
    if isinstance(drivers, str):
        drivers = [drivers]
    if not isinstance(drivers, list):
        drivers = []

    trip = {
        "id": str(t.get("id") or uuid.uuid4().hex),
        "start": t.get("start") or t.get("start_time"),
        "end": t.get("end") or t.get("end_time"),
        "start_km": start_km,
        "end_km": end_km,
        "distance": round(distance or 0.0, 1),
        "drivers": list(drivers),
        "soc_start": _to_float(t.get("soc_start")),
        "soc_end": _to_float(t.get("soc_end")),
    }
    if "soc_min" in t:
        trip["soc_min"] = _to_float(t.get("soc_min"))
    return trip


def estimate_energy(soc_start, soc_end, capacity) -> float | None:
    """kWh used; 0.0 if drop < 1 %, None if unknown or charged during trip."""
    if soc_start is None or soc_end is None or not capacity:
        return None
    drop = soc_start - soc_end
    if drop < 0:
        return None
    return round(drop / 100.0 * capacity, 2)


class CarTracker:
    """Tracks trips for a single car (one config entry)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}{entry.entry_id}")
        self.trips: list[dict] = []
        self.open_trip: dict | None = None
        self.last_odo: float | None = None
        self.last_soc: float | None = None
        self._unsubs: list = []
        self._idle_unsub = None
<<<<<<< Updated upstream
=======
        self._save_now_needed = False
        self._recovered_legacy = False
>>>>>>> Stashed changes

    # ---------- configuration ----------

    @property
    def cfg(self) -> dict:
        return {**self.entry.data, **self.entry.options}

    @property
    def name(self) -> str:
        return self.cfg.get(CONF_NAME) or self.entry.title or FALLBACK_NAME

    @property
    def odometer_entity(self) -> str | None:
        return self.cfg.get(CONF_ODOMETER)

    @property
    def battery_entity(self) -> str | None:
        return self.cfg.get(CONF_BATTERY) or None

    @property
    def capacity(self) -> float | None:
        return _to_float(self.cfg.get(CONF_CAPACITY)) or None

    @property
    def idle_seconds(self) -> float:
        minutes = _to_float(self.cfg.get(CONF_IDLE_MINUTES)) or DEFAULT_IDLE_MINUTES
        return minutes * 60

    @property
    def drivers(self) -> list[str]:
        return list(self.cfg.get(CONF_DRIVERS) or [])

    # ---------- lifecycle ----------

    async def _try_load(self, key: str) -> dict | None:
        try:
            data = await Store(self.hass, STORAGE_VERSION, key).async_load()
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.debug("Car tracker: load %s failed: %s", key, err)
            return None
        return data

    async def async_setup(self) -> None:
        # 0.4.1: Tolerant loading. We try the per-car key first, then several
        # legacy keys. We never throw trips away because of a key rename or
        # because a trip record is missing a newer field; _normalize_trip
        # defaults missing fields.
        data = await self._store.async_load()
<<<<<<< Updated upstream
        if data is None and self.entry.data.get(CONF_LEGACY_STORAGE):
            legacy = Store(self.hass, STORAGE_VERSION, LEGACY_STORAGE_KEY)
            data = await legacy.async_load()
            if data:
                _LOGGER.info("Importing trips from v0.1 storage into %s", self.name)
=======

        if not data and self.cfg.get(CONF_LEGACY_STORAGE):
            legacy = Store(self.hass, STORAGE_VERSION, LEGACY_STORAGE_KEY)
            data = await legacy.async_load()
            if data:
                data["_migrated_from_legacy"] = True
                self._recovered_legacy = True
                _LOGGER.info(
                    "Imported trips from legacy %s storage into %s",
                    LEGACY_STORAGE_KEY, self.name,
                )

        if not data:
            for key in EXTRA_LEGACY_KEYS:
                candidate = await self._try_load(key)
                if candidate and isinstance(candidate, dict) and (
                    candidate.get("trips") or candidate.get("open_trip")
                ):
                    data = candidate
                    data["_migrated_from_legacy"] = True
                    self._recovered_legacy = True
                    _LOGGER.info(
                        "Recovered trips from legacy key %s for %s", key, self.name,
                    )
                    break

>>>>>>> Stashed changes
        data = data or {}

        # Always coerce; never filter. Even if a trip has no "drivers" key,
        # _normalize_trip gives it an empty list.
        raw_trips = data.get("trips") or []
        if isinstance(raw_trips, list):
            normalized = [_normalize_trip(t) for t in raw_trips]
            self.trips = [t for t in normalized if isinstance(t, dict)]
        else:
            self.trips = []
        self.open_trip = data.get("open_trip") if isinstance(data.get("open_trip"), dict) else None
        self.last_odo = _to_float(data.get("last_odo"))
        self.last_soc = _to_float(data.get("last_soc"))
<<<<<<< Updated upstream
        self._save_now_needed = bool(data) and not await self._store.async_load()
=======

        # If we recovered from a legacy location, persist immediately under
        # the per-car key so future loads don't need to fall back again.
        if self._recovered_legacy:
            self._save_now_needed = True

        from homeassistant.helpers.event import async_track_state_change_event
>>>>>>> Stashed changes

        entities = [e for e in (self.odometer_entity, self.battery_entity) if e]
        if entities:
            self._unsubs.append(
                async_track_state_change_event(self.hass, entities, self._on_state_change)
            )

        # Pick up current values (also handles distance driven while HA was down)
        if self.battery_entity:
            soc = _state_float(self.hass.states.get(self.battery_entity))
            if soc is not None:
                self._handle_soc(soc)
        if self.odometer_entity:
            odo = _state_float(self.hass.states.get(self.odometer_entity))
            if odo is not None:
                self._handle_odometer(odo)

        if self.open_trip and self._idle_unsub is None:
            self._schedule_close()

        if self._save_now_needed:
            await self._store.async_save(self._serialize())

    async def async_unload(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._idle_unsub:
            self._idle_unsub()
            self._idle_unsub = None
        await self._store.async_save(self._serialize())

    # ---------- state handling ----------

    @callback
    def _on_state_change(self, event: Event) -> None:
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        value = _state_float(new_state)
        if value is None:
            return
        if entity_id == self.odometer_entity:
            self._handle_odometer(value)
        elif entity_id == self.battery_entity:
            self._handle_soc(value)

    @callback
    def _handle_soc(self, soc: float) -> None:
        if self.open_trip is not None:
            current_min = self.open_trip.get("soc_min")
            if current_min is None or soc < current_min:
                self.open_trip["soc_min"] = soc
        else:
            self.last_soc = soc
        self._save()

    @callback
    def _handle_odometer(self, odo: float) -> None:
        if self.last_odo is None:
            self.last_odo = odo
            self._save()
            return
        if odo <= self.last_odo:
            if odo < self.last_odo - 1:
                _LOGGER.warning(
                    "%s: odometer went backwards (%s -> %s), ignoring",
                    self.name, self.last_odo, odo,
                )
            return

        now = dt_util.utcnow().isoformat()
        if self.open_trip is None:
            self.open_trip = {
                "id": uuid.uuid4().hex,
                "start": now,
                "start_km": self.last_odo,
                "soc_start": self.last_soc,
                "soc_min": self.last_soc,
            }
        self.open_trip["end"] = now
        self.open_trip["end_km"] = odo
        self.last_odo = odo
        self._schedule_close()
        self._save()
        self._notify()

    @callback
    def _schedule_close(self) -> None:
        if self._idle_unsub:
            self._idle_unsub()
        self._idle_unsub = async_call_later(self.hass, self.idle_seconds, self._close_trip)

    @callback
    def _close_trip(self, _now=None) -> None:
        self._idle_unsub = None
        trip = self.open_trip
        self.open_trip = None
        if not trip:
            return

        distance = (trip.get("end_km") or 0) - (trip.get("start_km") or 0)
        soc_end = trip.get("soc_min")
        # Base for the next trip: current SoC if known, else the trip's end SoC
        if self.battery_entity:
<<<<<<< Updated upstream
            cur = _state_float(self.hass.states.get(self.battery_entity))
            self.last_soc = cur if cur is not None else soc_end
=======
            soc_state = _state_float(self.hass.states.get(self.battery_entity))
            if soc_state is not None and (soc_end is None or soc_state < soc_end):
                soc_end = soc_state
>>>>>>> Stashed changes

        if distance >= MIN_TRIP_KM:
            trip["distance"] = round(distance, 1)
            trip["soc_end"] = soc_end
            trip.setdefault("drivers", [])
            trip.pop("soc_min", None)
            self.trips.append(_normalize_trip(trip))
            _LOGGER.debug("%s: trip closed, %.1f km", self.name, distance)
        self._save()
        self._notify()

    # ---------- user actions ----------

    def get_trip(self, trip_id: str) -> dict | None:
        return next((t for t in self.trips if t.get("id") == trip_id), None)

    @callback
    def assign_drivers(self, trip_id: str, drivers: list[str]) -> bool:
        trip = self.get_trip(trip_id)
        if trip is None:
            return False
        trip["drivers"] = [d for d in dict.fromkeys(drivers) if d in self.drivers]
        self._save()
        self._notify()
        return True

    @callback
    def delete_trip(self, trip_id: str) -> bool:
        before = len(self.trips)
        self.trips = [t for t in self.trips if t.get("id") != trip_id]
        if len(self.trips) == before:
            return False
        self._save()
        self._notify()
        return True

<<<<<<< Updated upstream
=======
    @callback
    def end_open_trip(self) -> dict | None:
        trip = self.open_trip
        if not trip:
            return None
        if self._idle_unsub:
            self._idle_unsub()
            self._idle_unsub = None
        now = dt_util.utcnow().isoformat()
        end_km = self.last_odo if self.last_odo is not None else trip.get("start_km")
        soc_end = trip.get("soc_min")
        if self.battery_entity:
            soc_state = _state_float(self.hass.states.get(self.battery_entity))
            if soc_state is not None and (soc_end is None or soc_state < soc_end):
                soc_end = soc_state
        trip["end"] = now
        trip["end_km"] = end_km
        distance = (end_km or 0) - (trip.get("start_km") or 0)
        self.open_trip = None
        if distance < MIN_TRIP_KM:
            self._notify()
            return None
        trip["distance"] = round(distance, 1)
        trip["soc_end"] = soc_end
        trip.setdefault("drivers", [])
        trip.pop("soc_min", None)
        normalized = _normalize_trip(trip)
        self.trips.append(normalized)
        self._save()
        self._notify()
        return normalized

    @callback
    def merge_trips(self, trip_ids: list[str]) -> dict | None:
        if not trip_ids or len(trip_ids) < 2:
            return None
        selected: list[dict] = []
        for tid in trip_ids:
            trip = self.get_trip(tid)
            if trip is None:
                return None
            selected.append(trip)
        selected.sort(key=lambda t: t.get("start") or "")
        earliest = selected[0]
        latest = selected[-1]
        start_km = earliest.get("start_km")
        end_km = latest.get("end_km")
        if start_km is None or end_km is None:
            return None
        total_distance = sum((t.get("distance") or 0) for t in selected)
        soc_start = next(
            (t.get("soc_start") for t in selected if t.get("soc_start") is not None),
            None,
        )
        soc_end = next(
            (t.get("soc_end") for t in reversed(selected) if t.get("soc_end") is not None),
            None,
        )
        merged_drivers = _merge_drivers([t.get("drivers") or [] for t in selected])
        merged = {
            "id": uuid.uuid4().hex,
            "start": earliest.get("start"),
            "end": latest.get("end"),
            "start_km": start_km,
            "end_km": end_km,
            "distance": round(total_distance, 1),
            "drivers": merged_drivers,
            "soc_start": soc_start,
            "soc_end": soc_end,
        }
        ids = set(trip_ids)
        self.trips = [t for t in self.trips if t["id"] not in ids]
        self.trips.append(_normalize_trip(merged))
        self.trips.sort(key=lambda t: t.get("start") or "")
        self._save()
        self._notify()
        return merged

>>>>>>> Stashed changes
    # ---------- calculations ----------

    def trip_view(self, trip: dict) -> dict:
        energy = estimate_energy(trip.get("soc_start"), trip.get("soc_end"), self.capacity)
        consumption = None
        if energy and trip["distance"] > 0:
            consumption = round(energy / trip["distance"] * 100, 1)
        return {
            **trip,
            "energy_kwh": energy,
            "consumption": consumption,  # kWh/100 km, None if < 1 % drop
            "low_resolution": energy == 0.0,
        }

    def totals(self) -> dict:
<<<<<<< Updated upstream
        drivers = {d: {"km": 0.0, "kwh": 0.0, "kwh_km": 0.0, "trips": 0.0} for d in self.drivers}
=======
        drivers: dict[str, dict] = {d: {"km": 0.0, "kwh": 0.0, "trips": 0.0} for d in self.drivers}
>>>>>>> Stashed changes
        unassigned_km = 0.0
        total_km = total_kwh = kwh_km = 0.0

        for trip in self.trips:
            dist = trip["distance"]
            energy = estimate_energy(trip.get("soc_start"), trip.get("soc_end"), self.capacity)
            total_km += dist
            if energy is not None:
                total_kwh += energy
                kwh_km += dist
            assigned = [d for d in trip["drivers"] if d in drivers]
            if not assigned:
                unassigned_km += dist
                continue
            share = 1 / len(assigned)
            for d in assigned:
                drivers[d]["km"] += dist * share
                drivers[d]["trips"] += share
                if energy is not None:
                    drivers[d]["kwh"] += energy * share
                    drivers[d]["kwh_km"] += dist * share

        def avg(kwh, km):
<<<<<<< Updated upstream
            return round(kwh / km * 100, 1) if km > 0 and kwh > 0 else None
=======
            return round(kwh / km * 100, 2) if km > 0 and kwh > 0 else None
>>>>>>> Stashed changes

        return {
            "drivers": {
                d: {
                    "km": round(v["km"], 1),
                    "kwh": round(v["kwh"], 1),
                    "trips": round(v["trips"], 2),
<<<<<<< Updated upstream
                    "consumption": avg(v["kwh"], v["kwh_km"]),
=======
                    "consumption": avg(v["kwh"], v["km"]),
>>>>>>> Stashed changes
                }
                for d, v in drivers.items()
            },
            "unassigned_km": round(unassigned_km, 1),
            "total_km": round(total_km, 1),
            "total_kwh": round(total_kwh, 1),
            "consumption": avg(total_kwh, kwh_km),
        }

    def as_dict(self) -> dict:
        return {
            "entry_id": self.entry.entry_id,
            "name": self.name,
            "drivers": self.drivers,
            "has_battery": bool(self.battery_entity and self.capacity),
            "capacity": self.capacity,
            "open_trip": self.open_trip,
            "trips": [self.trip_view(t) for t in reversed(self.trips)],
            "totals": self.totals(),
        }

    # ---------- persistence ----------

    def _serialize(self) -> dict:
        return {
            "trips": self.trips,
            "open_trip": self.open_trip,
            "last_odo": self.last_odo,
            "last_soc": self.last_soc,
        }

    @callback
    def _save(self) -> None:
        self._store.async_delay_save(self._serialize, 1.0)

    @callback
    def _notify(self) -> None:
        async_dispatcher_send(self.hass, f"{SIGNAL_UPDATED}_{self.entry.entry_id}")
<<<<<<< Updated upstream
        async_dispatcher_send(self.hass, SIGNAL_ANY, self.entry.entry_id)
=======
        async_dispatcher_send(self.hass, SIGNAL_ANY, self.entry.entry_id)
>>>>>>> Stashed changes
