"""Config flow for Taipower AMI."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_CREDENTIAL_FILE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_CREDENTIAL_FILE,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
    MAX_UPDATE_INTERVAL_MINUTES,
    MIN_UPDATE_INTERVAL_MINUTES,
)
from .storage import load_credentials_file


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_CREDENTIAL_FILE,
                default=defaults.get(CONF_CREDENTIAL_FILE, DEFAULT_CREDENTIAL_FILE),
            ): str,
            vol.Required(
                CONF_UPDATE_INTERVAL,
                default=defaults.get(
                    CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MINUTES
                ),
            ): vol.All(
                vol.Coerce(int),
                vol.Range(
                    min=MIN_UPDATE_INTERVAL_MINUTES,
                    max=MAX_UPDATE_INTERVAL_MINUTES,
                ),
            ),
        }
    )


class TaipowerAmiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Taipower AMI config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Create the single supported Taipower AMI entry."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self._async_validate_file(user_input[CONF_CREDENTIAL_FILE])
            except ValueError:
                errors["base"] = "credential_file"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Taipower AMI", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]):
        """Start reauthentication after the browser session expires."""

        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None):
        """Confirm that the Windows companion replaced the handoff file."""

        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        credential_file = str(
            entry.options.get(
                CONF_CREDENTIAL_FILE,
                entry.data.get(CONF_CREDENTIAL_FILE, DEFAULT_CREDENTIAL_FILE),
            )
        )
        if user_input is not None:
            try:
                await self._async_validate_file(credential_file)
            except ValueError:
                errors["base"] = "credential_file"
            else:
                return self.async_update_reload_and_abort(entry)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({}),
            errors=errors,
        )

    async def _async_validate_file(self, relative_path: str) -> None:
        await self.hass.async_add_executor_job(
            load_credentials_file,
            self.hass.config.config_dir,
            relative_path,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow."""

        return TaipowerAmiOptionsFlow()


class TaipowerAmiOptionsFlow(config_entries.OptionsFlowWithReload):
    """Handle polling and handoff-file options."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        defaults = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    load_credentials_file,
                    self.hass.config.config_dir,
                    user_input[CONF_CREDENTIAL_FILE],
                )
            except ValueError:
                errors["base"] = "credential_file"
            else:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(user_input or defaults),
            errors=errors,
        )
