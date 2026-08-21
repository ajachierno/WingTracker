from datetime import datetime, timedelta

from custom_components.wing_delivery.state import (
    resolve,
    merge,
    MODE_LIVE,
    MODE_GRACE,
    MODE_IDLE,
)
from custom_components.wing_delivery.models import EmailOrder, LiveTracking, WingDeliveryData
from custom_components.wing_delivery.const import (
    STATUS_NONE,
    STATUS_ORDERED,
    STATUS_EN_ROUTE,
    STATUS_DELIVERED,
)

NOW = datetime(2026, 8, 21, 12, 0, 0)


def _order(oid="A1", status=STATUS_ORDERED, token="tok"):
    return EmailOrder(
        order_id=oid, status=status, tracking_url="https://myorder.wing.com/?trackingId=%s" % token,
        tracking_token=token, last_update=None, items=["Cookies"],
    )


def _live(status=STATUS_EN_ROUTE, eta=5, lat=1.0, lng=2.0):
    return LiveTracking(status=status, eta_minutes=eta, latitude=lat, longitude=lng, updated_at=None)


def test_no_email_is_idle_and_cleared():
    d = resolve(None, None, None, None, None, NOW)
    assert d.data.status == STATUS_NONE
    assert d.mode == MODE_IDLE
    assert d.delivered_at is None


def test_completed_order_receipt_stays_cleared():
    # The delivered order's receipt lingers forever; it must not re-activate.
    d = resolve(WingDeliveryData.empty(), "A1", None, _order("A1"), None, NOW)
    assert d.data.status == STATUS_NONE
    assert d.mode == MODE_IDLE
    assert d.completed_order_id == "A1"


def test_active_order_uses_live_status():
    d = resolve(WingDeliveryData.empty(), None, None, _order("A1"), _live(STATUS_EN_ROUTE), NOW)
    assert d.data.status == STATUS_EN_ROUTE
    assert d.data.order_id == "A1"
    assert d.data.eta_minutes == 5
    assert d.mode == MODE_LIVE


def test_transient_tracking_failure_keeps_live_snapshot():
    # live=None (fetch hiccup) must NOT drop back to the email's coarse "ordered".
    prev = merge(_order("A1"), _live(STATUS_EN_ROUTE, eta=4))
    d = resolve(prev, None, None, _order("A1"), None, NOW)
    assert d.data.status == STATUS_EN_ROUTE
    assert d.data.eta_minutes == 4
    assert d.mode == MODE_LIVE


def test_tracking_failure_with_no_prior_falls_back_to_email():
    d = resolve(WingDeliveryData.empty(), None, None, _order("A1", STATUS_ORDERED), None, NOW)
    assert d.data.status == STATUS_ORDERED
    assert d.mode == MODE_LIVE


def test_delivered_starts_grace():
    prev = merge(_order("A1"), _live(STATUS_EN_ROUTE))
    d = resolve(prev, None, None, _order("A1"), _live(STATUS_DELIVERED), NOW)
    assert d.data.status == STATUS_DELIVERED
    assert d.delivered_at == NOW
    assert d.mode == MODE_GRACE


def test_within_grace_holds_delivered():
    prev = merge(_order("A1"), _live(STATUS_DELIVERED))
    started = NOW - timedelta(minutes=2)
    d = resolve(prev, None, started, _order("A1"), None, NOW)
    assert d.data.status == STATUS_DELIVERED
    assert d.delivered_at == started
    assert d.mode == MODE_GRACE


def test_grace_elapsed_clears_and_marks_complete():
    prev = merge(_order("A1"), _live(STATUS_DELIVERED))
    started = NOW - timedelta(minutes=6)
    d = resolve(prev, None, started, _order("A1"), None, NOW)
    assert d.data.status == STATUS_NONE
    assert d.completed_order_id == "A1"
    assert d.delivered_at is None
    assert d.mode == MODE_IDLE


def test_new_order_after_completion_reactivates():
    d = resolve(WingDeliveryData.empty(), "A1", None, _order("B2"), _live(STATUS_EN_ROUTE), NOW)
    assert d.data.status == STATUS_EN_ROUTE
    assert d.data.order_id == "B2"
    assert d.mode == MODE_LIVE


def test_new_order_cancels_prior_grace():
    prev = merge(_order("A1"), _live(STATUS_DELIVERED))
    started = NOW - timedelta(minutes=1)
    d = resolve(prev, None, started, _order("B2"), _live(STATUS_EN_ROUTE), NOW)
    assert d.data.order_id == "B2"
    assert d.data.status == STATUS_EN_ROUTE
    assert d.delivered_at is None
    assert d.mode == MODE_LIVE
