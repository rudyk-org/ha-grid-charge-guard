# Changelog

## 0.2.2

- Use a 3-minute sliding voltage average with a 2-minute warmup to avoid reacting to every single noisy sample.
- Let 5 A increases resume after averaged voltage is stable; preserve instantaneous severe undervoltage protection.
- Rate-limit persistent average-based reductions and keep zero-voltage selector transfers out of the average.
- Add voltage average diagnostic sensor to the bundled card and controller tests.

## 0.2.1

- Throttle 205–214.9 V current reductions to 5 A per 30 seconds, instead of per 10-second poll.
- Preserve fast deep-voltage response and immediate hard caps from repeated grid losses.
- Add tests for rate limiting, severe dips, protective caps, and threshold boundaries.

## 0.2.0

- Bundle an attractive Lovelace card with live controller state and basic controls.
- Add an optional notify entity selector to integration options; Telegram works via Home Assistant notify and requires no credentials in the repository.
- Emit native `grid_charge_guard_event` diagnostics for actual action requests, observed readbacks, failures and grid-loss protections.
- Add `sensor.grid_charge_last_event` for the latest action and attributes.
- Suppress per-step Telegram spam; notify only important events with a per-type 15 minute cooldown.
- Do not alter current control thresholds, PV charging limits or AC enable state.
- Remove the overstrict HACS minimum Home Assistant version from `hacs.json` (compatibility with every old HA release is **not** guaranteed).

## 0.1.0

- Initial grid-voltage adaptive AC battery current controller.
