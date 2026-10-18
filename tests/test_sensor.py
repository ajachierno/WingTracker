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

LIVE_DATA = WingDeliveryData(
    status=STATUS_ARRIVING, order_id="A1", eta_minutes=6,
    latitude=32.9, longitude=-96.9, tracking_url="u", last_update=None,
    items=["Test Snack Item"],
)


async def _setup(hass, data):
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA)
    entry.add_to_hass(hass)
    with patch(
        "custom_components.wing_delivery.coordinator.WingDeliveryCoordinator._async_update_data",
        return_value=data,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_status_sensor_state_and_attributes(hass):
    await _setup(hass, LIVE_DATA)
    state = hass.states.get("sensor.wing_delivery_status")
    assert state is not None
    assert state.state == STATUS_ARRIVING
    assert state.attributes["order_id"] == "A1"
    assert state.attributes["items"] == ["Test Snack Item"]
    # The tracking link carries a private trackingId; it must never be exposed.
    assert "tracking_url" not in state.attributes


async def test_eta_sensor_value(hass):
    await _setup(hass, LIVE_DATA)
    state = hass.states.get("sensor.wing_delivery_eta")
    assert state.state == "6"


async def test_eta_sensor_unknown_without_live(hass):
    await _setup(hass, WingDeliveryData.empty())
    state = hass.states.get("sensor.wing_delivery_eta")
    assert state.state in ("unknown", "unavailable", None) or state.state == ""
