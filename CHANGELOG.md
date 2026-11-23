# Changelog

## 0.2.4

- Deduplicate 20-second Luxpower voltage reports inside the 10-second controller loop.
- Require distinct repeated readings before minimum-current action at 185–195 V; isolated 191 V readings no longer force 10 A.
- Retain immediate minimum limit below 185 V and independent 0 V TOMZN outage detection.
- Preserve configurable steps, averaging, dashboard and notifications.

## 0.2.3

- Add 8 persistent, native HA number entities for minimum AC current, up/down steps, ramp/drop intervals, and voltage averaging window.
- Make all dashboard metrics clickable to open native HA more-info/history, with an expandable settings section.
- Keep emergency voltage and outage protections fixed, preserve original entity IDs and storage compatibility.
- Add tests for tuning parameters and invalid stored settings.

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
