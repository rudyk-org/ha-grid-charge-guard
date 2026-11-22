/** Grid Charge Guard v0.2.0 - bundled Home Assistant Lovelace card. */
class GridChargeGuardCard extends HTMLElement {
  static getStubConfig() { return { type: "custom:grid-charge-guard-card" }; }
  static getConfigForm() {
    return {
      schema: [
        { name: "switch_entity", selector: { entity: { domain: "switch" } } },
        { name: "max_entity", selector: { entity: { domain: "number" } } },
        { name: "target_entity", selector: { entity: { domain: "sensor" } } },
        { name: "mode_entity", selector: { entity: { domain: "sensor" } } },
        { name: "losses_entity", selector: { entity: { domain: "sensor" } } },
        { name: "last_event_entity", selector: { entity: { domain: "sensor" } } },
        { name: "actual_entity", selector: { entity: { domain: "number" } } },
        { name: "voltage_entity", selector: { entity: { domain: "sensor" } } },
      ],
    };
  }
  setConfig(config) {
    if (!config) throw Error("Missing card configuration");
    this.config = {
      switch_entity: "switch.adaptive_ac_charging",
      max_entity: "number.allowed_ac_charge_current",
      target_entity: "sensor.adaptive_target_current",
      mode_entity: "sensor.grid_charge_mode",
      losses_entity: "sensor.grid_losses_15m",
      last_event_entity: "sensor.grid_charge_last_event",
      ...config,
    };
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this.render();
  }
  set hass(hass) { this._hass = hass; this.render(); }
  getCardSize() { return 5; }
  escape(s) {
    return String(s ?? "—").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  }
  state(id) { return id ? this._hass?.states?.[id] : undefined; }
  value(id, fallback="—") {
    const v = this.state(id)?.state;
    return v && v !== "unknown" && v !== "unavailable" ? v : fallback;
  }
  showMoreInfo(id) {
    if (id) this.dispatchEvent(new CustomEvent("hass-more-info", {
      detail: { entityId: id }, bubbles: true, composed: true,
    }));
  }
  render() {
    if (!this.shadowRoot || !this._hass || !this.config) return;
    const c = this.config;
    const enabled = this.value(c.switch_entity) === "on";
    const mode = this.value(c.mode_entity);
    const target = this.value(c.target_entity);
    const max = this.value(c.max_entity);
    const losses = this.value(c.losses_entity);
    const actual = this.value(c.actual_entity);
    const voltage = this.value(c.voltage_entity);
    const last = this.state(c.last_event_entity);
    const lastMsg = last?.attributes?.message || "Очікуємо першої події регулятора";
    const lastAt = last?.attributes?.time || "";
    const warning = ["critical_derate", "derated", "low_voltage", "grid_outage"].includes(mode);
    const failure = ["voltage_unavailable", "voltage_stale", "write_failed",
      "current_unavailable", "invalid_current_limits"].includes(mode);
    const modeLabel = {
      normal: "Мережа стабільна", derated: "Обмеження після 2 збоїв",
      critical_derate: "Мінімальний заряд", low_voltage: "Низька напруга",
      grid_outage: "Вхідна мережа відсутня", voltage_unavailable: "Датчик недоступний",
      voltage_stale: "Застарілі дані", current_unavailable: "Немає струму",
      write_failed: "Помилка запису", disabled: "Регулятор вимкнено",
      startup: "Ініціалізація", invalid_current_limits: "Некоректні межі струму",
    }[mode] || mode;
    const status = !enabled ? "off" : failure ? "bad" : warning ? "warn" : "ok";
    const maxNum = Number(max), targetNum=Number(target);
    const pct = Number.isFinite(maxNum) && maxNum > 0 && Number.isFinite(targetNum)
      ? Math.max(0,Math.min(100,100*targetNum/maxNum)) : 0;
    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; }
        ha-card { overflow:hidden; background:var(--ha-card-background,var(--card-background-color));
          color:var(--primary-text-color); border-radius:var(--ha-card-border-radius,18px); }
        .wrap { padding:19px; display:grid; gap:15px; }
        .top { display:flex; justify-content:space-between; align-items:center; gap:12px; }
        .brand { display:flex;align-items:center;gap:10px;font-size:15px;font-weight:800;letter-spacing:.3px; }
        .glyph { width:38px;height:38px;border-radius:12px;background:color-mix(in srgb,var(--primary-color) 12%,transparent);
          display:grid;place-items:center;font-size:21px; }
        .pill { border-radius:999px;padding:6px 10px;font-size:11px;font-weight:700;background:var(--secondary-background-color); }
        .pill.ok {color:var(--success-color,#27a26b)} .pill.warn {color:var(--warning-color,#e1a324)}
        .pill.bad {color:var(--error-color,#db5353)}
        .sub {font-size:12px;color:var(--secondary-text-color);margin-top:-8px}
        .hero {display:flex;justify-content:space-between;align-items:end;gap:12px}
        .metric-label {font-size:12px;color:var(--secondary-text-color)}
        .big {font-size:40px;font-weight:780;line-height:1.15;letter-spacing:-1.1px;font-variant-numeric:tabular-nums}
        .unit {font-size:15px;font-weight:500;color:var(--secondary-text-color)}
        .max {text-align:right}
        .max strong {display:block;font-size:21px;font-variant-numeric:tabular-nums}
        .bar {height:9px;border-radius:20px;background:var(--secondary-background-color);overflow:hidden}
        .fill {height:100%;border-radius:20px;background:var(--success-color,#27a26b);transition:width .35s}
        .grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
        .stat {background:var(--secondary-background-color);border-radius:12px;padding:12px;min-width:0}
        .stat .name {font-size:11px;color:var(--secondary-text-color);margin-bottom:6px}
        .stat .val {font-size:17px;font-weight:750;overflow-wrap:anywhere}
        .event {padding:12px;border:1px solid var(--divider-color);border-radius:12px;}
        .event-title {font-size:11px;text-transform:uppercase;color:var(--secondary-text-color);letter-spacing:.6px;margin-bottom:6px}
        .event-body {font-size:13px;line-height:1.5;overflow-wrap:anywhere}
        .foot {display:flex;justify-content:space-between;align-items:center;gap:8px}
        .button {cursor:pointer;border:0;border-radius:10px;font-size:13px;font-weight:650;padding:10px 14px;
          background:var(--primary-color);color:var(--text-primary-color,#fff)}
        .button.secondary {background:var(--secondary-background-color);color:var(--primary-text-color)}
        button:focus-visible {outline:2px solid var(--primary-color);outline-offset:2px}
        .small {font-size:11px;color:var(--secondary-text-color)}
        @media (max-width:360px){ .wrap{padding:13px} .brand{font-size:13px} .big{font-size:32px} }
      </style>
      <ha-card>
        <div class="wrap">
          <div class="top"><div class="brand"><div class="glyph">⚡</div> GRID CHARGE GUARD</div>
            <span class="pill ${status}">${this.escape(!enabled ? "OFF" : modeLabel)}</span></div>
          <div class="sub">Розумне керування зарядом від мережі</div>
          <div class="hero"><div><div class="metric-label">Цільовий струм</div>
            <div class="big">${this.escape(target)} <span class="unit">А</span></div></div>
            <div class="max"><div class="metric-label">Дозволений максимум</div>
            <strong>${this.escape(max)} А</strong></div></div>
          <div class="bar"><div class="fill" style="width:${pct}%"></div></div>
          <div class="grid">
            <div class="stat"><div class="name">Зникнень за 15 хв</div><div class="val">${this.escape(losses)}</div></div>
            <div class="stat"><div class="name">Режим</div><div class="val">${this.escape(modeLabel)}</div></div>
            ${c.actual_entity ? `<div class="stat"><div class="name">Ліміт Luxpower</div><div class="val">${this.escape(actual)} A</div></div>` : ""}
            ${c.voltage_entity ? `<div class="stat"><div class="name">Напруга мережі</div><div class="val">${this.escape(voltage)} В</div></div>` : ""}
          </div>
          <div class="event"><div class="event-title">Остання дія · ${this.escape(lastAt)}</div>
            <div class="event-body">${this.escape(lastMsg)}</div></div>
          <div class="foot"><button class="button ${enabled?'secondary':''}" id="toggle">
            ${enabled ? "Вимкнути автоматику" : "Увімкнути автоматику"}</button>
            <button class="button secondary" id="maximum">Змінити ліміт</button></div>
          <div class="small">Підтвердження значення HA не є окремою перевіркою Modbus-регістра.</div>
        </div>
      </ha-card>`;
    this.shadowRoot.getElementById("toggle")?.addEventListener("click", () => {
      this._hass.callService("switch", enabled ? "turn_off" : "turn_on", { entity_id: c.switch_entity });
    });
    this.shadowRoot.getElementById("maximum")?.addEventListener("click", () => this.showMoreInfo(c.max_entity));
  }
}
if (!customElements.get("grid-charge-guard-card")) {
  customElements.define("grid-charge-guard-card", GridChargeGuardCard);
  window.customCards = window.customCards || [];
  window.customCards.push({ type: "grid-charge-guard-card", name: "Grid Charge Guard",
    description: "Регулювання зарядного струму та історія захисних дій" });
}
