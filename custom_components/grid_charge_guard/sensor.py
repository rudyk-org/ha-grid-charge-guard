"""Read-only state for dashboards and troubleshooting."""
from homeassistant.components.sensor import SensorEntity
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        GuardSensor(c, entry, "Grid charge mode", "mode", "mdi:shield-check"),
        GuardSensor(c, entry, "Grid losses 15m", "losses", "mdi:transmission-tower-off"),
        GuardSensor(c, entry, "Adaptive target current", "target", "mdi:current-dc"),
        GuardSensor(c, entry, "Grid charge last event", "last_event", "mdi:history"),
        GuardSensor(c, entry, "Grid voltage average 3m", "voltage_average", "mdi:chart-bell-curve"),
    ])


class GuardSensor(SensorEntity):
    def __init__(self, controller, entry, name, field, icon):
        self.controller = controller
        self.field = field
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{field}"
        if field == "target":
            self._attr_native_unit_of_measurement = "A"
        elif field == "voltage_average":
            self._attr_native_unit_of_measurement = "V"

    @property
    def native_value(self):
        c = self.controller
        return {"mode": c.mode, "losses": c.losses, "target": c.target,
                "last_event": (c.reporter.last_event or {}).get("event"),
                "voltage_average": c.average_voltage}[self.field]

    @property
    def extra_state_attributes(self):
        if self.field == "last_event":
            return c if (c := self.controller.reporter.last_event) else {}
        return None

    async def async_added_to_hass(self):
        self.async_on_remove(self.controller.add_listener(self.async_write_ha_state))
