"""Diagnostics and optional notifications. No direct Telegram API or secrets."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import time

from .const import (CONF_NOTIFY_ENTITY, DOMAIN, EVENT_NAME,
                    NOTIFY_COOLDOWN_SECONDS)

_LOGGER = logging.getLogger(__name__)


class EventReporter:
    """Emit HA bus events, last-event sensor state, and important notifications."""

    def __init__(self, controller) -> None:
        self.controller = controller
        self.last_event = None
        self._alert_sent_at = {}
        self.recovery_needed = False

    async def emit(self, kind: str, message: str, *, severity: str = "info",
                   notify: bool = False, **details) -> None:
        c = self.controller
        now = time.time()
        event = {
            "event": kind, "message": message, "severity": severity,
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "current_entity": c.current_entity, **details,
        }
        self.last_event = event
        c.hass.bus.async_fire(EVENT_NAME, event)
        c._notify()
        _LOGGER.log(logging.WARNING if severity in ("warning", "error")
                    else logging.INFO, "Grid Charge Guard: %s | %s", kind, message)

        notify_entity = c.entry.options.get(CONF_NOTIFY_ENTITY)
        if not notify or not c.enabled or not notify_entity:
            return
        if kind != "recovered":
            last = self._alert_sent_at.get(kind, 0)
            if now - last < NOTIFY_COOLDOWN_SECONDS:
                return
        # Do not mark an alert as sent until the service call was dispatched.
        try:
            await c.hass.services.async_call(
                "notify", "send_message",
                {"message": f"Grid Charge Guard\n{message}"},
                target={"entity_id": notify_entity},
                blocking=True,
            )
            self._alert_sent_at[kind] = now
            if kind == "recovered":
                self.recovery_needed = False
            else:
                self.recovery_needed = True
        except Exception:
            _LOGGER.exception("Could not send Grid Charge Guard notification to %s", notify_entity)
