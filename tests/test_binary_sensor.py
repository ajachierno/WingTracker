from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD,
)

from custom_components.wing_delivery.const import (
    DOMAIN, CONF_FOLDER, CONF_SENDER, CONF_SCAN_INTERVAL, STATUS_EN_ROUTE,
)
from custom_components.wing_delivery.models import WingDeliveryData

ENTRY_DATA = {
    CONF_HOST: "imap.example.com", CONF_PORT: 993,
    CONF_USERNAME: "me@example.com", CONF_PASSWORD: "pw",
    CONF_FOLDER: "INBOX", CONF_SENDER: "wing.com", CONF_SCAN_INTERVAL: 120,
}


async def _setup(hass, data):
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA)
    entry.add_to_hass(hass)
    with patch(
        "custom_components.wing_delivery.coordinator.WingDeliveryCoordinator._async_update_data",
        return_value=data,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_active_on_when_en_route(hass):
    data = WingDeliveryData(
        status=STATUS_EN_ROUTE, order_id="A1", eta_minutes=None,
        latitude=None, longitude=None, tracking_url="u", last_update=None,
    )
    await _setup(hass, data)
    assert hass.states.get("binary_sensor.wing_delivery_active").state == "on"


async def test_active_off_when_none(hass):
    await _setup(hass, WingDeliveryData.empty())
    assert hass.states.get("binary_sensor.wing_delivery_active").state == "off"
