const VERSION = "1.1.0";
console.info(`%c CAR-USAGE-TRACKER-PANEL %c v${VERSION} `, "background:#039be5;color:#fff", "");
const STRINGS = {
  en: {
    title: "Car Usage", noCars: "No cars configured. Add one under Settings \u2192 Devices & services \u2192 Car Usage Tracker.",
    total: "Total", unassigned: "Unassigned", trips: "Trips", start: "Start", distance: "Distance",
    energy: "Energy (estimate)", drivers: "Drivers", noTrips: "No trips recorded yet.", tripProgress: "Trip in progress: {distance} km",
    timeframe: "Timeframe", last10: "Last 10", allTrips: "All trips", month: "Month", year: "Year", customRange: "Custom range", from: "From", to: "To", noMatchingTrips: "No trips match this timeframe.",
    delete: "Delete", deleteConfirm: "Delete this trip?", kwh: "kWh", per100: "kWh/100 km", lessBattery: "< 1 % battery", km: "km",
    endTrip: "End trip now", endTripConfirm: "End the current trip now?",
    merge: "Merge", mergeSelected: "Merge selected", clearSelection: "Clear",
    mergeConfirm: "Merge {count} trips into one? This cannot be undone.",
    mergeDisabledHint: "Select 2 or more trips of the same car to merge.",
    selectAll: "Select all",
  },
  de: {
    title: "Fahrzeugnutzung", noCars: "Keine Fahrzeuge konfiguriert. Hinzuf\u00fcgen unter Einstellungen \u2192 Ger\u00e4te & Dienste \u2192 Car Usage Tracker.",
    total: "Gesamt", unassigned: "Nicht zugeordnet", trips: "Fahrten", start: "Start", distance: "Strecke",
    energy: "Energie (Sch\u00e4tzung)", drivers: "Fahrer*innen", noTrips: "Noch keine Fahrten erfasst.", tripProgress: "Fahrt l\u00e4uft: {distance} km",
    timeframe: "Zeitraum", last10: "Letzte 10", allTrips: "Alle Fahrten", month: "Monat", year: "Jahr", customRange: "Benutzerdefiniert", from: "Von", to: "Bis", noMatchingTrips: "Keine Fahrten in diesem Zeitraum.",
    delete: "L\u00f6schen", deleteConfirm: "Diese Fahrt l\u00f6schen?", kwh: "kWh", per100: "kWh/100 km", lessBattery: "< 1 % Akku", km: "km",
    endTrip: "Fahrt beenden", endTripConfirm: "Aktuelle Fahrt jetzt beenden?",
    merge: "Zusammenf\u00fchren", mergeSelected: "Ausgew\u00e4hlte zusammenf\u00fchren", clearSelection: "Auswahl leeren",
    mergeConfirm: "{count} Fahrten zu einer zusammenf\u00fchren? Dies kann nicht r\u00fcckg\u00e4ngig gemacht werden.",
    mergeDisabledHint: "W\u00e4hle 2 oder mehr Fahrten desselben Autos zum Zusammenf\u00fchren.",
    selectAll: "Alle ausw\u00e4hlen",
  },
};

class CarUsageTrackerPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._cars = [];
    this._selected = null;
    this._unsub = null;
    this._loaded = false;
    this._hass = null;
    this._language = null;
    this._narrow = false;
    this._timeframe = "recent";
    const now = new Date();
    this._month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
    this._from = "";
    this._to = "";
    this._selectedTrips = new Set();
    this._merging = false;
  }

  set narrow(value) { this._narrow = Boolean(value); this._updateMenuButton(); }
  _updateMenuButton() {
    const button = this.shadowRoot && this.shadowRoot.querySelector("ha-menu-button");
    if (button) { button.hass = this._hass; button.narrow = this._narrow; }
  }
  set hass(hass) {
    const first = !this._hass;
    const lang = (hass.locale && hass.locale.language) || hass.language || "en";
    this._hass = hass;
    this._updateMenuButton();
    if (this._language !== lang) { this._language = lang; if (this._loaded) this._render(); }
    if (first) { this._load(); this._subscribe(); }
  }
  _t(key, params = {}) {
    const lang = String(this._language || "en").split("-")[0];
    const text = (STRINGS[lang] || STRINGS.en)[key] || STRINGS.en[key] || key;
    return text.replace(/\{(\w+)\}/g, (_, k) => this._esc(params[k] ?? ""));
  }
  disconnectedCallback() { if (this._unsub) { this._unsub(); this._unsub = null; } }
  async _subscribe() {
    try { this._unsub = await this._hass.connection.subscribeMessage(() => this._load(), { type: "car_usage_tracker/subscribe" }); }
    catch (e) { console.warn("Car Usage Tracker: live updates unavailable", e); }
  }
  async _load() {
    try {
      const res = await this._hass.callWS({ type: "car_usage_tracker/get_data" });
      this._cars = Array.isArray(res.cars) ? res.cars : [];
      if (!this._cars.find((c) => c.entry_id === this._selected)) {
        this._selected = this._cars.length ? this._cars[0].entry_id : null;
        this._selectedTrips = new Set();
      } else {
        // Drop selections that no longer exist after reload.
        const ids = new Set((this._car && this._car.trips || []).map((t) => t.id));
        this._selectedTrips = new Set(Array.from(this._selectedTrips).filter((id) => ids.has(id)));
      }
      this._loaded = true;
      this._render();
    } catch (e) { console.error("Car Usage Tracker: load failed", e); }
  }

  get _car() { return this._cars.find((c) => c.entry_id === this._selected); }

  async _toggleDriver(trip, driver) {
    const set = new Set(trip.drivers || []);
    if (set.has(driver)) set.delete(driver); else set.add(driver);
    await this._hass.callWS({ type: "car_usage_tracker/assign_drivers", entry_id: this._selected, trip_id: trip.id, drivers: Array.from(set) });
  }
  async _deleteTrip(trip) {
    if (!confirm(this._t("deleteConfirm"))) return;
    await this._hass.callWS({ type: "car_usage_tracker/delete_trip", entry_id: this._selected, trip_id: trip.id });
    this._selectedTrips.delete(trip.id);
  }
  async _endOpenTrip() {
    if (!confirm(this._t("endTripConfirm"))) return;
    try { await this._hass.callWS({ type: "car_usage_tracker/end_trip", entry_id: this._selected }); }
    catch (e) { alert("Could not end trip: " + (e && e.message ? e.message : e)); }
  }
  _toggleTripSelection(tripId) {
    if (this._selectedTrips.has(tripId)) this._selectedTrips.delete(tripId);
    else this._selectedTrips.add(tripId);
    this._render();
  }
  _clearTripSelection() { this._selectedTrips.clear(); this._render(); }
  _selectAllTrips() {
    const trips = (this._car && this._car.trips) || [];
    if (this._selectedTrips.size === trips.length && trips.length > 0) this._selectedTrips.clear();
    else this._selectedTrips = new Set(trips.map((t) => t.id));
    this._render();
  }
  async _mergeSelectedTrips() {
    const ids = Array.from(this._selectedTrips);
    if (ids.length < 2) return;
    const car = this._car;
    // Only merge trips that belong to the currently-selected car (same car).
    const validIds = ids.filter((id) => (car && car.trips || []).some((t) => t.id === id));
    if (validIds.length < 2) {
      alert(this._t("mergeDisabledHint"));
      return;
    }
    if (!confirm(this._t("mergeConfirm", { count: validIds.length }))) return;
    this._merging = true;
    this._render();
    try {
      await this._hass.callWS({ type: "car_usage_tracker/merge_trips", entry_id: this._selected, trip_ids: validIds });
      this._selectedTrips.clear();
    } catch (e) {
      alert("Could not merge trips: " + (e && e.message ? e.message : e));
    } finally {
      this._merging = false;
    }
  }

  _fmtDate(iso) {
    if (!iso) return "\u2013";
    return new Date(iso).toLocaleString(this._language || "en", { dateStyle: "short", timeStyle: "short" });
  }
  _num(value) { return Number(value).toLocaleString(this._language || "en", { maximumFractionDigits: 1 }); }
  _esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => "&#" + c.charCodeAt(0) + ";"); }
  _filteredTrips(trips) {
    if (this._timeframe === "recent") return trips.slice(0, 10);
    if (this._timeframe === "all") return trips;
    return trips.filter((t) => {
      const date = new Date(t.start);
      if (Number.isNaN(date.getTime())) return false;
      if (this._timeframe === "month") return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}` === this._month;
      const day = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
      return (!this._from || day >= this._from) && (!this._to || day <= this._to);
    });
  }
  _totalsFor(trips, drivers) {
    const values = Object.fromEntries(drivers.map((d) => [d, { km: 0, kwh: 0, kwhKm: 0, trips: 0 }]));
    let totalKm = 0, totalKwh = 0, kwhKm = 0, unassignedKm = 0;
    for (const trip of trips) {
      const distance = Number(trip.distance) || 0;
      totalKm += distance;
      const hasEnergy = trip.energy_kwh != null && Number.isFinite(Number(trip.energy_kwh));
      const energy = hasEnergy ? Number(trip.energy_kwh) : 0;
      if (hasEnergy) { totalKwh += energy; kwhKm += distance; }
      const assigned = (trip.drivers || []).filter((d) => values[d]);
      if (!assigned.length) { unassignedKm += distance; continue; }
      const share = 1 / assigned.length;
      for (const driver of assigned) {
        values[driver].km += distance * share;
        values[driver].trips += share;
        if (hasEnergy) {
          values[driver].kwh += energy * share;
          values[driver].kwhKm += distance * share;
        }
      }
    }
    const average = (kwh, km) => km > 0 && kwh > 0 ? Math.round(kwh / km * 1000) / 10 : null;
    return {
      drivers: Object.fromEntries(Object.entries(values).map(([name, value]) => [name, {
        km: Math.round(value.km * 10) / 10,
        kwh: Math.round(value.kwh * 10) / 10,
        trips: Math.round(value.trips * 100) / 100,
        consumption: average(value.kwh, value.kwhKm),
      }])),
      unassigned_km: Math.round(unassignedKm * 10) / 10,
      total_km: Math.round(totalKm * 10) / 10,
      total_kwh: Math.round(totalKwh * 10) / 10,
      consumption: average(totalKwh, kwhKm),
    };
  }
  _consumptionCell(car, t) {
    if (!car.has_battery) return "";
    if (t.consumption != null) return `<td>${this._num(t.energy_kwh)} ${this._t("kwh")}<br><small>${this._num(t.consumption)} ${this._t("per100")}</small></td>`;
    if (t.low_resolution) return `<td><small>${this._t("lessBattery")}</small></td>`;
    return "<td>\u2013</td>";
  }
  _monthControls(allTrips) {
    if (this._timeframe !== "month") return "";
    const [selYear, selMonth] = this._month.split("-");
    const years = new Set(allTrips.map((t) => new Date(t.start).getFullYear()).filter((y) => !Number.isNaN(y)));
    years.add(new Date().getFullYear());
    years.add(Number(selYear));
    const yearOptions = [...years].sort((a, b) => b - a).map((y) => `<option value="${y}" ${String(y) === selYear ? "selected" : ""}>${y}</option>`).join("");
    const monthOptions = Array.from({ length: 12 }, (_, i) => {
      const v = String(i + 1).padStart(2, "0");
      const name = new Date(2000, i, 1).toLocaleString(this._language || "en", { month: "long" });
      return `<option value="${v}" ${v === selMonth ? "selected" : ""}>${this._esc(name)}</option>`;
    }).join("");
    return `<label>${this._t("month")}<select class="month-select">${monthOptions}</select></label><label>${this._t("year")}<select class="year-select">${yearOptions}</select></label>`;
  }

  _render() {
    const root = this.shadowRoot;
    if (!this._loaded) return;
    if (!root.querySelector(".panel-header")) {
      root.innerHTML = `<style>.panel-header{height:56px;display:flex;align-items:center;background:var(--app-header-background-color,var(--primary-color));color:var(--app-header-text-color,white);padding:0 16px;box-sizing:border-box}.panel-header ha-menu-button{margin:0 8px 0 -8px}.panel-header .title{font-size:20px;font-weight:400}</style><div class="panel-header"><ha-menu-button></ha-menu-button><div class="title"></div></div><div class="panel-content"></div>`;
    }
    root.querySelector(".panel-header .title").textContent = this._t("title");
    this._updateMenuButton();
    const content = root.querySelector(".panel-content");
    if (!this._cars.length) {
      content.innerHTML = `${this._style()}<div class="wrap"><p>${this._t("noCars")}</p></div>`;
      return;
    }
    const car = this._car, drivers = car.drivers || [], allTrips = car.trips || [], trips = this._filteredTrips(allTrips), totals = this._totalsFor(trips, drivers), totalDrivers = totals.drivers || {};
    const hasOpen = !!(car.open_trip && car.open_trip.end_km != null && car.open_trip.start_km != null);

    const tabs = this._cars.map((c) => `<button class="tab ${c.entry_id === this._selected ? "active" : ""}" data-car="${this._esc(c.entry_id)}">${this._esc(c.name)}</button>`).join("");
    const driverCards = drivers.map((d) => {
      const v = totalDrivers[d] || { km: 0, kwh: 0, consumption: null };
      const extra = car.has_battery ? `<div class="sub">${this._num(v.kwh)} ${this._t("kwh")}${v.consumption != null ? ` \u00b7 ${this._num(v.consumption)} ${this._t("per100")}` : ""}</div>` : "";
      return `<div class="card"><div class="label">${this._esc(d)}</div><div class="big">${this._num(v.km)} ${this._t("km")}</div>${extra}</div>`;
    }).join("");

    const sel = this._selectedTrips;
    const canMerge = sel.size >= 2 && !this._merging;
    const mergeBar = canMerge
      ? `<div class="merge-bar"><span class="sel-count">${sel.size} selected</span>
           <button class="merge-btn" data-merge>${this._t("mergeSelected")}</button>
           <button class="clear-btn" data-clear>${this._t("clearSelection")}</button>
         </div>`
      : (sel.size > 0 ? `<div class="merge-bar"><span class="sel-count">${sel.size} selected</span><button class="clear-btn" data-clear>${this._t("clearSelection")}</button><span class="hint">${this._t("mergeDisabledHint")}</span></div>` : "");

    const rows = trips.map((t) => {
      const tripDrivers = t.drivers || [];
      const chips = drivers.map((d) => `<button class="chip ${tripDrivers.includes(d) ? "on" : ""}" data-trip="${this._esc(t.id)}" data-driver="${this._esc(d)}">${this._esc(d)}</button>`).join("");
      const checked = sel.has(t.id) ? "checked" : "";
      return `<tr class="${tripDrivers.length ? "" : "unassigned"} ${checked ? "selected" : ""}">
        <td class="select-cell"><input type="checkbox" class="row-select" data-select="${this._esc(t.id)}" ${checked}></td>
        <td>${this._fmtDate(t.start)}</td>
        <td>${this._num(t.distance)} ${this._t("km")}</td>
        ${this._consumptionCell(car, t)}
        <td><div class="chips">${chips}</div></td>
        <td class="actions"><button class="del" data-del="${this._esc(t.id)}" title="${this._t("delete")}">\u2715</button></td>
      </tr>`;
    }).join("");

    const open = hasOpen
      ? `<div class="open"><span class="open-label">${this._t("tripProgress", { distance: this._num(car.open_trip.end_km - car.open_trip.start_km) })}</span><button class="end-trip" data-end>${this._t("endTrip")}</button></div>`
      : "";

    const totalExtra = car.has_battery ? `<div class="sub">${this._num(totals.total_kwh)} ${this._t("kwh")}${totals.consumption != null ? ` \u00b7 ${this._num(totals.consumption)} ${this._t("per100")}` : ""}</div>` : "";
    const monthControl = this._monthControls(allTrips), rangeControls = this._timeframe === "custom" ? `<label>${this._t("from")}<input type="date" class="from-filter" value="${this._esc(this._from)}"></label><label>${this._t("to")}<input type="date" class="to-filter" value="${this._esc(this._to)}"></label>` : "";
    const filter = `<div class="filters"><label>${this._t("timeframe")}<select class="timeframe"><option value="recent" ${this._timeframe === "recent" ? "selected" : ""}>${this._t("last10")}</option><option value="all" ${this._timeframe === "all" ? "selected" : ""}>${this._t("allTrips")}</option><option value="month" ${this._timeframe === "month" ? "selected" : ""}>${this._t("month")}</option><option value="custom" ${this._timeframe === "custom" ? "selected" : ""}>${this._t("customRange")}</option></select></label>${monthControl}${rangeControls}</div>`;
    const selectAllLabel = this._t("selectAll");
    content.innerHTML = `${this._style()}<div class="wrap"><div class="tabs">${tabs}</div>${filter}${open}${mergeBar}<div class="cards"><div class="card total"><div class="label">${this._t("total")}</div><div class="big">${this._num(totals.total_km)} ${this._t("km")}</div>${totalExtra}</div>${driverCards}<div class="card ${totals.unassigned_km > 0 ? "warn" : ""}"><div class="label">${this._t("unassigned")}</div><div class="big">${this._num(totals.unassigned_km)} ${this._t("km")}</div></div></div><h2>${this._t("trips")}</h2><div class="table-wrap"><table><thead><tr><th class="select-cell"><input type="checkbox" class="select-all" ${allTrips.length && sel.size === allTrips.length ? "checked" : ""} title="${selectAllLabel}"></th><th>${this._t("start")}</th><th>${this._t("distance")}</th>${car.has_battery ? `<th>${this._t("energy")}</th>` : ""}<th>${this._t("drivers")}</th><th></th></tr></thead><tbody>${rows || `<tr><td colspan="${car.has_battery ? 6 : 5}">${allTrips.length ? this._t("noMatchingTrips") : this._t("noTrips")}</td></tr>`}</tbody></table></div></div>`;
    content.querySelector(".timeframe").addEventListener("change", (e) => { this._timeframe = e.target.value; this._render(); });
    const monthSel = content.querySelector(".month-select"), yearSel = content.querySelector(".year-select");
    const updateMonth = () => { this._month = `${yearSel.value}-${monthSel.value}`; this._render(); };
    if (monthSel) monthSel.addEventListener("change", updateMonth);
    if (yearSel) yearSel.addEventListener("change", updateMonth);
    const fromInput = content.querySelector(".from-filter"), toInput = content.querySelector(".to-filter");
    if (fromInput) fromInput.addEventListener("change", (e) => { this._from = e.target.value; this._render(); });
    if (toInput) toInput.addEventListener("change", (e) => { this._to = e.target.value; this._render(); });
    content.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => { this._selected = b.dataset.car; this._selectedTrips.clear(); this._render(); }));
    content.querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => { const trip = (this._car.trips || []).find((t) => t.id === b.dataset.trip); if (trip) this._toggleDriver(trip, b.dataset.driver); }));
    content.querySelectorAll(".del").forEach((b) => b.addEventListener("click", () => { const trip = (this._car.trips || []).find((t) => t.id === b.dataset.del); if (trip) this._deleteTrip(trip); }));
    content.querySelectorAll(".row-select").forEach((b) => b.addEventListener("change", () => this._toggleTripSelection(b.dataset.select)));
    const sa = content.querySelector(".select-all");
    if (sa) sa.addEventListener("change", () => this._selectAllTrips());
    const mb = content.querySelector("[data-merge]");
    if (mb) mb.addEventListener("click", () => this._mergeSelectedTrips());
    const cl = content.querySelector("[data-clear]");
    if (cl) cl.addEventListener("click", () => this._clearTripSelection());
    const endBtn = content.querySelector("[data-end]");
    if (endBtn) endBtn.addEventListener("click", () => this._endOpenTrip());
  }

  _style() {
    return `<style>:host{display:block;background:var(--primary-background-color);color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,sans-serif)}.wrap{max-width:1000px;margin:0 auto;padding:16px}h1{margin:0 0 12px;font-weight:400}h2{margin:24px 0 8px;font-weight:400}.tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}.tab{border:1px solid var(--divider-color);background:var(--card-background-color);color:inherit;padding:8px 16px;border-radius:18px;cursor:pointer;font-size:14px}.tab.active{background:var(--primary-color);color:var(--text-primary-color,#fff);border-color:var(--primary-color)}.filters{display:flex;align-items:end;gap:16px;flex-wrap:wrap;margin:8px 0 16px}.filters label{display:grid;gap:6px;color:var(--secondary-text-color);font-size:13px}.filters select,.filters input{min-height:36px;padding:6px 10px;font-size:14px;border:1px solid var(--divider-color);border-radius:8px;background:var(--card-background-color);color:var(--primary-text-color);font-family:inherit;box-sizing:border-box}.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}.card{background:var(--card-background-color);border-radius:12px;padding:12px 16px;box-shadow:var(--ha-card-box-shadow,0 1px 3px rgba(0,0,0,.2))}.card.total{border-left:4px solid var(--primary-color)}.card.warn{border-left:4px solid var(--warning-color,#ffa600)}.label{color:var(--secondary-text-color);font-size:13px}.big{font-size:24px;margin-top:4px}.sub{color:var(--secondary-text-color);font-size:12px;margin-top:2px}.table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}.open{display:flex;align-items:center;gap:12px;background:var(--card-background-color);border-left:4px solid var(--info-color,#039be5);padding:8px 12px;border-radius:8px;margin-bottom:12px}.open-label{flex:1 1 auto}.end-trip{border:1px solid var(--primary-color);background:var(--primary-color);color:var(--text-primary-color,#fff);padding:6px 12px;border-radius:14px;cursor:pointer;font-size:13px}.end-trip:hover{filter:brightness(1.1)}.merge-bar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;background:var(--card-background-color);border:1px solid var(--primary-color);padding:8px 12px;border-radius:8px;margin-bottom:12px}.sel-count{font-weight:500}.merge-btn,.clear-btn{border:1px solid var(--divider-color);background:var(--primary-color);color:var(--text-primary-color,#fff);border-color:var(--primary-color);padding:6px 12px;border-radius:14px;cursor:pointer;font-size:13px}.clear-btn{background:transparent;color:var(--primary-text-color)}.merge-btn:hover,.clear-btn:hover{filter:brightness(1.05)}.hint{color:var(--secondary-text-color);font-size:12px}table{width:100%;min-width:640px;border-collapse:collapse;background:var(--card-background-color);border-radius:12px;overflow:hidden}th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--divider-color);font-size:14px;vertical-align:middle}th{color:var(--secondary-text-color);font-weight:500}th:last-child,td:last-child{width:1%;white-space:nowrap;text-align:right}th.select-cell,td.select-cell{width:32px;text-align:center;vertical-align:middle}tbody tr:hover{background:var(--secondary-background-color, rgba(0,0,0,.04))}tr.selected td{background:var(--primary-color, #03a9f4);color:var(--text-primary-color,#fff)}tr.unassigned td:nth-child(2){border-left:4px solid var(--warning-color,#ffa600)}small{color:var(--secondary-text-color)}.chips{display:flex;gap:6px;flex-wrap:wrap}.chip{border:1px solid var(--divider-color);background:transparent;color:inherit;padding:4px 10px;border-radius:14px;cursor:pointer;font-size:13px}.chip.on{background:var(--primary-color);color:var(--text-primary-color,#fff);border-color:var(--primary-color)}.del{background:none;border:none;color:var(--secondary-text-color);cursor:pointer;font-size:16px;padding:4px;line-height:1;display:inline-flex;align-items:center;justify-content:center;vertical-align:middle}.del:hover{color:var(--error-color,#db4437)}@media (max-width:600px){.wrap{padding:8px}.table-wrap table{font-size:13px;min-width:0}.table-wrap table thead{display:none}.table-wrap table,.table-wrap table tbody,.table-wrap table tr,.table-wrap table td{display:block;width:100%}.table-wrap table tr{margin-bottom:12px;border:1px solid var(--divider-color);border-radius:12px;padding:8px;background:var(--card-background-color)}.table-wrap table td{padding:6px 8px;border-bottom:1px solid var(--divider-color);text-align:left;display:flex;align-items:center;justify-content:space-between;gap:8px}.table-wrap table td:last-child{border-bottom:none;text-align:right;justify-content:flex-end}.table-wrap table td.actions{justify-content:flex-end}.table-wrap table td.select-cell{justify-content:flex-start}.cards{grid-template-columns:1fr 1fr}.filter-row{flex-direction:column;align-items:stretch}}
    </style>`;
  }
}

customElements.define("car-usage-tracker-panel", CarUsageTrackerPanel);
