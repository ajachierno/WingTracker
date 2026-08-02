from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD,
)

from custom_components.wing_delivery.const import (
    DOMAIN, CONF_FOLDER, CONF_SENDER, CONF_SCAN_INTERVAL,
)
from custom_components.wing_delivery.models import WingDeliveryData

ENTRY_DATA = {
    CONF_HOST: "imap.example.com",
    CONF_PORT: 993,
    CONF_USERNAME: "me@example.com",
    CONF_PASSWORD: "pw",
    CONF_FOLDER: "INBOX",
    CONF_SENDER: "wing.com",
    CONF_SCAN_INTERVAL: 120,
}


async def test_setup_and_unload_entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA)
    entry.add_to_hass(hass)

    with patch(
        "custom_components.wing_delivery.coordinator.WingDeliveryCoordinator._async_update_data",
        return_value=WingDeliveryData.empty(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.entry_id not in hass.data[DOMAIN]
