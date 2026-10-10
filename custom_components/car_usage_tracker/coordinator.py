"""Trip detection and storage."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import SIGNAL_UPDATED, STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)

MIN_TRIP_KM = 0.0  # trips with distance <= this are discarded


class TripCoordinator:
    """Detects trips from odometer changes and stores them."""

    def __init__(
        self,
        hass: HomeAssistant,
        odometer_entity: str,
        idle_minutes: int,
        drivers: list[str],
    ) -> None:
        self.hass = hass
        self.odometer_entity = odometer_entity
        self.idle = timedelta(minutes=idle_minutes)
        self.drivers = drivers

        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.trips: list[dict[str, Any]] = []
        self.last_odometer: float | None = None
        self.open_trip: dict[str, Any] | None = None

        self._unsub_state: CALLBACK_TYPE | None = None
        self._unsub_timer: CALLBACK_TYPE | None = None

    # ---------- lifecycle ----------

    async def async_start(self) -> None:
        data = await self._store.async_load() or {}
        self.trips = data.get("trips", [])
        self.last_odometer = data.get("last_odometer")
        self.open_trip = data.get("open_trip")

        self._unsub_state = async_track_state_change_event(
            self.hass, [self.odometer_entity], self._handle_state_event
        )

        # Process the current state (covers changes while HA was down)
        state = self.hass.states.get(self.odometer_entity)
        if state is not None:
            self._process_value(state.state, dt_util.utcnow())
        elif self.open_trip:
            self._schedule_close(self._remaining_idle())

    async def async_stop(self) -> None:
        if self._unsub_state:
            self._unsub_state()
            self._unsub_state = None
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None
        await self._store.async_save(self._serialize())

    # ---------- odometer handling ----------

    @callback
    def _handle_state_event(self, event: Event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        self._process_value(new_state.state, dt_util.utcnow())

    def _process_value(self, raw: str, now: datetime) -> None:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return  # unknown / unavailable

        if self.last_odometer is None:
            self.last_odometer = value
            self._save()
            return

        if value > self.last_odometer:
            if self.open_trip is None:
                self.open_trip = {
                    "id": uuid.uuid4().hex,
                    "start": now.isoformat(),
                    "start_odometer": self.last_odometer,
                    "end_odometer": value,
                    "last_change": now.isoformat(),
                }
            else:
                self.open_trip["end_odometer"] = value
                self.open_trip["last_change"] = now.isoformat()
            self.last_odometer = value
            self._schedule_close(self.idle)
            self._save()
        elif value < self.last_odometer:
            # Odometer reset / replaced: re-baseline, do not create a trip
            _LOGGER.warning(
                "Odometer decreased (%s -> %s); re-baselining",
                self.last_odometer,
                value,
            )
            self.last_odometer = value
            self._save()
        elif self.open_trip is not None and self._unsub_timer is None:
            # Value unchanged after restart with an open trip
            self._schedule_close(self._remaining_idle())

    # ---------- trip closing ----------

    def _remaining_idle(self) -> timedelta:
        if not self.open_trip:
            return self.idle
        last = dt_util.parse_datetime(self.open_trip["last_change"])
        if last is None:
            return timedelta(0)
        elapsed = dt_util.utcnow() - last
        return max(timedelta(0), self.idle - elapsed)

    def _schedule_close(self, delay: timedelta) -> None:
        if self._unsub_timer:
            self._unsub_timer()
        self._unsub_timer = async_call_later(
            self.hass, delay.total_seconds(), self._close_trip
        )

    @callback
    def _close_trip(self, _now: datetime) -> None:
        self._unsub_timer = None
        trip = self.open_trip
        self.open_trip = None
        if trip is None:
            return
        distance = round(trip["end_odometer"] - trip["start_odometer"], 3)
        if distance > MIN_TRIP_KM:
            self.trips.append(
                {
                    "id": trip["id"],
                    "start": trip["start"],
                    "end": trip["last_change"],
                    "start_odometer": trip["start_odometer"],
                    "end_odometer": trip["end_odometer"],
                    "distance": distance,
                    "drivers": [],
                }
            )
        self._save()
        self._notify()

    # ---------- public API ----------

    def set_drivers_for_trip(self, trip_id: str, drivers: list[str]) -> bool:
        valid = [d for d in dict.fromkeys(drivers) if d in self.drivers]
        for trip in self.trips:
            if trip["id"] == trip_id:
                trip["drivers"] = valid
                self._save()
                self._notify()
                return True
        return False

    def delete_trip(self, trip_id: str) -> bool:
        before = len(self.trips)
        self.trips = [t for t in self.trips if t["id"] != trip_id]
        if len(self.trips) != before:
            self._save()
            self._notify()
            return True
        return False

    def totals(self) -> dict[str, float]:
        totals = {d: 0.0 for d in self.drivers}
        for trip in self.trips:
            assigned = [d for d in trip["drivers"] if d in totals]
            if not assigned:
                continue
            share = trip["distance"] / len(assigned)
            for d in assigned:
                totals[d] += share
        return {d: round(v, 2) for d, v in totals.items()}

    def unassigned_distance(self) -> float:
        return round(
            sum(t["distance"] for t in self.trips if not t["drivers"]), 2
        )

    # ---------- persistence ----------

    def _serialize(self) -> dict[str, Any]:
        return {
            "trips": self.trips,
            "last_odometer": self.last_odometer,
            "open_trip": self.open_trip,
        }

    def _save(self) -> None:
        self._store.async_delay_save(self._serialize, 1)

    def _notify(self) -> None:
        async_dispatcher_send(self.hass, SIGNAL_UPDATED)