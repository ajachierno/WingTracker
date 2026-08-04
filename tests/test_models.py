from custom_components.wing_delivery.models import (
    EmailOrder,
    LiveTracking,
    WingDeliveryData,
)
from custom_components.wing_delivery.const import STATUS_NONE


def test_empty_data_has_none_status():
    data = WingDeliveryData.empty()
    assert data.status == STATUS_NONE
    assert data.order_id is None
    assert data.eta_minutes is None
    assert data.latitude is None
    assert data.longitude is None
    assert data.items == []


def test_dataclasses_construct():
    email = EmailOrder(
        order_id="A1",
        status="en_route",
        tracking_url="https://track/x",
        tracking_token="tok",
        last_update=None,
    )
    live = LiveTracking(
        status="arriving",
        eta_minutes=6,
        latitude=32.9,
        longitude=-96.9,
        updated_at=None,
    )
    assert email.status == "en_route"
    assert live.eta_minutes == 6
