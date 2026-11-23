"""Dependency-free charging policy. Currents are battery-side AC charging amps."""
from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from math import isfinite


def normalize_setting(raw, spec: dict) -> int:
    """Clamp and quantize a native HA number setting (safe on malformed storage)."""
    try:
        value = float(raw)
    except (ValueError, TypeError):
        value = spec["default"]
    if not isfinite(value):
        value = spec["default"]
    value = min(spec["maximum"], max(spec["minimum"], value))
    return int(spec["minimum"] +
               round((value - spec["minimum"]) / spec["step"]) * spec["step"])


# Fast protective steps for sustained low voltage, slow steps for 3-minute mean.
LOW_VOLTAGE_DROP_INTERVAL_SECONDS = 30
AVERAGE_SEVERE_DROP_INTERVAL_SECONDS = 45
AVERAGE_MODERATE_DROP_INTERVAL_SECONDS = 120


class VoltageWindow:
    """Time-windowed input voltage; outage samples must never be averaged."""

    def __init__(self, window_seconds=180, warmup_seconds=120, min_samples=8):
        self.window_seconds = window_seconds
        self.warmup_seconds = warmup_seconds
        self.min_samples = min_samples
        self.samples: deque[tuple[float, float]] = deque()

    def clear(self) -> None:
        self.samples.clear()

    def add(self, now: float, voltage: float) -> float | None:
        """Return a mean after warmup, or None for invalid/incomplete history."""
        if not isfinite(voltage) or voltage < 180 or voltage > 300:
            self.clear()
            return None
        self.samples.append((now, voltage))
        while self.samples and now - self.samples[0][0] > self.window_seconds:
            self.samples.popleft()
        if (len(self.samples) < self.min_samples
                or now - self.samples[0][0] < self.warmup_seconds):
            return None
        return round(sum(v for _, v in self.samples) / len(self.samples), 2)


class VoltageObservations:
    """Count actual HA reports rather than repeated controller polls.

    A 20-second sensor value seen twice by the 10-second timer is one sample.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.last_report_at: float | None = None
        self.low_samples = 0
        self.critical_samples = 0
        self.first_low_at: float | None = None

    def observe(self, reported_at: float, voltage: float) -> bool:
        if self.last_report_at == reported_at:
            return False
        self.last_report_at = reported_at
        if voltage < 205:
            if self.low_samples == 0:
                self.first_low_at = reported_at
            self.low_samples += 1
        else:
            self.low_samples = 0
            self.first_low_at = None
        self.critical_samples = self.critical_samples + 1 if voltage < 195 else 0
        return True

    def sustained_low(self) -> bool:
        return (self.low_samples >= 2 and self.first_low_at is not None
                and self.last_report_at is not None
                and self.last_report_at - self.first_low_at >= 15)


@dataclass(frozen=True)
class Decision:
    target: float
    cap: float
    mode: str


def decide_current(
    *, voltage: float, average_voltage: float | None,
    sustained_low: bool, current: float, user_max: float, min_current: float,
    losses: int, derate_active: bool, stable_for: float, since_increase: float,
    since_voltage_decrease: float,
    critical_samples: int = 0,
    ramp_up_step: float = 5, moderate_drop_step: float = 5,
    severe_drop_step: float = 10, ramp_interval_seconds: float = 180,
    moderate_drop_interval_seconds: float = AVERAGE_MODERATE_DROP_INTERVAL_SECONDS,
    severe_drop_interval_seconds: float = AVERAGE_SEVERE_DROP_INTERVAL_SECONDS,
) -> Decision:
    """Decide from averaged voltage; preserve raw-voltage emergency protection.

    The average is None until there is enough measured history. It never
    includes 0 V transfer intervals, which are counted independently.
    """
    cap = user_max
    mode = "normal"
    if derate_active or losses >= 3:
        cap = min(cap, min_current)
        mode = "critical_derate"
    elif losses >= 2:
        cap = min(cap, 50.0)
        mode = "derated"

    target = min(current, cap)
    if voltage < 185:
        # Near the hardware undervoltage cutoff: reduce immediately.
        # Never wait for a second sensor report this close to the limit.
        target = min_current
        mode = "emergency_voltage"
    elif voltage < 195:
        # Luxpower reports about every 20 seconds while we poll every 10.
        # One sub-195 V report is not proof of sustained undervoltage.
        # Two *distinct* reports: one guarded reduction. Three: floor.
        if critical_samples >= 3:
            target = min_current
            mode = "low_voltage"
        elif critical_samples >= 2:
            if since_voltage_decrease >= severe_drop_interval_seconds:
                target = max(min_current, target - severe_drop_step)
            mode = "low_voltage"
        else:
            # Do not ramp upward during a single low reading either.
            mode = "voltage_dip"
    elif sustained_low:
        # Below 205 V for at least 20 s, even if average is still high.
        if since_voltage_decrease >= LOW_VOLTAGE_DROP_INTERVAL_SECONDS:
            target = max(min_current, target - severe_drop_step)
        mode = "low_voltage"
    elif average_voltage is None:
        # Startup, after an outage or a sensor gap: no upward adjustments.
        if mode == "normal":
            mode = "averaging"
    elif average_voltage < 205:
        if since_voltage_decrease >= severe_drop_interval_seconds:
            target = max(min_current, target - severe_drop_step)
        mode = "low_voltage"
    elif average_voltage < 215:
        if since_voltage_decrease >= moderate_drop_interval_seconds:
            target = max(min_current, target - moderate_drop_step)
        mode = "low_voltage"
    elif (average_voltage >= 220 and voltage >= 215
          and stable_for >= 120 and since_increase >= ramp_interval_seconds):
        target = min(target + ramp_up_step, cap)

    target = max(min_current, min(target, cap, user_max))
    return Decision(target=target, cap=cap, mode=mode)
