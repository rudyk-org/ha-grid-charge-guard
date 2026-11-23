"""Entity-based charger controller; never communicates directly with Modbus.

The controller ONLY writes to the selected number entity; it never toggles AC
charging or modifies total battery/PV current limits.
"""
from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from datetime import timedelta
import logging
import math
import time

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN, CONF_CURRENT_ENTITY, CONF_VOLTAGE_ENTITY, DEFAULT_MAX,
    MIN_CURRENT, MAX_CURRENT, OUTAGE_VOLTAGE, RECOVERY_VOLTAGE,
    OUTAGE_WINDOW, DERATE_HOLD, POLL_SECONDS, STORAGE_VERSION,
    WRITE_CONFIRM_TIMEOUT_SECONDS, VOLTAGE_AVERAGE_WINDOW_SECONDS,
    VOLTAGE_AVERAGE_WARMUP_SECONDS, VOLTAGE_AVERAGE_MIN_SAMPLES,
    SETTING_SPECS,
)
from .logic import decide_current, VoltageWindow, normalize_setting
from .reporter import EventReporter

_LOGGER = logging.getLogger(__name__)


class GridChargeController:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.voltage_entity = entry.data[CONF_VOLTAGE_ENTITY]
        self.current_entity = entry.data[CONF_CURRENT_ENTITY]
        self.store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}")
        self.enabled = False
        self.user_max = DEFAULT_MAX
        self.settings = {name: spec["default"] for name, spec in SETTING_SPECS.items()}
        self.mode = "disabled"
        self.target: int | None = None
        self.events: deque[float] = deque()
        self.derate_until = 0.0
        self._listeners: set[Callable] = set()
        self._unsub_timer = None
        self._tick_lock = asyncio.Lock()
        self._seen_valid_voltage = False
        self._in_outage = False
        self._low_since: float | None = None
        self._stable_since: float | None = None
        # The 0 V selector transfer is handled separately, never averaged.
        self._voltage_filter = self._new_voltage_filter()
        self.average_voltage: float | None = None
        self._sustained_low_since: float | None = None
        self._last_increase = time.time()
        # First moderate voltage dip may reduce immediately; later drops are throttled.
        self._last_voltage_decrease = float("-inf")
        self._last_write = 0.0
        self.reporter = EventReporter(self)
        self._pending_write: dict | None = None

    async def async_load(self) -> None:
        data = await self.store.async_load() or {}
        self.enabled = bool(data.get("enabled", False))
        saved_settings = data.get("settings", {})
        if not isinstance(saved_settings, dict):
            saved_settings = {}
        for name, spec in SETTING_SPECS.items():
            self.settings[name] = self._bound_setting(
                name, saved_settings.get(name, spec["default"])
            )
        self.user_max = max(
            self.settings["min_current"],
            min(MAX_CURRENT, float(data.get("user_max", DEFAULT_MAX))),
        )
        self._voltage_filter = self._new_voltage_filter()
        now = time.time()
        self.events = deque(float(t) for t in data.get("events", [])
                            if isinstance(t, (int, float)) and 0 <= now - t < OUTAGE_WINDOW)
        self.derate_until = float(data.get("derate_until", 0.0))
        self.mode = "startup" if self.enabled else "disabled"

    async def _save(self) -> None:
        await self.store.async_save({
            "enabled": self.enabled,
            "user_max": self.user_max,
            "settings": self.settings.copy(),
            "events": list(self.events),
            "derate_until": self.derate_until,
        })

    @staticmethod
    def _bound_setting(name: str, raw: float) -> int:
        return normalize_setting(raw, SETTING_SPECS[name])

    def _new_voltage_filter(self) -> VoltageWindow:
        window = self.settings["average_window_minutes"] * 60
        warmup = min(window - 10, max(60, round(window * 2 / 3)))
        return VoltageWindow(window, warmup, VOLTAGE_AVERAGE_MIN_SAMPLES)

    @property
    def losses(self) -> int:
        now = time.time()
        return sum(1 for t in self.events if 0 <= now - t < OUTAGE_WINDOW)

    @callback
    def add_listener(self, listener: Callable) -> Callable:
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    @callback
    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    def start(self) -> None:
        # Treat first 5 minutes after an HA reboot as an observation period.
        self._stable_since = None
        self._voltage_filter.clear()
        self.average_voltage = None
        self._sustained_low_since = None
        self._last_increase = time.time()
        self._unsub_timer = async_track_time_interval(
            self.hass, self._timer_callback, timedelta(seconds=POLL_SECONDS)
        )
        self.hass.async_create_task(self.async_tick())

    @callback
    def _timer_callback(self, _now) -> None:
        self.hass.async_create_task(self.async_tick())

    def stop(self) -> None:
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    async def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.mode = "startup" if enabled else "disabled"
        self._stable_since = None
        # Rebuild the average on re-enabling; do not reuse stale voltage.
        self._voltage_filter.clear()
        self.average_voltage = None
        self._sustained_low_since = None
        self._last_increase = time.time()
        await self._save()
        self._notify()
        await self.reporter.emit(
            "enabled" if enabled else "disabled",
            "Автоматичне регулювання увімкнено" if enabled else "Автоматичне регулювання вимкнено",
        )
        if enabled:
            self.hass.async_create_task(self.async_tick())

    async def set_maximum(self, maximum: float) -> None:
        self.user_max = max(self.settings["min_current"],
                            min(MAX_CURRENT, maximum))
        await self._save()
        self._notify()
        if self.enabled:
            self.hass.async_create_task(self.async_tick())

    async def set_setting(self, name: str, value: float) -> None:
        """Apply a controller setting without restarting HA or touching PV limits."""
        if name not in SETTING_SPECS:
            raise ValueError(f"Unknown charge setting: {name}")
        bounded = self._bound_setting(name, value)
        if name == "min_current":
            bounded = min(bounded, self.user_max)
        if self.settings[name] == bounded:
            return
        self.settings[name] = bounded
        if name == "average_window_minutes":
            self._voltage_filter = self._new_voltage_filter()
            self.average_voltage = None
            self._stable_since = None
            self._last_increase = time.time()
        await self._save()
        self._notify()
        if self.enabled:
            self.hass.async_create_task(self.async_tick())

    async def async_tick(self) -> None:
        if self._tick_lock.locked():
            return
        async with self._tick_lock:
            await self._tick()

    def _update_average(self, now: float, voltage: float) -> None:
        self.average_voltage = self._voltage_filter.add(now, voltage)

    async def _tick(self) -> None:
        now = time.time()
        original_count = len(self.events)
        while self.events and now - self.events[0] >= OUTAGE_WINDOW:
            self.events.popleft()
        if len(self.events) != original_count:
            await self._save()

        voltage_state = self.hass.states.get(self.voltage_entity)
        current_state = self.hass.states.get(self.current_entity)
        try:
            voltage = float(voltage_state.state) if voltage_state is not None else math.nan
        except (ValueError, TypeError):
            voltage = math.nan
        await self._check_pending_write(now, current_state)
        if not math.isfinite(voltage) or voltage < 0 or voltage > 300:
            if self.mode != "voltage_unavailable":
                await self.reporter.emit("voltage_unavailable",
                    "Датчик вхідної напруги недоступний. Автоматичні записи призупинено.",
                    severity="warning", notify=True)
            self.mode = "voltage_unavailable"
            self._stable_since = None
            self._voltage_filter.clear()
            self.average_voltage = None
            self._sustained_low_since = None
            self._notify()
            return

        # Some integrations publish unchanged values periodically via state_reported.
        # If no reported update is observed for two minutes, don't issue a write.
        reported = getattr(voltage_state, "last_reported", None)
        if reported is not None and (now - reported.timestamp()) > 120:
            if self.mode != "voltage_stale":
                await self.reporter.emit("voltage_stale",
                    "Дані напруги застаріли понад 120 с. Записи призупинено.",
                    severity="warning", notify=True)
            self.mode = "voltage_stale"
            self._stable_since = None
            self._voltage_filter.clear()
            self.average_voltage = None
            self._sustained_low_since = None
            self._notify()
            return

        # First sample after start only arms detection; prevents phantom outage.
        if not self._seen_valid_voltage:
            self._seen_valid_voltage = True
            if voltage < OUTAGE_VOLTAGE:
                self._in_outage = True
            self._notify()

        if voltage < OUTAGE_VOLTAGE:
            self._stable_since = None
            self._voltage_filter.clear()
            self.average_voltage = None
            self._sustained_low_since = None
            if not self._in_outage:
                if self._low_since is None:
                    self._low_since = now
                elif now - self._low_since >= 5:
                    self._low_since = None
                    self._in_outage = True
                    self.events.append(now)
                    count = self.losses
                    if count >= 3:
                        self.derate_until = now + DERATE_HOLD
                    await self._save()
                    if count in (2, 3):
                        cap = 50 if count == 2 else self.settings["min_current"]
                        await self.reporter.emit(
                            f"grid_loss_{count}",
                            f"{count} зникнення мережі за 15 хв. Обмеження AC-заряду до {cap} А.",
                            severity="warning", notify=True,
                            grid_losses=count, voltage=voltage, cap=cap,
                        )
                    else:
                        await self.reporter.emit("grid_loss",
                            f"Зафіксовано зникнення вхідної напруги (за 15 хв: {count}).",
                            grid_losses=count, voltage=voltage)
            self.mode = "grid_outage"
            self._notify()
            return

        self._low_since = None
        if voltage >= RECOVERY_VOLTAGE:
            self._in_outage = False

        # Use a time-windowed mean for normal current control and recovery.
        # If input voltage is below 180 V, don't use that reading to authorize
        # an upward ramp. Raw <195 V still triggers the emergency current floor.
        if voltage >= RECOVERY_VOLTAGE:
            self._update_average(now, voltage)
        else:
            self._voltage_filter.clear()
            self.average_voltage = None

        if voltage < 205:
            if self._sustained_low_since is None:
                self._sustained_low_since = now
        else:
            self._sustained_low_since = None
        sustained_low = (self._sustained_low_since is not None
                         and now - self._sustained_low_since >= 20)

        # Hysteresis: a brief mean dip to 218 V does not erase the entire
        # recovery period. Sustained raw dips or a weak mean reset recovery.
        if (self.average_voltage is None or self.average_voltage < 215
                or sustained_low or voltage < 195):
            self._stable_since = None
        elif self.average_voltage >= 220 and self._stable_since is None:
            self._stable_since = now

        if not self.enabled:
            self.mode = "disabled"
            self.target = None
            self._notify()
            return

        try:
            actual = float(current_state.state) if current_state is not None else math.nan
        except (ValueError, TypeError):
            actual = math.nan
        if not math.isfinite(actual):
            self.mode = "current_unavailable"
            self._notify()
            return

        # Cap at the target entity's own min/max. Respect its declared step.
        attrs = current_state.attributes
        native_min = max(MIN_CURRENT, self.settings["min_current"],
                         float(attrs.get("min", MIN_CURRENT)))
        native_max = min(MAX_CURRENT, self.user_max,
                         float(attrs.get("max", MAX_CURRENT)))
        step = max(1.0, float(attrs.get("step", 1.0)))
        if native_min > native_max:
            self.mode = "invalid_current_limits"
            self._notify()
            return

        decision = decide_current(
            voltage=voltage, average_voltage=self.average_voltage,
            sustained_low=sustained_low, current=actual,
            user_max=min(self.user_max, native_max), min_current=native_min,
            losses=self.losses, derate_active=(now < self.derate_until),
            stable_for=(now - self._stable_since if self._stable_since is not None else 0),
            since_increase=now - self._last_increase,
            since_voltage_decrease=now - self._last_voltage_decrease,
            ramp_up_step=self.settings["ramp_up_step"],
            moderate_drop_step=self.settings["moderate_drop_step"],
            severe_drop_step=self.settings["severe_drop_step"],
            ramp_interval_seconds=self.settings["ramp_interval_minutes"] * 60,
            moderate_drop_interval_seconds=self.settings["moderate_drop_interval_seconds"],
            severe_drop_interval_seconds=self.settings["severe_drop_interval_seconds"],
        )
        # Quantize DOWN to avoid exceeding a safe cap.
        target = max(native_min, native_min +
                     math.floor((decision.target - native_min) / step) * step)
        target = round(min(target, native_max), 3)
        self.target = int(target) if target.is_integer() else target
        self.mode = decision.mode
        self._notify()

        # Recovery notice only after sustained averaged voltage recovery.
        if (self.reporter.recovery_needed and self.mode == "normal"
                and self.average_voltage is not None
                and self.average_voltage >= 220
                and self._stable_since is not None
                and now - self._stable_since >= 120):
            await self.reporter.emit("recovered",
                "Середня напруга стабільна, звичайне регулювання відновлено.",
                notify=True, voltage=voltage, average_voltage=self.average_voltage)

        if abs(actual - target) < step / 2 or now - self._last_write < 10:
            return
        # Avoid repeatedly writing a value that has not yet been read back.
        # Still allow urgent downward corrections if the required target falls.
        if (self._pending_write and now < self._pending_write["deadline"]
                and target >= self._pending_write["target"]):
            return

        try:
            # Never toggle switch.ac_charging or any PV / total charge limits.
            await self.hass.services.async_call(
                "number", "set_value",
                {ATTR_ENTITY_ID: self.current_entity, "value": target},
                blocking=True,
            )
            self._last_write = now
            self._pending_write = {
                "previous": actual, "target": target, "deadline": now + WRITE_CONFIRM_TIMEOUT_SECONDS,
                "reason": decision.mode,
            }
            if target > actual:
                self._last_increase = now
            elif target < actual and decision.mode == "low_voltage":
                # Average-driven reductions also need throttling even if the
                # instantaneous voltage has already recovered.
                self._last_voltage_decrease = now
            await self.reporter.emit(
                "current_requested",
                f"Запитано зміну AC-струму {actual:g} → {target:g} А ({decision.mode}).",
                previous=actual, target=target, voltage=voltage,
                average_voltage=self.average_voltage, reason=decision.mode,
            )
        except Exception:
            self._last_write = now
            self._pending_write = None
            self.mode = "write_failed"
            self._notify()
            await self.reporter.emit("write_failed",
                f"Помилка надсилання AC-струму {target:g} А до Luxpower.",
                severity="error", notify=True, target=target, voltage=voltage)
            _LOGGER.exception("Failed to set AC charging limit on %s", self.current_entity)

    async def _check_pending_write(self, now: float, current_state) -> None:
        """Observe HA entity readback; this is not independent Modbus acknowledgement."""
        pending = self._pending_write
        if not pending or current_state is None:
            return
        try:
            current = float(current_state.state)
        except (TypeError, ValueError):
            current = math.nan
        if math.isfinite(current) and abs(current - pending["target"]) < 0.5:
            self._pending_write = None
            await self.reporter.emit(
                "current_observed",
                f"HA показує новий ліміт AC-струму: {current:g} А.",
                previous=pending["previous"], target=pending["target"],
                reason=pending["reason"],
            )
        elif now >= pending["deadline"]:
            self._pending_write = None
            await self.reporter.emit(
                "write_unconfirmed",
                f"Через 65 с після запиту {pending['target']:g} А HA досі показує "
                f"{current:g} А. Перевір Luxpower.",
                severity="warning", notify=True,
                expected=pending["target"], observed=current,
            )
