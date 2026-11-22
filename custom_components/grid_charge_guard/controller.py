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
)
from .logic import decide_current

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
        self._last_increase = time.time()
        self._last_write = 0.0

    async def async_load(self) -> None:
        data = await self.store.async_load() or {}
        self.enabled = bool(data.get("enabled", False))
        self.user_max = max(MIN_CURRENT, min(MAX_CURRENT, float(data.get("user_max", DEFAULT_MAX))))
        now = time.time()
        self.events = deque(float(t) for t in data.get("events", [])
                            if isinstance(t, (int, float)) and 0 <= now - t < OUTAGE_WINDOW)
        self.derate_until = float(data.get("derate_until", 0.0))
        self.mode = "startup" if self.enabled else "disabled"

    async def _save(self) -> None:
        await self.store.async_save({
            "enabled": self.enabled,
            "user_max": self.user_max,
            "events": list(self.events),
            "derate_until": self.derate_until,
        })

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
        self._last_increase = time.time()
        await self._save()
        self._notify()
        if enabled:
            self.hass.async_create_task(self.async_tick())

    async def set_maximum(self, maximum: float) -> None:
        self.user_max = max(MIN_CURRENT, min(MAX_CURRENT, maximum))
        await self._save()
        self._notify()
        if self.enabled:
            self.hass.async_create_task(self.async_tick())

    async def async_tick(self) -> None:
        if self._tick_lock.locked():
            return
        async with self._tick_lock:
            await self._tick()

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
        if not math.isfinite(voltage) or voltage < 0 or voltage > 300:
            self.mode = "voltage_unavailable"
            self._stable_since = None
            self._notify()
            return

        # Some integrations publish unchanged values periodically via state_reported.
        # If no reported update is observed for two minutes, don't issue a write.
        reported = getattr(voltage_state, "last_reported", None)
        if reported is not None and (now - reported.timestamp()) > 120:
            self.mode = "voltage_stale"
            self._stable_since = None
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
            if not self._in_outage:
                if self._low_since is None:
                    self._low_since = now
                elif now - self._low_since >= 5:
                    self._low_since = None
                    self._in_outage = True
                    self.events.append(now)
                    if len(self.events) >= 3:
                        self.derate_until = now + DERATE_HOLD
                    await self._save()
            self.mode = "grid_outage"
            self._notify()
            return

        self._low_since = None
        if voltage >= RECOVERY_VOLTAGE:
            self._in_outage = False

        if voltage < 220:
            self._stable_since = None
        elif self._stable_since is None:
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
        native_min = max(MIN_CURRENT, float(attrs.get("min", MIN_CURRENT)))
        native_max = min(MAX_CURRENT, float(attrs.get("max", MAX_CURRENT)))
        step = max(1.0, float(attrs.get("step", 1.0)))
        if native_min > native_max:
            self.mode = "invalid_current_limits"
            self._notify()
            return

        decision = decide_current(
            voltage=voltage, current=actual,
            user_max=min(self.user_max, native_max), min_current=native_min,
            losses=self.losses, derate_active=(now < self.derate_until),
            stable_for=(now - self._stable_since if self._stable_since is not None else 0),
            since_increase=now - self._last_increase,
        )
        # Quantize DOWN to avoid exceeding a safe cap.
        target = max(native_min, native_min +
                     math.floor((decision.target - native_min) / step) * step)
        target = round(min(target, native_max), 3)
        self.target = int(target) if target.is_integer() else target
        self.mode = decision.mode
        self._notify()

        if abs(actual - target) < step / 2 or now - self._last_write < 10:
            return

        try:
            # Never toggle switch.ac_charging or any PV / total charge limits.
            await self.hass.services.async_call(
                "number", "set_value",
                {ATTR_ENTITY_ID: self.current_entity, "value": target},
                blocking=True,
            )
            self._last_write = now
            if target > actual:
                self._last_increase = now
            _LOGGER.info("Grid Charge Guard: AC charge current %.1f -> %.1f A", actual, target)
        except Exception:
            self._last_write = now
            self.mode = "write_failed"
            self._notify()
            _LOGGER.exception("Failed to set AC charging limit on %s", self.current_entity)
