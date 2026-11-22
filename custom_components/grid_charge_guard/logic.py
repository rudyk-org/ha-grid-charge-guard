"""Dependency-free charging policy. All current values are battery-side AC charge A."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    target: float
    cap: float
    mode: str


def decide_current(
    *, voltage: float, current: float, user_max: float, min_current: float,
    losses: int, derate_active: bool, stable_for: float, since_increase: float,
) -> Decision:
    """Reduce fast; ramp up only after a continuously stable five-minute period."""
    cap = user_max
    mode = "normal"
    if derate_active or losses >= 3:
        cap = min(cap, min_current)
        mode = "critical_derate"
    elif losses >= 2:
        cap = min(cap, 50.0)
        mode = "derated"

    target = min(current, cap)
    if voltage < 195:
        target = min_current
        mode = "low_voltage"
    elif voltage < 205:
        target = max(min_current, target - 10)
        mode = "low_voltage"
    elif voltage < 215:
        target = max(min_current, target - 5)
        mode = "low_voltage"
    elif voltage >= 220 and stable_for >= 300 and since_increase >= 300:
        target = min(target + 5, cap)

    target = max(min_current, min(target, cap, user_max))
    return Decision(target=target, cap=cap, mode=mode)
