"""Config flow for Ring Snapshot."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries

from .const import DOMAIN


class RingSnapshotConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ring Snapshot."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Create the Ring Snapshot config entry."""

        if user_input is None:
            return self.async_show_form(step_id="user")

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title="Ring Snapshot", data={})
