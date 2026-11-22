"""UI setup for Grid Charge Guard."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import DOMAIN, CONF_VOLTAGE_ENTITY, CONF_CURRENT_ENTITY


class GridChargeGuardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_CURRENT_ENTITY])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Grid Charge Guard", data=user_input)

        schema = vol.Schema({
            vol.Required(CONF_VOLTAGE_ENTITY): EntitySelector(
                EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_CURRENT_ENTITY): EntitySelector(
                EntitySelectorConfig(domain="number")
            ),
        })
        return self.async_show_form(step_id="user", data_schema=schema)
