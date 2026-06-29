"""Config flow for Ring Snapshot."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.components import camera
from homeassistant.core import callback
from homeassistant.helpers import selector
import voluptuous as vol

from .const import ATTR_CAMERA_ENTITY, DOMAIN


def _camera_schema(default_camera_entity: str | None = None) -> vol.Schema:
    """Return the schema for selecting the source camera."""

    suggested_value = (
        {"suggested_value": default_camera_entity} if default_camera_entity else {}
    )
    return vol.Schema(
        {
            vol.Required(
                ATTR_CAMERA_ENTITY,
                **suggested_value,
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=camera.DOMAIN)
            )
        }
    )


class RingSnapshotConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ring Snapshot."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""

        return RingSnapshotOptionsFlow()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Create the Ring Snapshot config entry."""

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=_camera_schema(),
            )

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title="Ring Snapshot", data=user_input)


class RingSnapshotOptionsFlow(config_entries.OptionsFlow):
    """Handle Ring Snapshot options."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage Ring Snapshot options."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        camera_entity = self.config_entry.options.get(
            ATTR_CAMERA_ENTITY,
            self.config_entry.data.get(ATTR_CAMERA_ENTITY),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=_camera_schema(camera_entity),
        )
