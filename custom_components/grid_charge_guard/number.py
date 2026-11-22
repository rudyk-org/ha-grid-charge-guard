"""The user-set maximum battery-side AC charge current."""
from homeassistant.components.number import NumberEntity
from .const import DOMAIN, MIN_CURRENT, MAX_CURRENT


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([GridChargeMaximum(hass.data[DOMAIN][entry.entry_id], entry)])


class GridChargeMaximum(NumberEntity):
    _attr_name = "Allowed AC charge current"
    _attr_icon = "mdi:current-dc"
    _attr_native_min_value = MIN_CURRENT
    _attr_native_max_value = MAX_CURRENT
    _attr_native_step = 5
    _attr_native_unit_of_measurement = "A"

    def __init__(self, controller, entry):
        self.controller = controller
        self._attr_unique_id = f"{entry.entry_id}_maximum"

    @property
    def native_value(self):
        return self.controller.user_max

    async def async_set_native_value(self, value):
        await self.controller.set_maximum(float(value))

    async def async_added_to_hass(self):
        self.async_on_remove(self.controller.add_listener(self.async_write_ha_state))
