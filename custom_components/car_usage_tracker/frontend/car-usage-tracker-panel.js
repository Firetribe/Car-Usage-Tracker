class CarUsageTrackerPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._cars = [];
    this._selected = null;
    this._unsub = null;
    this._loaded = false;
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
      this._cars = res.cars;
      if (!this._cars.find((c) => c.entry_id === this._selected)) {
        this._selected = this._cars.length ? this._cars[0].entry_id : null;
      }
      this._loaded = true;
      this._render();
    } catch (e) {
      console.error("Car Usage Tracker: load failed", e);
    }
  }

  get _car() {
    return this._cars.find((c) => c.entry_id === this._selected);
  }

  async _toggleDriver(trip, driver) {
    const set = new Set(trip.drivers);
    set.has(driver) ? set.delete(driver) : set.add(driver);
    await this._hass.callWS({
      type: "car_usage_tracker/assign_drivers",
      entry_id: this._selected,
      trip_id: trip.id,
      drivers: [...set],
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

  _fmtDate(iso) {
    if (!iso) return "–";
    return new Date(iso).toLocaleString(this._hass?.locale?.language, {
      dateStyle: "short",
      timeStyle: "short",
    });
  }

  _esc(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&", "<": "<", ">": ">", '"': """, "'": "'",
    }[c]));
  }

  _consumptionCell(car, t) {
    if (!car.has_battery) return "";
    if (t.consumption != null) {
      return `<td>${t.energy_kwh} kWh<br><small>${t.consumption} kWh/100 km</small></td>`;
    }
    if (t.low_resolution) return `<td><small>< 1 % battery</small></td>`;
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
    const tabs = this._cars
      .map((c) => `<button class="tab ${c.entry_id === this._selected ? "active" : ""}"
        data-car="${c.entry_id}">${this._esc(c.name)}</button>`)
      .join("");

    const totals = car.totals;
    const driverCards = car.drivers
      .map((d) => {
        const v = totals.drivers[d] || { km: 0, kwh: 0, consumption: null };
        return `<div class="card">
          <div class="label">${this._esc(d)}</div>
          <div class="big">${v.km} km</div>
          ${car.has_battery ? `<div class="sub">${v.kwh} kWh${
            v.consumption != null ? ` · ${v.consumption} kWh/100 km` : ""}</div>` : ""}
        </div>`;
      })
      .join("");

    const rows = car.trips
      .map((t) => {
        const chips = car.drivers
          .map((d) => `<button class="chip ${t.drivers.includes(d) ? "on" : ""}"
            data-trip="${t.id}" data-driver="${this._esc(d)}">${this._esc(d)}</button>`)
          .join("");
        return `<tr class="${t.drivers.length ? "" : "unassigned"}">
          <td>${this._fmtDate(t.start)}</td>
          <td>${t.distance} km</td>
          ${this._consumptionCell(car, t)}
          <td class="chips">${chips}</td>
          <td><button class="del" data-del="${t.id}" title="Delete">✕</button></td>
        </tr>`;
      })
      .join("");

    const open = car.open_trip && car.open_trip.end_km != null
      ? `<div class="open">Trip in progress: ${
          (car.open_trip.end_km - car.open_trip.start_km).toFixed(1)} km</div>`
      : "";

    root.innerHTML = `${this._style()}
      <div class="wrap">
        <h1>Car Usage</h1>
        <div class="tabs">${tabs}</div>
        ${open}
        <div class="cards">
          <div class="card total">
            <div class="label">Total</div>
            <div class="big">${totals.total_km} km</div>
            ${car.has_battery ? `<div class="sub">${totals.total_kwh} kWh${
              totals.consumption != null ? ` · ${totals.consumption} kWh/100 km` : ""}</div>` : ""}
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
            <th>Start</th><th>Distance</th>
            ${car.has_battery ? "<th>Energy (estimate)</th>" : ""}
            <th>Drivers</th><th></th>
          </tr></thead>
          <tbody>${rows || `<tr><td colspan="5">No trips recorded yet.</td></tr>`}</tbody>
        </table>
      </div>`;

    root.querySelectorAll(".tab").forEach((b) =>
      b.addEventListener("click", () => { this._selected = b.dataset.car; this._render(); }));
    root.querySelectorAll(".chip").forEach((b) =>
      b.addEventListener("click", () => {
        const trip = this._car.trips.find((t) => t.id === b.dataset.trip);
        this._toggleDriver(trip, b.dataset.driver);
      }));
    root.querySelectorAll(".del").forEach((b) =>
      b.addEventListener("click", () => {
        const trip = this._car.trips.find((t) => t.id === b.dataset.del);
        this._deleteTrip(trip);
      }));
  }

  _style() {
    return `<style>
      :host { display:block; background:var(--primary-background-color); color:var(--primary-text-color);
              font-family:var(--paper-font-body1_-_font-family, sans-serif); }
      .wrap { max-width:1000px; margin:0 auto; padding:16px; }
      h1 { margin:0 0 12px; font-weight:400; }
      h2 { margin:24px 0 8px; font-weight:400; }
      .tabs { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:16px; }
      .tab { border:1px solid var(--divider-color); background:var(--card-background-color);
             color:inherit; padding:8px 16px; border-radius:18px; cursor:pointer; font-size:14px; }
      .tab.active { background:var(--primary-color); color:var(--text-primary-color,#fff); border-color:var(--primary-color); }
      .cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:12px; }
      .card { background:var(--card-background-color); border-radius:12px; padding:12px 16px;
              box-shadow:var(--ha-card-box-shadow,0 1px 3px rgba(0,0,0,.2)); }
      .card.total { border-left:4px solid var(--primary-color); }
      .card.warn { border-left:4px solid var(--warning-color,#ffa600); }
      .label { color:var(--secondary-text-color); font-size:13px; }
      .big { font-size:24px; margin-top:4px; }
      .sub { color:var(--secondary-text-color); font-size:12px; margin-top:2px; }
      .open { background:var(--card-background-color); border-left:4px solid var(--info-color,#039be5);
              padding:8px 12px; border-radius:8px; margin-bottom:12px; }
      table { width:100%; border-collapse:collapse; background:var(--card-background-color);
              border-radius:12px; overflow:hidden; }
      th, td { text-align:left; padding:10px 12px; border-bottom:1px solid var(--divider-color); font-size:14px; vertical-align:middle; }
      th { color:var(--secondary-text-color); font-weight:500; }
      tr.unassigned td:first-child { border-left:4px solid var(--warning-color,#ffa600); }
      small { color:var(--secondary-text-color); }
      .chips { display:flex; gap:6px; flex-wrap:wrap; }
      .chip { border:1px solid var(--divider-color); background:transparent; color:inherit;
              padding:4px 10px; border-radius:14px; cursor:pointer; font-size:13px; }
      .chip.on { background:var(--primary-color); color:var(--text-primary-color,#fff); border-color:var(--primary-color); }
      .del { background:none; border:none; color:var(--secondary-text-color); cursor:pointer; font-size:16px; }
      .del:hover { color:var(--error-color,#db4437); }
    </style>`;
  }
}

customElements.define("car-usage-tracker-panel", CarUsageTrackerPanel);