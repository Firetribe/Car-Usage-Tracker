class CarUsageTrackerPanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._data = null;
    this._unsub = null;
    this._subscribing = false;
    this._filter = "all"; // all | unassigned
    this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._render();
      this._subscribe();
    }
  }

  set narrow(v) { this._narrow = v; }
  set panel(v) { this._panel = v; }

  connectedCallback() {
    if (this._hass && !this._unsub) this._subscribe();
  }

  disconnectedCallback() {
    if (this._unsub) {
      this._unsub();
      this._unsub = null;
    }
  }

  async _subscribe() {
    if (this._unsub || this._subscribing || !this._hass) return;
    this._subscribing = true;
    try {
      this._unsub = await this._hass.connection.subscribeMessage(
        (data) => {
          this._data = data;
          this._render();
        },
        { type: "car_usage_tracker/subscribe" }
      );
    } catch (e) {
      this._error = e.message || String(e);
      this._render();
    } finally {
      this._subscribing = false;
    }
  }

  async _toggleDriver(trip, driver, checked) {
    let drivers = new Set(trip.drivers);
    checked ? drivers.add(driver) : drivers.delete(driver);
    try {
      await this._hass.callWS({
        type: "car_usage_tracker/assign",
        trip_id: trip.id,
        drivers: [...drivers],
      });
    } catch (e) {
      alert("Could not save: " + (e.message || e));
    }
  }

  async _deleteTrip(trip) {
    if (!confirm(`Delete trip of ${trip.distance.toFixed(1)} km?`)) return;
    try {
      await this._hass.callWS({
        type: "car_usage_tracker/delete",
        trip_id: trip.id,
      });
    } catch (e) {
      alert("Could not delete: " + (e.message || e));
    }
  }

  _fmtDate(iso) {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  }

  _render() {
    const root = this.shadowRoot;
    const d = this._data;

    const style = `
      <style>
        :host { display: block; background: var(--primary-background-color); min-height: 100vh; }
        .wrap { max-width: 1000px; margin: 0 auto; padding: 16px; font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif); color: var(--primary-text-color); }
        h1 { font-weight: 400; margin: 8px 0 16px; }
        .totals { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 24px; }
        .card { background: var(--card-background-color); border-radius: 12px; padding: 14px 16px; box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,.2)); }
        .card .name { color: var(--secondary-text-color); font-size: 0.9em; }
        .card .value { font-size: 1.6em; margin-top: 4px; }
        .card.warn .value { color: var(--warning-color, orange); }
        .toolbar { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; }
        button.chip { border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); border-radius: 16px; padding: 6px 14px; cursor: pointer; }
        button.chip.active { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: var(--primary-color); }
        table { width: 100%; border-collapse: collapse; background: var(--card-background-color); border-radius: 12px; overflow: hidden; }
        th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--divider-color); }
        th { color: var(--secondary-text-color); font-weight: 500; font-size: 0.85em; }
        td.num { text-align: right; white-space: nowrap; }
        label.drv { display: inline-flex; align-items: center; gap: 4px; margin-right: 12px; cursor: pointer; white-space: nowrap; }
        button.del { background: none; border: none; cursor: pointer; color: var(--secondary-text-color); font-size: 1.1em; }
        .badge { display: inline-block; background: var(--warning-color, orange); color: #fff; border-radius: 8px; padding: 1px 8px; font-size: 0.8em; margin-left: 6px; }
        .empty, .err { padding: 24px; text-align: center; color: var(--secondary-text-color); }
        .err { color: var(--error-color, red); }
        .open { margin-bottom: 16px; padding: 10px 14px; border-radius: 12px; background: var(--card-background-color); border-left: 4px solid var(--primary-color); }
      </style>`;

    if (this._error) {
      root.innerHTML = `${style}<div class="wrap"><div class="err">${this._error}</div></div>`;
      return;
    }
    if (!d) {
      root.innerHTML = `${style}<div class="wrap"><div class="empty">Loading…</div></div>`;
      return;
    }

    const totalsHtml = d.drivers.map((name) => `
      <div class="card">
        <div class="name">${name}</div>
        <div class="value">${(d.totals[name] ?? 0).toFixed(1)} km</div>
      </div>`).join("");

    const unassignedHtml = `
      <div class="card warn">
        <div class="name">Unassigned</div>
        <div class="value">${d.unassigned.toFixed(1)} km</div>
      </div>`;

    const trips = d.trips.filter(
      (t) => this._filter === "all" || t.drivers.length === 0
    );

    let openHtml = "";
    if (d.open_trip) {
      const km = d.open_trip.end_odometer - d.open_trip.start_odometer;
      openHtml = `<div class="open">Trip in progress: ${km.toFixed(1)} km so far (started ${this._fmtDate(d.open_trip.start)})</div>`;
    }

    const rows = trips.map((t) => {
      const boxes = d.drivers.map((name) => `
        <label class="drv">
          <input type="checkbox" data-trip="${t.id}" data-driver="${name}"
            ${t.drivers.includes(name) ? "checked" : ""}>
          ${name}
        </label>`).join("");
      const share = t.drivers.length > 1
        ? `<span class="badge">${(t.distance / t.drivers.length).toFixed(1)} km each</span>` : "";
      return `
        <tr>
          <td>${this._fmtDate(t.start)}</td>
          <td class="num">${t.distance.toFixed(1)} km${share}</td>
          <td>${boxes}</td>
          <td><button class="del" data-del="${t.id}" title="Delete trip">🗑</button></td>
        </tr>`;
    }).join("");

    root.innerHTML = `
      ${style}
      <div class="wrap">
        <h1>Car Usage</h1>
        <div class="totals">${totalsHtml}${unassignedHtml}</div>
        ${openHtml}
        <div class="toolbar">
          <button class="chip ${this._filter === "all" ? "active" : ""}" data-filter="all">All trips</button>
          <button class="chip ${this._filter === "unassigned" ? "active" : ""}" data-filter="unassigned">Unassigned only</button>
        </div>
        ${trips.length ? `
        <table>
          <thead><tr><th>Start</th><th style="text-align:right">Distance</th><th>Drivers</th><th></th></tr></thead>
          <tbody>${rows}</tbody>
        </table>` : `<div class="empty">No trips yet.</div>`}
      </div>`;

    root.querySelectorAll("input[type=checkbox]").forEach((cb) => {
      cb.addEventListener("change", () => {
        const trip = this._data.trips.find((t) => t.id === cb.dataset.trip);
        if (trip) this._toggleDriver(trip, cb.dataset.driver, cb.checked);
      });
    });
    root.querySelectorAll("button[data-del]").forEach((b) => {
      b.addEventListener("click", () => {
        const trip = this._data.trips.find((t) => t.id === b.dataset.del);
        if (trip) this._deleteTrip(trip);
      });
    });
    root.querySelectorAll("button[data-filter]").forEach((b) => {
      b.addEventListener("click", () => {
        this._filter = b.dataset.filter;
        this._render();
      });
    });
  }
}

customElements.define("car-usage-tracker-panel", CarUsageTrackerPanel);