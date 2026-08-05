from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD,
)

from custom_components.wing_delivery.const import (
    DOMAIN, CONF_FOLDER, CONF_SENDER, CONF_EMAIL_INTERVAL, CONF_LIVE_INTERVAL,
)

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


async def test_user_flow_invalid_auth(hass):
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
