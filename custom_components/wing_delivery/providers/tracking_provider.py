"""Tracking provider: live delivery data from Wing's tracking endpoint.

PHASE 1: interface is frozen; async_fetch returns None (no verified endpoint).
PHASE 2: implement async_fetch against real captured traffic; parse_tracking()
already maps the expected shape and is covered by tests.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from aiohttp import ClientSession

from ..models import LiveTracking


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_tracking(payload: dict[str, Any]) -> LiveTracking:
    """Map a tracking-endpoint JSON payload to LiveTracking. Tolerant of gaps."""
    location = payload.get("location") or {}
    updated_raw = payload.get("updated_at")
    updated_at: datetime | None = None
    if isinstance(updated_raw, str):
        try:
            updated_at = datetime.fromisoformat(updated_raw)
        except ValueError:
            updated_at = None
    return LiveTracking(
        status=payload.get("status"),
        eta_minutes=_as_int(payload.get("eta_minutes")),
        latitude=_as_float(location.get("lat")),
        longitude=_as_float(location.get("lng")),
        updated_at=updated_at,
    )


class TrackingProvider:
    """Fetch live tracking data. Phase-1 stub returns None."""

    def __init__(self, session: ClientSession | None) -> None:
        self._session = session

    async def async_fetch(
        self, tracking_url: str | None, tracking_token: str | None
    ) -> LiveTracking | None:
        """Return live tracking data, or None when no live feed is available.

        Phase 2 replaces the body below with a real request to the tracking
        endpoint and `return parse_tracking(await resp.json())`.
        """
        return None
