class CarUsageTrackerPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._cars = [];
    this._selected = null;
    this._unsub = null;
    this._loaded = false;
    this._hass = null;
    this._selectedTrips = new Set();
    this._merging = false;
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._load();
      this._subscribe();
    }
  }

  disconnectedCallback() {
    if (this._unsub) {
      this._unsub();
      this._unsub = null;
    }
  }

  async _subscribe() {
    try {
      this._unsub = await this._hass.connection.subscribeMessage(
        () => this._load(),
        { type: "car_usage_tracker/subscribe" }
      );
    } catch (e) {
      console.warn("Car Usage Tracker: live updates unavailable", e);
    }
  }

  async _load() {
    try {
      const res = await this._hass.callWS({ type: "car_usage_tracker/get_data" });
      this._cars = Array.isArray(res.cars) ? res.cars : [];
      if (!this._cars.find((c) => c.entry_id === this._selected)) {
        this._selected = this._cars.length ? this._cars[0].entry_id : null;
      }
      this._loaded = true;
      // Drop selections that no longer exist after reload.
      this._selectedTrips = new Set(
        Array.from(this._selectedTrips).filter((id) =>
          (this._car && this._car.trips || []).some((t) => t.id === id)
        )
      );
      this._render();
    } catch (e) {
      console.error("Car Usage Tracker: load failed", e);
    }
  }

  get _car() {
    return this._cars.find((c) => c.entry_id === this._selected);
  }

  async _toggleDriver(trip, driver) {
    const set = new Set(trip.drivers || []);
    if (set.has(driver)) {
      set.delete(driver);
    } else {
      set.add(driver);
    }
    await this._hass.callWS({
      type: "car_usage_tracker/assign_drivers",
      entry_id: this._selected,
      trip_id: trip.id,
      drivers: Array.from(set),
    });
  }

  async _deleteTrip(trip) {
    if (!confirm("Delete this trip?")) return;
    await this._hass.callWS({
      type: "car_usage_tracker/delete_trip",
      entry_id: this._selected,
      trip_id: trip.id,
    });
  }

  async _endOpenTrip() {
    const car = this._car;
    if (!car || !car.open_trip) return;
    if (!confirm("End the current trip now?")) return;
    try {
      await this._hass.callWS({
        type: "car_usage_tracker/end_trip",
        entry_id: this._selected,
      });
    } catch (e) {
      alert("Could not end trip: " + (e && e.message ? e.message : e));
    }
  }

  _toggleTripSelection(tripId) {
    if (this._selectedTrips.has(tripId)) {
      this._selectedTrips.delete(tripId);
    } else {
      this._selectedTrips.add(tripId);
    }
    this._render();
  }

  _clearTripSelection() {
    this._selectedTrips.clear();
    this._render();
  }

  async _mergeSelectedTrips() {
    const ids = Array.from(this._selectedTrips);
    if (ids.length < 2) return;
    if (!confirm(`Merge ${ids.length} trips into one?`)) return;
    this._merging = true;
    this._render();
    try {
      await this._hass.callWS({
        type: "car_usage_tracker/merge_trips",
        entry_id: this._selected,
        trip_ids: ids,
      });
      this._selectedTrips.clear();
    } catch (e) {
      alert("Could not merge trips: " + (e && e.message ? e.message : e));
    } finally {
      this._merging = false;
    }
  }

  _fmtDate(iso) {
    if (!iso) return { date: "–", time: "" };
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return { date: "–", time: "" };
    const lang = this._hass && this._hass.locale ? this._hass.locale.language : undefined;
    const date = d.toLocaleDateString(lang, { dateStyle: "short" });
    const time = d.toLocaleTimeString(lang, { timeStyle: "short" });
    return { date, time };
  }

  _esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return "&#" + c.charCodeAt(0) + ";";
    });
  }

  _consumptionCell(car, t) {
    if (!car.has_battery) return "";
    if (t.consumption != null) {
      return `<td>${t.energy_kwh} kWh<br><small>${t.consumption} kWh/100 km</small></td>`;
    }
    if (t.low_resolution) return `<td><small>&lt; 1 % battery</small></td>`;
    return `<td>–</td>`;
  }

  _render() {
    const root = this.shadowRoot;
    if (!this._loaded) return;

    if (!this._cars.length) {
      root.innerHTML = `${this._style()}<div class="wrap"><h1>Car Usage</h1>
        <p>No cars configured. Add one under Settings → Devices & services → Car Usage Tracker.</p></div>`;
      return;
    }

    const car = this._car;
    const drivers = car.drivers || [];
    const trips = car.trips || [];
    const totals = car.totals || { drivers: {}, total_km: 0, total_kwh: 0, unassigned_km: 0, consumption: null };
    const totalDrivers = totals.drivers || {};
    const hasOpen = !!(car.open_trip && car.open_trip.end_km != null && car.open_trip.start_km != null);

    const tabs = this._cars
      .map(
        (c) => `<button class="tab ${c.entry_id === this._selected ? "active" : ""}"
        data-car="${this._esc(c.entry_id)}">${this._esc(c.name)}</button>`
      )
      .join("");

    const driverCards = drivers
      .map((d) => {
        const v = totalDrivers[d] || { km: 0, kwh: 0, consumption: null };
        const extra = car.has_battery
          ? `<div class="sub">${v.kwh} kWh${v.consumption != null ? ` · ${v.consumption} kWh/100 km` : ""}</div>`
          : "";
        return `<div class="card">
          <div class="label">${this._esc(d)}</div>
          <div class="big">${v.km} km</div>
          ${extra}
        </div>`;
      })
      .join("");

    const rows = trips
      .map((t) => {
        const tripDrivers = t.drivers || [];
        const chips = drivers
          .map(
            (d) => `<button class="chip ${tripDrivers.includes(d) ? "on" : ""}"
              data-trip="${this._esc(t.id)}" data-driver="${this._esc(d)}">${this._esc(d)}</button>`
          )
          .join("");
        const dt = this._fmtDate(t.start);
        const selected = this._selectedTrips.has(t.id);
        return `<tr class="${tripDrivers.length ? "" : "unassigned"} ${selected ? "selected" : ""}">
          <td class="select-cell"><input type="checkbox" class="trip-select"
              data-trip="${this._esc(t.id)}" ${selected ? "checked" : ""}></td>
          <td class="when">
            <div class="date">${this._esc(dt.date)}</div>
            <div class="time">${this._esc(dt.time)}</div>
          </td>
          <td>${t.distance} km</td>
          ${this._consumptionCell(car, t)}
          <td class="chips">${chips}</td>
          <td class="actions"><button class="del" data-del="${this._esc(t.id)}" title="Delete">×</button></td>
        </tr>`;
      })
      .join("");

    const open = hasOpen
      ? `<div class="open"><span class="open-label">Trip in progress: ${car.open_trip.end_km - car.open_trip.start_km} km</span>
          <button class="end-trip" data-end>End trip now</button></div>`
      : "";

    const totalExtra = car.has_battery
      ? `<div class="sub">${totals.total_kwh} kWh${totals.consumption != null ? ` · ${totals.consumption} kWh/100 km` : ""}</div>`
      : "";

    const selectionCount = this._selectedTrips.size;
    const mergeBar = selectionCount > 0
      ? `<div class="merge-bar">
          <span>${selectionCount} trip${selectionCount === 1 ? "" : "s"} selected</span>
          <button class="merge-btn" data-merge ${this._merging ? "disabled" : ""}>${this._merging ? "Merging…" : "Merge trips"}</button>
          <button class="merge-clear" data-clear>Clear</button>
        </div>`
      : "";

    root.innerHTML = `${this._style()}
      <div class="wrap">
        <h1>Car Usage</h1>
        <div class="tabs">${tabs}</div>
        ${open}
        ${mergeBar}
        <div class="cards">
          <div class="card total">
            <div class="label">Total</div>
            <div class="big">${totals.total_km} km</div>
            ${totalExtra}
          </div>
          ${driverCards}
          <div class="card ${totals.unassigned_km > 0 ? "warn" : ""}">
            <div class="label">Unassigned</div>
            <div class="big">${totals.unassigned_km} km</div>
          </div>
        </div>
        <h2>Trips</h2>
        <table>
          <thead><tr>
            <th></th><th>Start</th><th>Distance</th>
            ${car.has_battery ? "<th>Energy</th>" : ""}
            <th>Drivers</th><th></th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;

    root.querySelectorAll(".tab").forEach((b) =>
      b.addEventListener("click", () => {
        this._selected = b.dataset.car;
        this._selectedTrips.clear();
        this._render();
      })
    );
    root.querySelectorAll(".chip").forEach((b) =>
      b.addEventListener("click", () => {
        const trip = (this._car.trips || []).find((t) => t.id === b.dataset.trip);
        if (trip) this._toggleDriver(trip, b.dataset.driver);
      })
    );
    root.querySelectorAll(".del").forEach((b) =>
      b.addEventListener("click", () => {
        const trip = (this._car.trips || []).find((t) => t.id === b.dataset.del);
        if (trip) this._deleteTrip(trip);
      })
    );
    root.querySelectorAll(".trip-select").forEach((cb) =>
      cb.addEventListener("change", () => this._toggleTripSelection(cb.dataset.trip))
    );
    const endBtn = root.querySelector("[data-end]");
    if (endBtn) endBtn.addEventListener("click", () => this._endOpenTrip());
    const mergeBtn = root.querySelector("[data-merge]");
    if (mergeBtn) mergeBtn.addEventListener("click", () => this._mergeSelectedTrips());
    const clearBtn = root.querySelector("[data-clear]");
    if (clearBtn) clearBtn.addEventListener("click", () => this._clearTripSelection());
  }

  _style() {
    return `<style>
      :host { display:block; background:var(--primary-background-color); color:var(--primary-text-color); font-family:var(--paper-font-body1_-_font-family,sans-serif); }
      .wrap { max-width:1000px; margin:0 auto; padding:16px; }
      h1 { margin:0 0 12px; font-weight:400; }
      h2 { margin:24px 0 8px; font-weight:400; }
      .tabs { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:16px; }
      .tab { border:1px solid var(--divider-color); background:var(--card-background-color); color:inherit; padding:8px 16px; border-radius:18px; cursor:pointer; font-size:14px; }
      .tab.active { background:var(--primary-color); color:var(--text-primary-color,#fff); border-color:var(--primary-color); }
      .cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:12px; }
      .card { background:var(--card-background-color); border-radius:12px; padding:12px 16px; box-shadow:var(--ha-card-box-shadow,0 1px 3px rgba(0,0,0,.2)); }
      .card.total { border-left:4px solid var(--primary-color); }
      .card.warn { border-left:4px solid var(--warning-color,#ffa600); }
      .label { color:var(--secondary-text-color); font-size:13px; }
      .big { font-size:24px; margin-top:4px; }
      .sub { color:var(--secondary-text-color); font-size:12px; margin-top:2px; }
      .open { background:var(--card-background-color); border-left:4px solid var(--info-color,#039be5); padding:8px 12px; border-radius:8px; margin-bottom:12px; display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
      .open-label { flex:1 1 auto; }
      .end-trip { background:var(--primary-color); color:var(--text-primary-color,#fff); border:none; border-radius:14px; padding:6px 14px; cursor:pointer; font-size:13px; }
      .end-trip:hover { filter:brightness(1.1); }
      .merge-bar { background:var(--card-background-color); border:1px solid var(--primary-color); padding:8px 12px; border-radius:8px; margin-bottom:12px; display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
      .merge-btn { background:var(--primary-color); color:var(--text-primary-color,#fff); border:none; border-radius:14px; padding:6px 14px; cursor:pointer; font-size:13px; }
      .merge-btn[disabled] { opacity:0.6; cursor:wait; }
      .merge-clear { background:none; border:1px solid var(--divider-color); color:inherit; border-radius:14px; padding:6px 12px; cursor:pointer; font-size:13px; }
      table { width:100%; border-collapse:collapse; background:var(--card-background-color); border-radius:12px; overflow:hidden; }
      th, td { text-align:left; padding:10px 12px; border-bottom:1px solid var(--divider-color); font-size:14px; vertical-align:middle; }
      th { color:var(--secondary-text-color); font-weight:500; }
      th:last-child, td:last-child { width:1%; white-space:nowrap; text-align:right; }
      tbody tr:hover { background:var(--secondary-background-color,rgba(0,0,0,.04)); }
      tr.unselected td:first-child { border-left:4px solid var(--warning-color,#ffa600); }
      tr.selected { background:var(--secondary-background-color,rgba(0,0,0,.06)); }
      .when .date { font-weight:500; }
      .when .time { color:var(--secondary-text-color); font-size:12px; margin-top:2px; }
      small { color:var(--secondary-text-color); }
      .chips { display:flex; gap:6px; flex-wrap:wrap; }
      .chip { border:1px solid var(--divider-color); background:transparent; color:inherit; padding:4px 10px; border-radius:14px; cursor:pointer; font-size:13px; }
      .chip.on { background:var(--primary-color); color:var(--text-primary-color,#fff); border-color:var(--primary-color); }
      .del { background:none; border:none; color:var(--secondary-text-color); cursor:pointer; font-size:16px; padding:4px; line-height:1; display:inline-flex; align-items:center; justify-content:center; }
      .del:hover { color:var(--error-color,#db4437); }
      .select-cell { width:32px; text-align:center; }
      .actions { width:1%; white-space:nowrap; }
      /* mobile: stack date and time on two lines, no horizontal scroll */
      @media (max-width: 600px) {
        .wrap { padding:8px; }
        table { font-size:13px; }
        .when .date, .when .time { display:block; }
        .when .time { margin-top:0; }
        .cards { grid-template-columns:1fr 1fr; }
        .chips .chip { font-size:12px; padding:3px 8px; }
      }
    </style>`;
  }
}

customElements.define("car-usage-tracker-panel", CarUsageTrackerPanel);
