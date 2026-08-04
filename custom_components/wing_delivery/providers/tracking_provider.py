"""Tracking provider: live delivery data from Wing's tracking endpoint.

The Wing tracking page (myorder.wing.com) is an Angular app that reads order
data from a public Google API — no login, just the trackingId from the order
email plus a public web API key baked into Wing's web client:

    GET https://content-wingdelivery.googleapis.com/v2alpha/orders:track
          ?orderTrackingReferenceTrackingId=<trackingId>&key=<publicKey>

`async_fetch` is wired to call that endpoint. `parse_tracking`'s field mapping
is PROVISIONAL: the exact response schema (the JSON keys for status, ETA, and
drone lat/lng) must be confirmed against a live, in-flight order — a delivered
order returns a terminal state without live ETA/position. Until confirmed,
parse_tracking reads defensively and returns None for any field it can't find,
so it never fabricates data. See projects/ha-wing-delivery/phase-2-notes.md.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from ..models import LiveTracking

_LOGGER = logging.getLogger(__name__)

# Wing's public order-tracking API (discovered from the tracking web app).
TRACK_API_URL = "https://content-wingdelivery.googleapis.com/v2alpha/orders:track"
# Public web API key embedded in Wing's tracking app (browser-visible, not a
# secret — the same key drives the app's Maps calls). Rotatable: overridable via
# the constructor if Wing changes it.
DEFAULT_API_KEY = "AIzaSyCHzeCcjPYHmcegQss2V94g2YNlvnEsLc4"
REQUEST_TIMEOUT = ClientTimeout(total=15)


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
    """Map a tracking-endpoint JSON payload to LiveTracking. Tolerant of gaps.

    PROVISIONAL mapping — confirm the real field names against a live order and
    update this function. Missing fields yield None (never fabricated values).
    """
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
    """Fetch live tracking data from Wing's public order-tracking API."""

    def __init__(
        self, session: ClientSession | None, api_key: str = DEFAULT_API_KEY
    ) -> None:
        self._session = session
        self._api_key = api_key

    async def async_fetch(
        self, tracking_url: str | None, tracking_token: str | None
    ) -> LiveTracking | None:
        """Return live tracking data, or None when no live feed is available.

        Needs the trackingId (``tracking_token``, from the order email). Returns
        None on a missing token, missing session, non-200 response, or any
        network/parse error, so the integration degrades to email-only status.
        """
        if not tracking_token or self._session is None:
            return None
        params = {
            "orderTrackingReferenceTrackingId": tracking_token,
            "key": self._api_key,
        }
        try:
            async with self._session.get(
                TRACK_API_URL, params=params, timeout=REQUEST_TIMEOUT
            ) as resp:
                if resp.status != 200:
                    _LOGGER.debug(
                        "Wing tracking API returned HTTP %s", resp.status
                    )
                    return None
                payload = await resp.json()
        except (ClientError, TimeoutError, ValueError) as err:
            _LOGGER.debug("Wing tracking fetch failed: %s", err)
            return None
        if not isinstance(payload, dict):
            return None
        return parse_tracking(payload)
