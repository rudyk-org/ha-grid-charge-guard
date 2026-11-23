/** Grid Charge Guard v0.2.4 - bundled Home Assistant Lovelace card. */
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
        { name: "average_voltage_entity", selector: { entity: { domain: "sensor" } } },
        { name: "min_entity", selector: { entity: { domain: "number" } } },
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
      average_voltage_entity: "sensor.grid_voltage_average_3m",
      min_entity: "number.minimum_ac_charge_current",
      ramp_step_entity: "number.charge_ramp_up_step",
      moderate_step_entity: "number.moderate_voltage_drop_step",
      severe_step_entity: "number.severe_voltage_drop_step",
      ramp_interval_entity: "number.charge_ramp_interval",
      moderate_interval_entity: "number.moderate_drop_interval",
      severe_interval_entity: "number.severe_drop_interval",
      average_window_entity: "number.voltage_averaging_window",
      ...config,
    };
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this.render();
  }
  set hass(hass) { this._hass = hass; this.render(); }
  getCardSize() { return this._settingsOpen ? 9 : 5; }
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
    const averageVoltage = this.value(c.average_voltage_entity);
    const averageMinutes = this.value(c.average_window_entity);
    const last = this.state(c.last_event_entity);
    const lastMsg = last?.attributes?.message || "Очікуємо першої події регулятора";
    const lastAtRaw = last?.attributes?.time || "";
    const lastAt = lastAtRaw && !Number.isNaN(Date.parse(lastAtRaw))
      ? new Date(lastAtRaw).toLocaleString("uk-UA", { dateStyle: "short", timeStyle: "short" })
      : lastAtRaw;
    const settings = [
      ["Мінімальний AC струм", c.min_entity, "А"],
      ["Крок збільшення", c.ramp_step_entity, "А"],
      ["Крок зменшення · помірний", c.moderate_step_entity, "А"],
      ["Крок зменшення · сильний", c.severe_step_entity, "А"],
      ["Інтервал збільшення", c.ramp_interval_entity, "хв"],
      ["Інтервал помірного зниження", c.moderate_interval_entity, "с"],
      ["Інтервал сильного зниження", c.severe_interval_entity, "с"],
      ["Вікно усереднення", c.average_window_entity, "хв"],
    ];
    const settingCards = settings.map(([label, id, unit]) => `
      <button type="button" class="stat interactive" data-history="${this.escape(id)}"
        aria-label="Відкрити ${this.escape(label)} та історію змін">
        <div class="name">${this.escape(label)}</div>
        <div class="val">${this.escape(this.value(id))} ${this.escape(unit)}</div>
      </button>`).join("");
    const warning = ["critical_derate", "derated", "low_voltage", "voltage_dip", "grid_outage"].includes(mode);
    const failure = ["voltage_unavailable", "voltage_stale", "write_failed",
      "current_unavailable", "invalid_current_limits"].includes(mode);
    const modeLabel = {
      normal: "Мережа стабільна", derated: "Обмеження після 2 збоїв",
      critical_derate: "Мінімальний заряд", low_voltage: "Низька напруга", voltage_dip: "Коротка просадка",
      grid_outage: "Вхідна мережа відсутня", voltage_unavailable: "Датчик недоступний",
      voltage_stale: "Застарілі дані", current_unavailable: "Немає струму",
      write_failed: "Помилка запису", averaging: "Усереднення напруги",
      disabled: "Регулятор вимкнено",
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
        button.pill {border:0;cursor:pointer;font:inherit;font-size:11px;font-weight:700;}
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
        button.stat {font:inherit;text-align:left;color:inherit;border:0;width:100%;}
        .interactive {cursor:pointer;}
        .interactive:hover {filter:brightness(1.12)}
        .interactive:focus-visible {outline:2px solid var(--primary-color);outline-offset:2px}
        .metric-action {cursor:pointer;appearance:none;border:0;background:transparent;
          color:inherit;font:inherit;text-align:left;padding:0;}
        .metric-action:hover .big, .metric-action:hover strong {text-decoration:underline;text-decoration-thickness:1px;}
        .settings-wrap {display:grid;gap:10px;}
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
            <button type="button" class="pill ${status}" data-history="${this.escape(c.mode_entity)}"
              aria-label="Режим та історія">${this.escape(!enabled ? "OFF" : modeLabel)}</button></div>
          <div class="sub">Розумне керування зарядом від мережі</div>
          <div class="hero"><button type="button" class="metric-action" data-history="${this.escape(c.target_entity)}" aria-label="Історія цільового струму">
            <div class="metric-label">Цільовий струм</div>
            <div class="big">${this.escape(target)} <span class="unit">А</span></div></button>
            <button type="button" class="metric-action max" data-history="${this.escape(c.max_entity)}" aria-label="Максимум: керування та історія">
              <div class="metric-label">Дозволений максимум</div>
              <strong>${this.escape(max)} А</strong></button></div>
          <div class="bar"><div class="fill" style="width:${pct}%"></div></div>
          <div class="grid">
            <button type="button" class="stat interactive" data-history="${this.escape(c.losses_entity)}"><div class="name">Зникнень за 15 хв</div><div class="val">${this.escape(losses)}</div></button>
            <button type="button" class="stat interactive" data-history="${this.escape(c.mode_entity)}"><div class="name">Режим</div><div class="val">${this.escape(modeLabel)}</div></button>
            ${c.actual_entity ? `<button type="button" class="stat interactive" data-history="${this.escape(c.actual_entity)}"><div class="name">Ліміт Luxpower</div><div class="val">${this.escape(actual)} A</div></button>` : ""}
            ${c.voltage_entity ? `<button type="button" class="stat interactive" data-history="${this.escape(c.voltage_entity)}"><div class="name">Напруга мережі</div><div class="val">${this.escape(voltage)} В</div></button>` : ""}
            ${c.average_voltage_entity ? `<button type="button" class="stat interactive" data-history="${this.escape(c.average_voltage_entity)}"><div class="name">Середня за ${this.escape(averageMinutes)} хв</div><div class="val">${this.escape(averageVoltage)} В</div></button>` : ""}
          </div>
          <button type="button" class="event interactive" data-history="${this.escape(c.last_event_entity)}" style="background:transparent;color:inherit;font:inherit;text-align:left" aria-label="Остання дія та історія">
            <div class="event-title">Остання дія · ${this.escape(lastAt)}</div>
            <div class="event-body">${this.escape(lastMsg)}</div></button>
          <div class="foot"><button class="button ${enabled?'secondary':''}" id="toggle">
            ${enabled ? "Вимкнути автоматику" : "Увімкнути автоматику"}</button>
            <button class="button secondary" id="maximum">Змінити ліміт</button></div>
          <button class="button secondary" id="settings" aria-expanded="${Boolean(this._settingsOpen)}">
            ${this._settingsOpen ? "▾ Сховати параметри" : "▸ Налаштування регулятора"}</button>
          ${this._settingsOpen ? `<div class="settings-wrap"><div class="grid">${settingCards}</div>
            <div class="small">Натисни значення, щоб змінити його або переглянути історію HA.
              Пороги аварійного захисту не змінюються цими параметрами.</div></div>` : ""}
          <div class="small">Підтвердження значення HA не є окремою перевіркою Modbus-регістра.</div>
        </div>
      </ha-card>`;
    this.shadowRoot.getElementById("toggle")?.addEventListener("click", () => {
      this._hass.callService("switch", enabled ? "turn_off" : "turn_on", { entity_id: c.switch_entity });
    });
    this.shadowRoot.getElementById("maximum")?.addEventListener("click", () => this.showMoreInfo(c.max_entity));
    this.shadowRoot.getElementById("settings")?.addEventListener("click", () => {
      this._settingsOpen = !this._settingsOpen;
      this.render();
    });
    for (const item of this.shadowRoot.querySelectorAll("[data-history]")) {
      item.addEventListener("click", () => this.showMoreInfo(item.dataset.history));
    }
  }
}
if (!customElements.get("grid-charge-guard-card")) {
  customElements.define("grid-charge-guard-card", GridChargeGuardCard);
  window.customCards = window.customCards || [];
  window.customCards.push({ type: "grid-charge-guard-card", name: "Grid Charge Guard",
    description: "Регулювання зарядного струму та історія захисних дій" });
}
