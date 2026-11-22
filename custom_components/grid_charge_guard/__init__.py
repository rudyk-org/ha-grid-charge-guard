"""Grid Charge Guard Home Assistant integration."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .controller import GridChargeController

PLATFORMS = ["switch", "number", "sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    controller = GridChargeController(hass, entry)
    await controller.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    controller.start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    done = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if done:
        controller = hass.data[DOMAIN].pop(entry.entry_id)
        controller.stop()
    return done
