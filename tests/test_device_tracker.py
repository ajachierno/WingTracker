from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD,
)

from custom_components.wing_delivery.const import (
    DOMAIN, CONF_FOLDER, CONF_SENDER, CONF_SCAN_INTERVAL, STATUS_ARRIVING,
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


async def test_tracker_reports_coordinates(hass):
    data = WingDeliveryData(
        status=STATUS_ARRIVING, order_id="A1", eta_minutes=6,
        latitude=32.9101, longitude=-96.95, tracking_url="u", last_update=None,
    )
    await _setup(hass, data)
    state = hass.states.get("device_tracker.wing_drone")
    assert state is not None
    assert state.attributes["latitude"] == 32.9101
    assert state.attributes["longitude"] == -96.95
    # Custom map marker: the drone uses the integration's icon, not initials.
    assert state.attributes["entity_picture"].endswith("brand/icon.png")


async def test_tracker_unavailable_without_position(hass):
    await _setup(hass, WingDeliveryData.empty())
    state = hass.states.get("device_tracker.wing_drone")
    assert state.attributes.get("latitude") is None
