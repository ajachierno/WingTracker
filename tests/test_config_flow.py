from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD,
)

from custom_components.wing_delivery.const import (
    DOMAIN, CONF_FOLDER, CONF_SENDER, CONF_EMAIL_INTERVAL, CONF_LIVE_INTERVAL,
)
from custom_components.wing_delivery.providers.email_provider import InvalidAuth

VERIFY = "custom_components.wing_delivery.config_flow.EmailProvider.verify_login"

USER_INPUT = {
    CONF_HOST: "imap.example.com",
    CONF_PORT: 993,
    CONF_USERNAME: "me@example.com",
    CONF_PASSWORD: "app-password",
    CONF_FOLDER: "INBOX",
    CONF_SENDER: "wing.com",
    CONF_EMAIL_INTERVAL: 120,
    CONF_LIVE_INTERVAL: 20,
}


async def test_user_flow_success(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"

    with patch(
        "custom_components.wing_delivery.config_flow.EmailProvider.verify_login",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result2["type"] == "create_entry"
    assert result2["title"] == "me@example.com"
    assert result2["data"][CONF_HOST] == "imap.example.com"


async def test_user_flow_cannot_connect(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "custom_components.wing_delivery.config_flow.EmailProvider.verify_login",
        side_effect=OSError("login failed"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_flow_invalid_auth(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(VERIFY, side_effect=InvalidAuth("AUTHENTICATIONFAILED")):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth_updates_password(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="me@example.com", data=USER_INPUT
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

    with patch(VERIFY, side_effect=InvalidAuth("nope")):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "still-wrong"}
        )
    assert result2["errors"] == {"base": "invalid_auth"}

    with patch(VERIFY, return_value=None), patch(
        "custom_components.wing_delivery.async_setup_entry", return_value=True
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "new-app-password"}
        )
    assert result3["type"] == "abort"
    assert result3["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new-app-password"
    assert entry.data[CONF_HOST] == "imap.example.com"
