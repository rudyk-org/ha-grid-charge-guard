"""Grid Charge Guard Home Assistant integration."""
from __future__ import annotations

from pathlib import Path
from homeassistant.core import HomeAssistant
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .controller import GridChargeController

PLATFORMS = ["switch", "number", "sensor"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Serve the bundled dashboard card; add it as a Lovelace resource once."""
    path = Path(__file__).parent / "frontend" / "grid-charge-guard-card.js"
    await hass.http.async_register_static_paths([
        StaticPathConfig("/grid-charge-guard/card.js", str(path), False)
    ])
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    controller = GridChargeController(hass, entry)
    await controller.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    controller.start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    done = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if done:
        controller = hass.data[DOMAIN].pop(entry.entry_id)
        controller.stop()
    return done


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
