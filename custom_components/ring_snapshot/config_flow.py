"""Config flow for Ring Snapshot."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.components import binary_sensor, camera
from homeassistant.core import callback
from homeassistant.helpers import selector
import voluptuous as vol

from .const import (
    ATTR_CAMERA_ENTITY,
    ATTR_DING_ENTITY,
    ATTR_FILENAME,
    ATTR_INTERVAL_SECONDS,
    ATTR_MOTION_ENTITY,
    ATTR_SNAPSHOT_MODE,
    DEFAULT_FILENAME,
    DEFAULT_INTERVAL_SECONDS,
    DOMAIN,
    SNAPSHOT_MODE_DISABLED,
    SNAPSHOT_MODES,
)


def _settings_schema(values: dict[str, Any] | None = None) -> vol.Schema:
    """Return the schema for Ring Snapshot settings."""

    values = values or {}
    camera_entity_field = (
        vol.Required(
            ATTR_CAMERA_ENTITY,
            default=values[ATTR_CAMERA_ENTITY],
        )
        if values.get(ATTR_CAMERA_ENTITY)
        else vol.Required(ATTR_CAMERA_ENTITY)
    )
    motion_entity_field = (
        vol.Optional(
            ATTR_MOTION_ENTITY,
            default=values[ATTR_MOTION_ENTITY],
        )
        if values.get(ATTR_MOTION_ENTITY)
        else vol.Optional(ATTR_MOTION_ENTITY)
    )
    ding_entity_field = (
        vol.Optional(
            ATTR_DING_ENTITY,
            default=values[ATTR_DING_ENTITY],
        )
        if values.get(ATTR_DING_ENTITY)
        else vol.Optional(ATTR_DING_ENTITY)
    )

    return vol.Schema(
        {
            camera_entity_field: selector.EntitySelector(
                selector.EntitySelectorConfig(domain=camera.DOMAIN)
            ),
            vol.Required(
                ATTR_SNAPSHOT_MODE,
                default=values.get(ATTR_SNAPSHOT_MODE, SNAPSHOT_MODE_DISABLED),
            ): vol.In(SNAPSHOT_MODES),
            vol.Required(
                ATTR_FILENAME,
                default=values.get(ATTR_FILENAME, DEFAULT_FILENAME),
            ): str,
            vol.Required(
                ATTR_INTERVAL_SECONDS,
                default=values.get(
                    ATTR_INTERVAL_SECONDS,
                    DEFAULT_INTERVAL_SECONDS,
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=10)),
            motion_entity_field: selector.EntitySelector(
                selector.EntitySelectorConfig(domain=binary_sensor.DOMAIN)
            ),
            ding_entity_field: selector.EntitySelector(
                selector.EntitySelectorConfig(domain=binary_sensor.DOMAIN)
            ),
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
                data_schema=_settings_schema(),
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

        values = dict(self.config_entry.data)
        values.update(self.config_entry.options)

        return self.async_show_form(
            step_id="init",
            data_schema=_settings_schema(values),
        )
