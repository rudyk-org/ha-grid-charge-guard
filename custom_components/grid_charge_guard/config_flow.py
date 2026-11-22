"""UI setup for Grid Charge Guard."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import DOMAIN, CONF_VOLTAGE_ENTITY, CONF_CURRENT_ENTITY, CONF_NOTIFY_ENTITY


class GridChargeGuardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return GridChargeGuardOptionsFlow()

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


class GridChargeGuardOptionsFlow(config_entries.OptionsFlow):
    """Optional notifications via an existing Home Assistant notify entity."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # Removing the selection disables notifications. No bot token is stored.
            return self.async_create_entry(title="", data=user_input)

        saved = self.config_entry.options.get(CONF_NOTIFY_ENTITY)
        key = vol.Optional(CONF_NOTIFY_ENTITY, default=saved) if saved else vol.Optional(CONF_NOTIFY_ENTITY)
        schema = vol.Schema({key: EntitySelector(EntitySelectorConfig(domain="notify"))})
        return self.async_show_form(step_id="init", data_schema=schema)
