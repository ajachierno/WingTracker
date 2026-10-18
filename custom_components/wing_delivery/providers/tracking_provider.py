"""Tracking provider: live delivery data from Wing's tracking endpoint.

The Wing tracking page (myorder.wing.com) is an Angular app that reads order
data from a public Google API — no login, just the trackingId from the order
email plus a public web API key baked into Wing's web client:

    GET https://content-wingdelivery.googleapis.com/v2alpha/orders:track
          ?orderTrackingReferenceTrackingId=<trackingId>&key=<publicKey>

`async_fetch` calls that endpoint and `parse_tracking` maps the response
(confirmed against a live order): package state -> status, the estimated
delivery time -> minutes remaining, and the aircraft telemetry -> drone
position. It reads defensively and returns None for any field it can't find,
so it never fabricates data.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout
from homeassistant.util import dt as dt_util

from ..const import (
    STATUS_ARRIVING,
    STATUS_DELIVERED,
    STATUS_EN_ROUTE,
    STATUS_PREPARING,
)
from ..models import LiveTracking

_LOGGER = logging.getLogger(__name__)

# Wing's public order-tracking API (discovered from the tracking web app).
TRACK_API_URL = "https://content-wingdelivery.googleapis.com/v2alpha/orders:track"
# Public web API key embedded in Wing's tracking app (browser-visible, not a
# secret — the same key drives the app's Maps calls). Rotatable: overridable via
# the constructor if Wing changes it.
DEFAULT_API_KEY = "AIzaSyCHzeCcjPYHmcegQss2V94g2YNlvnEsLc4"
# The key is HTTP-referrer-restricted to the tracking site: without this header
# Google returns 403 API_KEY_HTTP_REFERRER_BLOCKED. A browser sends it for free;
# our request must set it explicitly.
TRACK_REFERER = "https://myorder.wing.com/"
REQUEST_TIMEOUT = ClientTimeout(total=15)


# Wing package/order state -> our status vocabulary. Confirmed from a live
# delivery on 2026-08-04: a package goes packageState IN_TRANSIT (airborne) ->
# DELIVERED, with orderState PACKAGES_PENDING_LOAD -> ALL_PACKAGES_COMPLETE.
# The pre-flight and "arriving" strings are best-effort until observed; unknown
# states leave status as None so the email's "ordered" stands.
_STATE_MAP: dict[str, str] = {
    "DELIVERED": STATUS_DELIVERED,
    "ALL_PACKAGES_COMPLETE": STATUS_DELIVERED,
    "COMPLETED": STATUS_DELIVERED,
    "ARRIVING": STATUS_ARRIVING,
    "DELIVERING": STATUS_ARRIVING,
    "ON_FINAL_APPROACH": STATUS_ARRIVING,
    "IN_TRANSIT": STATUS_EN_ROUTE,
    "OUT_FOR_DELIVERY": STATUS_EN_ROUTE,
    "PACKED": STATUS_PREPARING,
    "LOADING": STATUS_PREPARING,
    "PENDING_LOAD": STATUS_PREPARING,
    "PACKAGES_PENDING_LOAD": STATUS_PREPARING,
    "PENDING": STATUS_PREPARING,
}


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _map_state(state: Any) -> str | None:
    if not isinstance(state, str):
        return None
    return _STATE_MAP.get(state.upper())


def _eta_minutes(iso: Any) -> int | None:
    """Minutes from now until an ISO delivery-time string; clamped to >= 0."""
    if not isinstance(iso, str):
        return None
    try:
        eta = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    delta = (eta - dt_util.utcnow()).total_seconds()
    return max(0, round(delta / 60))


def parse_tracking(payload: dict[str, Any]) -> LiveTracking:
    """Map Wing's orders:track JSON to LiveTracking. Tolerant of missing fields.

    Real shape (confirmed from a live order):
      order.packages[].packageState        -> status (IN_TRANSIT/DELIVERED/...)
      packageMetrics[id].estimatedPackageDeliveryTime (ISO) -> eta_minutes
      packageMetrics[id].aircraftTelemetry.aircraftLocation.{latitude,longitude} -> position
    Uses the first package in the order. Missing data yields None, never guesses.
    """
    order = payload.get("order") or {}
    packages = order.get("packages") or []
    metrics = payload.get("packageMetrics") or {}

    package = packages[0] if packages else {}
    package_id = package.get("packageId")
    pkg_metrics = (metrics.get(package_id) if package_id else None) or {}
    if not pkg_metrics and metrics:
        pkg_metrics = next(iter(metrics.values()))

    status = _map_state(package.get("packageState")) or _map_state(
        order.get("orderState")
    )

    eta_iso = (
        pkg_metrics.get("estimatedPackageDeliveryTime")
        or pkg_metrics.get("packageDeliveryEstimateTime")
        or package.get("estimatedDeliveryTime")
    )

    location = (pkg_metrics.get("aircraftTelemetry") or {}).get(
        "aircraftLocation"
    ) or {}

    return LiveTracking(
        status=status,
        eta_minutes=_eta_minutes(eta_iso),
        latitude=_as_float(location.get("latitude")),
        longitude=_as_float(location.get("longitude")),
        updated_at=dt_util.utcnow(),
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
                TRACK_API_URL,
                params=params,
                headers={"Referer": TRACK_REFERER},
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status != 200:
                    _LOGGER.debug(
                        "Wing tracking API returned HTTP %s", resp.status
                    )
                    return None
                payload = await resp.json()
        except (ClientError, TimeoutError, ValueError) as err:
            # Log the error type only: aiohttp errors can include the request
            # URL, and its query string carries the private trackingId.
            _LOGGER.debug("Wing tracking fetch failed: %s", type(err).__name__)
            return None
        if not isinstance(payload, dict):
            return None
        return parse_tracking(payload)
