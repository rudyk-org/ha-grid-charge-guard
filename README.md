# Grid Charge Guard

An experimental Home Assistant custom integration that **adjusts only the AC battery charging current limit** of an existing inverter integration using grid input voltage and recent grid interruptions. It does not connect to Luxpower/Modbus itself, and never writes PV charging limits or toggles AC charging.

**Status: v0.2.4, experimental. Use only after a backup, with AC charge current safely configured and the integration switch OFF at installation. Not a substitute for a voltage protection relay, phase selector, fuses, or BMS.**

## Requirements

- Home Assistant with access to a **grid input voltage** `sensor` entity. The sensor must report volts and fall toward 0 V during the phase selector's interruption; EPS/output voltage is NOT appropriate.
- A writable `number` entity controlling the inverter's **AC battery charge current** in amperes on the battery side, not a PV+AC total current limit.
- Optional Marketplace (HA 2026.11+) or HACS (older HA versions) for installation and updates.

## Installation

> Official project repository: https://github.com/rudyk-org/ha-grid-charge-guard


1. Publish these repository files to a **public GitHub repo** (update `manifest.json` URLs if the repository name/owner changes).
2. Home Assistant 2026.11+: Settings → Marketplace → Custom repositories, add the GitHub repository URL as an **Integration**; install and restart HA. On older versions, use HACS custom repositories.
3. Settings → Devices & services → Add integration → **Grid Charge Guard**.
4. Select a **grid input voltage sensor** and the **AC charge battery current number**. Check that both represent the intended hardware registers.
5. On the integration's device/entities, set **Allowed AC charge current** (default 60 A; never more than the safe grid, inverter and battery system can support) and turn on **Adaptive AC charging** after confirming it works.

For manual installation copy `custom_components/grid_charge_guard` to `/config/custom_components/grid_charge_guard`, restart HA, and add the integration from Devices & services.

## Behavior (v0.2.2)

- Voltage sampled every **10 seconds** into a **3-minute sliding average**; ordinary regulation requires at least **2 minutes of samples** after startup or an outage. The average is exposed as `sensor.grid_voltage_average_3m`.
- **Average ≥220 V:** increase grid-only charging by 5 A at most every **3 minutes**, after at least 2 minutes of acceptable averaged voltage. A brief average drop to 215–219 V does not reset the recovery timer.
- **Average 215–219.9 V:** hold current, do not repeatedly reduce it.
- **Average 205–214.9 V:** reduce by 5 A at most once every **2 minutes**.
- **Average below 205 V:** reduce by 10 A at most every **45 seconds**.
- **Instantaneous voltage below 205 V for at least 20 seconds:** reduce by 10 A, bypassing a high moving average (at most every 30 seconds).
- **Instantaneous voltage below 195 V:** immediately request the minimum current (10 A by default), even before the mean is ready.
- **Grid voltage falls below 50 V:** treat as outage/phase transfer. No writes during the outage; discard old average and count interruption independently. An `unknown`/`unavailable` sensor value is **not** a confirmed grid loss.
- **1 loss in rolling 15 minutes:** log; **2 losses:** cap at 50 A; **3+ losses:** cap at 10 A for at least 30 minutes. Protective caps are not throttled by averaging.
- **PV, BMS and AC Charging toggle:** never modified. Only the selected grid charging current `number` is written.
- After restart, the average is rebuilt before ramping up; a missing or stale voltage source suspends writes.

### Upgrade from v0.2.1

Apply the patch, update the integration and restart Home Assistant. For the updated card frontend, change the resource URL to `/grid-charge-guard/card.js?v=0.2.2` and refresh the browser. The existing `notify` configuration and dashboard entity IDs are preserved. New optional card entity: `average_voltage_entity: sensor.grid_voltage_average_3m`.

## Important limitations

- This integration **cannot guarantee the entire line stays below 32 A**, since input grid current and the home's other loads are not measured here. Max current defaults to 60 A (battery side); raising it to 100 A is a deliberate user choice and must be tested.
- HA observes entities, not independent Modbus register acknowledgements. Check sensor reading and inverter settings after a write.
- If a voltage entity stays at an old numeric value instead of becoming unavailable, its freshness is checked using `last_reported` where available; not all integrations guarantee fresh data or regular reports.
- Outage detection can miss events if HA is down, or if the voltage integration does not report a 30-second interruption. Rolling events and cooldown persist, but events occurring during downtime cannot be recovered.
- Do not run a second HA automation that controls the **same AC charge current** entity at the same time. Existing SOC-profile Watchdog automations can continue if they do not touch this number entity.
- Do not rely on this for critical power safety. Test with a conservative maximum and read back register values.

## Sensors/entities

- `switch.*_adaptive_ac_charging`: enable/disable the regulator
- `number.*_allowed_ac_charge_current`: configured user maximum (10–100 A)
- `sensor.*_grid_charge_mode`: `normal`, `derated`, `critical_derate`, `low_voltage`, `grid_outage`, `disabled`, or error states
- `sensor.*_grid_losses_15m`: count of low-voltage interruption events in the last 15 minutes
- `sensor.*_adaptive_target_current`: last computed target in A
- `sensor.*_grid_voltage_average_3m`: time-windowed input voltage average (V), blank during warmup

## Development

Run `python -m pytest -q tests` for unit tests of the policy. For integration behavior, use a separate test Home Assistant instance with simulated entities; this repository has **not** undergone live Modbus/hardware tests.

Licensed MIT.

## v0.2.2: sliding voltage average and recovery hysteresis

- Use a three-minute moving average for normal derating/ramp-up decisions.
- Keep a raw-voltage emergency path and the separate phase-transfer/outage counter.
- Resume incremental charging after averaged voltage stabilizes instead of resetting on every brief dip.
- Expose the new voltage average sensor and show it in the bundled card.

## v0.2.1: prevent overreaction to moderate voltage dips

- Moderate grid undervoltage (205–214.9 V) causes at most one 5 A decrease per 30 seconds of successfully requested reductions, instead of one per 10-second tick.
- Severe voltage dips below 205 V and protective derating after repeated outages still act immediately (subject to Modbus/HA state reporting).
- No changes to PV charging, the inverter's AC Charging enable switch, notifications or the dashboard card.
- When installing the updated card for the first time, the bundled JS remains at v0.2.0; there is no frontend resource change in this release.

## v0.2.0: dashboard card, diagnostics and alerts

**Experimental release.** Version 0.2.0 adds observability without changing voltage/current control thresholds. It still **only writes to the selected AC charging `number` entity**. The voltage selector, automatic charging enable switch, PV charging limit and BMS configuration are untouched.

### Dashboard card bundled with the integration

The integration serves its JavaScript card directly. **No separate frontend repository is required.** Add its resource **once**:

1. Settings → Dashboards → three-dot menu → Resources → Add resource.
2. URL: `/grid-charge-guard/card.js?v=0.2.0`; type: **JavaScript module**.
3. Open the dashboard, Edit → Add card → Manual; paste:

```yaml
type: custom:grid-charge-guard-card
# Optional, if you want to display them:
# actual_entity: number.YOUR_LUXPOWER_AC_CHARGE_CURRENT
# voltage_entity: sensor.YOUR_GRID_INPUT_VOLTAGE
```

Default card entities are `switch.adaptive_ac_charging`, `number.allowed_ac_charge_current`, `sensor.adaptive_target_current`, `sensor.grid_charge_mode`, `sensor.grid_losses_15m` and `sensor.grid_charge_last_event`.

If your entities have a suffix (`_2`), edit the card configuration to supply `switch_entity`, `max_entity`, `target_entity`, `mode_entity`, `losses_entity` or `last_event_entity` explicitly. Opening the maximum uses Home Assistant's own More Info dialog and the toggle calls the real switch service, not a Developer Tools state override.

On upgrading the JS file, update `?v=0.2.0` and reload the browser to avoid stale frontend cache. The card is served without auth like other Lovelace resources: do not put secrets into this JavaScript file.

### Telegram (or other Home Assistant notify entities)

1. Add/configure a Telegram Bot integration so that a `notify.*` entity exists. Do **not** put bot tokens or chat IDs in this repository.
2. Settings → Devices & Services → Grid Charge Guard → **Configure** → **Notifications**; choose that `notify.*` entity.
3. Important events will be sent through `notify.send_message`: two/three grid losses, unavailable/stale voltage, failed writes, unconfirmed readback and recovery after at least five minutes of stable grid.
4. Leave the notify entity blank to disable push messages. This doesn't disable the activity events, sensor or card.

Normal +5 A/-5 A steps are **not** sent to Telegram. Each alert type has a 15-minute anti-spam cooldown per integration process. Under repeated errors HA logs the event even if Telegram is unavailable.

### Native diagnostics / automation triggers

The integration now emits `grid_charge_guard_event` on the Home Assistant event bus. Typical event payload:

```json
{
  "event": "current_requested",
  "message": "Запитано зміну AC-струму 50 → 40 А (low_voltage).",
  "severity": "info",
  "time": "2026-11-22T19:00:00+00:00",
  "current_entity": "number.ac_charge_current_from_grid",
  "previous": 50,
  "target": 40,
  "reason": "low_voltage",
  "voltage": 199
}
```

`current_observed` means the **Home Assistant number entity** subsequently reported the requested target. It **does not guarantee an independent physical Modbus-register readback**. `write_unconfirmed` is emitted if 65 seconds pass without seeing the value in the HA entity. On materially lower voltage the controller can still request a lower current before that timeout.

Events are not retained forever; the newest one is exposed as `sensor.grid_charge_last_event` with attributes (`time`, `message`, `previous`, `target`, etc.). HA Recorder can maintain a historical trail if that entity is included in Recorder. To inspect emitted events in Developer Tools → Events, subscribe to `grid_charge_guard_event`.

### Upgrade

The existing config entry and regulator state are preserved. After upgrading the integration files, restart HA, add the optional notify entity using Configure and add the bundled card resource. **Disable automation temporarily during upgrade** and test with a conservative AC current cap; the new notification logic has not been tested against your physical inverter.

## v0.2.3: live tuning and native HA history

Eight native `number` entities were added and settings persist in the integration's HA `.storage` alongside the existing maximum. They are live-editable from the device entity dialog or the card's **Налаштування регулятора** section, no HA restart required:

| Entity (usual ID) | Default | Allowed range |
| --- | ---: | --- |
| `number.minimum_ac_charge_current` | 10 A | 5–50 A (5 A step) |
| `number.charge_ramp_up_step` | 5 A | 5–20 A (5 A step) |
| `number.moderate_voltage_drop_step` | 5 A | 5–20 A (5 A step) |
| `number.severe_voltage_drop_step` | 10 A | 5–30 A (5 A step) |
| `number.charge_ramp_interval` | 3 min | 2–15 min |
| `number.moderate_drop_interval` | 120 s | 30–300 s (30 s step) |
| `number.severe_drop_interval` | 45 s | 30–180 s (15 s step) |
| `number.voltage_averaging_window` | 3 min | 2–10 min |

**Min/max relationship:** the minimum is capped by the user maximum (and by the actual inverter `number` min/max for writes). The effective safe minimum is the greatest of the configured minimum and the inverter entity's native minimum. If the hardware requires at least 10 A, setting 5 A in the UI **does not** cause a 5 A Modbus command.

**Safety limits remain fixed:** raw voltage below 195 V triggers the configured effective minimum; the grid-loss detector still counts zero-voltage interruptions separately; at 2 losses the allowed current is capped at 50 A, at 3 losses the effective minimum is held for 30 minutes. This update does **not** change PV charging, total charge, or the AC Charging switch. Changing the averaging window resets the observation window and upward ramp warmup.

**Card / history:** update the Lovelace resource URL to `/grid-charge-guard/card.js?v=0.2.4` and hard-refresh the dashboard. Tap the target current, maximum, input voltage, averaged voltage, mode, loss count, actual inverter limit, or the most recent event to open Home Assistant's native more-info dialog. Numeric controls in the expandable settings section open the native value editor with history. This relies on the HA Recorder storing those entities; no history is invented by the card.

Existing dashboards keep the legacy `sensor.grid_voltage_average_3m` entity ID for compatibility; its new attribute `configured_window_minutes` reflects the actual filter duration, which may no longer be 3 minutes.

**After upgrading:** disable adaptive control during replacement, restart HA, confirm the new number entities exist and have sane defaults, then re-enable with a conservative maximum. This release is tested with pure Python logic unit tests and JS syntax checks only, not on a physical Luxpower.

## v0.2.4: handle 20-second Luxpower voltage reports

- Process each actual HA voltage report only once (`last_reported`, fallback `last_updated`). The 10-second controller poll no longer duplicates voltage history or low-voltage confirmations.
- An isolated input reading of **185–194.9 V** is marked `voltage_dip` and does not immediately force charging to the minimum. Two distinct consecutive low reports allow a single rate-limited severe reduction; three force the floor.
- Below **185 V**, immediately reduce the AC charging current to its allowed minimum, subject to HA/Modbus responsiveness. Actual grid loss (0 V) remains separately counted, without Modbus writes during the loss.
- Average-based control, user-configured steps and minimum current, TOMZN switching events, Telegram and the card remain supported.
- The HA polling loop cannot act before the inverter reports a drop, and **software is not a replacement for the hardware voltage relay/phase selector**.
- Test on the hardware with a conservative cap and compare `sensor.grid_voltage_average_3m`, the Luxpower current limit, and `sensor.grid_charge_mode`.
