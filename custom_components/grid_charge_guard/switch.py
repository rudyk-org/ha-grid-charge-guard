"""The master auto-regulation switch."""
from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([GridChargeEnabled(hass.data[DOMAIN][entry.entry_id], entry)])


class GridChargeEnabled(SwitchEntity):
    _attr_name = "Adaptive AC charging"
    _attr_icon = "mdi:current-ac"

    def __init__(self, controller, entry):
        self.controller = controller
        self._attr_unique_id = f"{entry.entry_id}_enabled"

    @property
    def is_on(self):
        return self.controller.enabled

    async def async_turn_on(self, **kwargs):
        await self.controller.set_enabled(True)

    async def async_turn_off(self, **kwargs):
        await self.controller.set_enabled(False)

    async def async_added_to_hass(self):
        self.async_on_remove(self.controller.add_listener(self.async_write_ha_state))
