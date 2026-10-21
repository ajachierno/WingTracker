"""Config and options flow for Wing Delivery."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_EMAIL_INTERVAL,
    CONF_FOLDER,
    CONF_LIVE_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_SENDER,
    DEFAULT_EMAIL_INTERVAL,
    DEFAULT_FOLDER,
    DEFAULT_LIVE_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SENDER,
    DOMAIN,
)
from .providers.email_provider import EmailProvider, InvalidAuth


def _user_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_FOLDER, default=DEFAULT_FOLDER): str,
            vol.Required(CONF_SENDER, default=DEFAULT_SENDER): str,
            vol.Required(
                CONF_EMAIL_INTERVAL, default=DEFAULT_EMAIL_INTERVAL
            ): int,
            vol.Required(
                CONF_LIVE_INTERVAL, default=DEFAULT_LIVE_INTERVAL
            ): int,
        }
    )


async def _async_validate(
    hass: HomeAssistant, data: Mapping[str, Any]
) -> dict[str, str]:
    """Try a real login with these settings; return form errors (empty = ok)."""
    provider = EmailProvider(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        folder=data[CONF_FOLDER],
        sender=data[CONF_SENDER],
    )
    try:
        await hass.async_add_executor_job(provider.verify_login)
    except InvalidAuth:
        return {"base": "invalid_auth"}
    except Exception:  # noqa: BLE001 - any other IMAP/TLS failure
        return {"base": "cannot_connect"}
    return {}


class WingDeliveryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI setup flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()
            errors = await _async_validate(self.hass, user_input)
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )
        return self.async_show_form(
            step_id="user", data_schema=_user_schema(), errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth after the mailbox rejected the stored password."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new password and check it before saving."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            errors = await _async_validate(self.hass, data)
            if not errors:
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> "WingDeliveryOptionsFlow":
        return WingDeliveryOptionsFlow(config_entry)


class WingDeliveryOptionsFlow(OptionsFlow):
    """Allow changing the poll interval."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        data = self._entry.data
        opts = self._entry.options
        email_default = opts.get(
            CONF_EMAIL_INTERVAL,
            data.get(
                CONF_EMAIL_INTERVAL,
                data.get(CONF_SCAN_INTERVAL, DEFAULT_EMAIL_INTERVAL),
            ),
        )
        live_default = opts.get(
            CONF_LIVE_INTERVAL, data.get(CONF_LIVE_INTERVAL, DEFAULT_LIVE_INTERVAL)
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_EMAIL_INTERVAL, default=email_default
                    ): int,
                    vol.Required(
                        CONF_LIVE_INTERVAL, default=live_default
                    ): int,
                }
            ),
        )
