"""Pure decision logic for the Wing Delivery coordinator.

Turns the persistent state plus a freshly-fetched email/live snapshot into the
next entity data, updated state, and poll mode. It has no Home Assistant
dependencies so it can be unit-tested without the HA test harness.

Lifecycle it enforces:
- A delivered order is shown for ``DELIVERED_GRACE`` (5 min), then the entities
  clear and that order id is marked complete.
- A completed order's lingering receipt is ignored (no polling, entities stay
  cleared) until a *new* order id appears.
- Transient tracking failures keep the last live snapshot rather than dropping
  back to the email's coarse "ordered" — no flapping.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .const import ACTIVE_STATUSES, STATUS_DELIVERED, STATUS_NONE
from .models import EmailOrder, LiveTracking, WingDeliveryData

# How long a delivered order stays visible before the entities clear.
DELIVERED_GRACE = timedelta(minutes=5)

MODE_LIVE = "live"    # a delivery is in flight -> poll fast
MODE_GRACE = "grace"  # delivered, counting down before clearing
MODE_IDLE = "idle"    # nothing to show -> poll email slowly


@dataclass(slots=True)
class Decision:
    """Outcome of one update cycle."""

    data: WingDeliveryData
    completed_order_id: str | None
    delivered_at: datetime | None
    mode: str


def merge(email: EmailOrder, live: LiveTracking | None) -> WingDeliveryData:
    """Combine email and live data; live fields win when present."""
    status = email.status
    if live is not None and live.status:
        status = live.status
    return WingDeliveryData(
        status=status,
        order_id=email.order_id,
        eta_minutes=live.eta_minutes if live else None,
        latitude=live.latitude if live else None,
        longitude=live.longitude if live else None,
        tracking_url=email.tracking_url,
        last_update=email.last_update,
        items=email.items,
    )


def resolve(
    prev_data: WingDeliveryData | None,
    completed_order_id: str | None,
    delivered_at: datetime | None,
    email: EmailOrder | None,
    live: LiveTracking | None,
    now: datetime,
    grace: timedelta = DELIVERED_GRACE,
) -> Decision:
    """Compute the next Decision from the current state and a fresh snapshot."""
    # No order, or the receipt of an order we've already finished: stay cleared.
    if email is None or email.order_id == completed_order_id:
        return Decision(WingDeliveryData.empty(), completed_order_id, None, MODE_IDLE)

    # A different order id than we were tracking cancels any prior grace timer.
    if prev_data is None or email.order_id != prev_data.order_id:
        delivered_at = None

    # Delivered: hold the snapshot for the grace period, then clear + complete.
    if delivered_at is not None:
        if now - delivered_at >= grace:
            return Decision(WingDeliveryData.empty(), email.order_id, None, MODE_IDLE)
        return Decision(prev_data, completed_order_id, delivered_at, MODE_GRACE)

    # Active order. On a transient tracking failure keep the last live snapshot
    # rather than dropping to the email's coarse "ordered".
    if (
        live is None
        and prev_data is not None
        and prev_data.order_id == email.order_id
        and prev_data.status != STATUS_NONE
    ):
        data = prev_data
    else:
        data = merge(email, live)

    if data.status == STATUS_DELIVERED:
        # Just delivered: start the grace countdown now.
        return Decision(data, completed_order_id, now, MODE_GRACE)

    mode = MODE_LIVE if data.status in ACTIVE_STATUSES else MODE_IDLE
    return Decision(data, completed_order_id, delivered_at, mode)
