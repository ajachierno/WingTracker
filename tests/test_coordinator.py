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
        items=["Lasagna"],
    )
    data = WingDeliveryCoordinator.merge(email, None)
    assert data.status == STATUS_EN_ROUTE
    assert data.order_id == "A1"
    assert data.eta_minutes is None
    assert data.latitude is None
    assert data.items == ["Lasagna"]


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
        hass, None, _FakeEmail(order), _FakeTracking(), 60, 20
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


async def test_update_wraps_email_error_as_update_failed(hass):
    from homeassistant.helpers.update_coordinator import UpdateFailed

    class _BoomEmail:
        async def async_fetch_latest(self, hass):
            raise OSError("imap down")

    coord = WingDeliveryCoordinator(hass, None, _BoomEmail(), _FakeTracking(), 60, 20)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()


class _CountingEmail:
    def __init__(self, order):
        self._order = order
        self.calls = 0

    async def async_fetch_latest(self, hass):
        self.calls += 1
        return self._order


class _CountingTracking:
    def __init__(self, live=None):
        self._live = live
        self.calls = 0

    async def async_fetch(self, url, token):
        self.calls += 1
        return self._live


async def test_adaptive_polling_speeds_up_and_throttles_email(hass, freezer):
    from datetime import timedelta

    freezer.move_to("2026-08-04T12:00:00+00:00")
    order = EmailOrder(
        order_id="A1", status=STATUS_EN_ROUTE,
        tracking_url="u", tracking_token="t", last_update=None,
    )
    email = _CountingEmail(order)
    tracking = _CountingTracking()
    coord = WingDeliveryCoordinator(
        hass, None, email, tracking, email_interval=120, live_interval=20
    )

    # First cycle: email + tracking both fetched; active status -> fast interval.
    await coord.async_refresh()
    await hass.async_block_till_done()
    assert email.calls == 1
    assert tracking.calls == 1
    assert coord.update_interval == timedelta(seconds=20)

    # 20s later (< email interval): tracking refreshes, email is throttled.
    freezer.move_to("2026-08-04T12:00:20+00:00")
    await coord.async_refresh()
    await hass.async_block_till_done()
    assert email.calls == 1  # not re-fetched
    assert tracking.calls == 2

    # Past the email interval: email is re-fetched.
    freezer.move_to("2026-08-04T12:02:05+00:00")
    await coord.async_refresh()
    await hass.async_block_till_done()
    assert email.calls == 2
    assert tracking.calls == 3
