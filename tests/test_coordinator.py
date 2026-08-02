import pytest

from custom_components.wing_delivery.coordinator import WingDeliveryCoordinator
from custom_components.wing_delivery.models import EmailOrder, LiveTracking
from custom_components.wing_delivery.const import (
    EVENT_STATUS_CHANGED,
    STATUS_EN_ROUTE,
    STATUS_ARRIVING,
    STATUS_NONE,
)


def test_merge_email_only():
    email = EmailOrder(
        order_id="A1", status=STATUS_EN_ROUTE,
        tracking_url="u", tracking_token="t", last_update=None,
    )
    data = WingDeliveryCoordinator.merge(email, None)
    assert data.status == STATUS_EN_ROUTE
    assert data.order_id == "A1"
    assert data.eta_minutes is None
    assert data.latitude is None


def test_merge_live_overrides_status_and_adds_position():
    email = EmailOrder(
        order_id="A1", status=STATUS_EN_ROUTE,
        tracking_url="u", tracking_token="t", last_update=None,
    )
    live = LiveTracking(
        status=STATUS_ARRIVING, eta_minutes=6,
        latitude=32.9, longitude=-96.9, updated_at=None,
    )
    data = WingDeliveryCoordinator.merge(email, live)
    assert data.status == STATUS_ARRIVING
    assert data.eta_minutes == 6
    assert data.latitude == 32.9


def test_merge_no_order_is_empty():
    data = WingDeliveryCoordinator.merge(None, None)
    assert data.status == STATUS_NONE


class _FakeEmail:
    def __init__(self, order):
        self._order = order

    async def async_fetch_latest(self, hass):
        return self._order


class _FakeTracking:
    def __init__(self, live=None):
        self._live = live

    async def async_fetch(self, url, token):
        return self._live


async def test_update_fires_event_on_status_change(hass):
    order = EmailOrder(
        order_id="A1", status=STATUS_EN_ROUTE,
        tracking_url="u", tracking_token="t", last_update=None,
    )
    coord = WingDeliveryCoordinator(
        hass, _FakeEmail(order), _FakeTracking(), 60
    )
    events = []
    hass.bus.async_listen(EVENT_STATUS_CHANGED, lambda e: events.append(e.data))

    await coord.async_refresh()
    await hass.async_block_till_done()

    assert coord.data.status == STATUS_EN_ROUTE
    assert len(events) == 1
    assert events[0]["new_status"] == STATUS_EN_ROUTE
    assert events[0]["old_status"] == STATUS_NONE
    assert events[0]["order_id"] == "A1"
