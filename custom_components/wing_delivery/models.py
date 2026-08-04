"""Normalized data models for the Wing Delivery integration."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .const import STATUS_NONE


@dataclass(slots=True)
class EmailOrder:
    """Order details parsed from a Wing order email."""

    order_id: str | None
    status: str
    tracking_url: str | None
    tracking_token: str | None
    last_update: datetime | None
    items: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LiveTracking:
    """Live delivery details from Wing's tracking endpoint."""

    status: str | None
    eta_minutes: int | None
    latitude: float | None
    longitude: float | None
    updated_at: datetime | None


@dataclass(slots=True)
class WingDeliveryData:
    """Merged delivery state consumed by entities."""

    status: str
    order_id: str | None
    eta_minutes: int | None
    latitude: float | None
    longitude: float | None
    tracking_url: str | None
    last_update: datetime | None
    items: list[str] = field(default_factory=list)

    @classmethod
    def empty(cls) -> "WingDeliveryData":
        """Return an inactive state."""
        return cls(
            status=STATUS_NONE,
            order_id=None,
            eta_minutes=None,
            latitude=None,
            longitude=None,
            tracking_url=None,
            last_update=None,
        )
