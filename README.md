# Grid Charge Guard

An experimental Home Assistant custom integration that **adjusts only the AC battery charging current limit** of an existing inverter integration using grid input voltage and recent grid interruptions. It does not connect to Luxpower/Modbus itself, and never writes PV charging limits or toggles AC charging.

**Status: v0.2.0, experimental. Use only after a backup, with AC charge current safely configured and the integration switch OFF at installation. Not a substitute for a voltage protection relay, phase selector, fuses, or BMS.**

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

## Behavior

- **Voltage <195 V:** minimum current (default 10 A, or higher if dictated by the number entity).
- **195–204.9 V:** decrease current by 10 A per 10-second tick.
- **205–214.9 V:** decrease by 5 A per 10-second tick.
- **215–219.9 V:** do not raise current.
- **≥220 V continuously for at least 5 minutes:** +5 A no more than every 5 minutes.
- **1 grid loss in a rolling 15-minute window:** record only; voltage regulation still applies.
- **2 grid losses:** cap current at 50 A.
- **3 or more losses:** cap at 10 A for at least 30 minutes following the last qualifying grid-loss event. New events extend the 30-minute hold.
- **Actual 0 V:** no Modbus set-value attempts while voltage is absent.
- Voltage values reported as `unknown`/`unavailable` do **not** count as outages. At startup an initial 0 V sample does not count as a new event. A low-voltage sample must persist for another 10-second poll to count as one loss. A new loss can only be counted after voltage recovers to ≥180 V.
- Stores enabled state, max current, recent losses, and derate expiry in HA `.storage`. After HA restart, upward ramping waits for five minutes of observed voltage ≥220 V. Missing readings prevent new writes.
- Disabling the integration stops changes to the AC charge limit, but does not restore the previous numeric limit. The existing AC charging enable switch is never changed.

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

## Development

Run `python -m pytest -q tests` for unit tests of the policy. For integration behavior, use a separate test Home Assistant instance with simulated entities; this repository has **not** undergone live Modbus/hardware tests.

Licensed MIT.

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
