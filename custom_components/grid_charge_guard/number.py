"""Native Home Assistant number entities for live Grid Charge Guard settings."""
from homeassistant.components.number import NumberEntity

from .const import DOMAIN, MIN_CURRENT, MAX_CURRENT, SETTING_SPECS


async def async_setup_entry(hass, entry, async_add_entities):
    controller = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        GridChargeMaximum(controller, entry),
        *(GridChargeSetting(controller, entry, field, spec)
          for field, spec in SETTING_SPECS.items()),
    ])


class GridChargeMaximum(NumberEntity):
    _attr_name = "Allowed AC charge current"
    _attr_icon = "mdi:current-dc"
    _attr_native_max_value = MAX_CURRENT
    _attr_native_step = 5
    _attr_native_unit_of_measurement = "A"

    def __init__(self, controller, entry):
        self.controller = controller
        self._attr_unique_id = f"{entry.entry_id}_maximum"

    @property
    def native_min_value(self):
        return max(MIN_CURRENT, self.controller.settings["min_current"])

    @property
    def native_value(self):
        return self.controller.user_max

    async def async_set_native_value(self, value):
        await self.controller.set_maximum(float(value))

    async def async_added_to_hass(self):
        self.async_on_remove(self.controller.add_listener(self.async_write_ha_state))


class GridChargeSetting(NumberEntity):
    """A persistent, live-adjustable setting with standard HA history."""

    def __init__(self, controller, entry, field, spec):
        self.controller = controller
        self.field = field
        self._attr_unique_id = f"{entry.entry_id}_{field}"
        self._attr_name = spec["name"]
        self._attr_icon = spec["icon"]
        self._attr_native_min_value = spec["minimum"]
        self._attr_native_max_value = spec["maximum"]
        self._attr_native_step = spec["step"]
        self._attr_native_unit_of_measurement = spec["unit"]

    @property
    def native_max_value(self):
        if self.field == "min_current":
            return min(SETTING_SPECS[self.field]["maximum"], self.controller.user_max)
        return SETTING_SPECS[self.field]["maximum"]

    @property
    def native_value(self):
        return self.controller.settings[self.field]

    async def async_set_native_value(self, value):
        await self.controller.set_setting(self.field, float(value))

    async def async_added_to_hass(self):
        self.async_on_remove(self.controller.add_listener(self.async_write_ha_state))
