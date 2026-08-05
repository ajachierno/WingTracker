import json
from pathlib import Path

from custom_components.wing_delivery.providers.tracking_provider import (
    parse_tracking,
    TrackingProvider,
    TRACK_API_URL,
    TRACK_REFERER,
)
from custom_components.wing_delivery.const import STATUS_DELIVERED, STATUS_EN_ROUTE

FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "wing_tracking_live.json"
)


def test_parse_tracking_maps_live_fields(freezer):
    # Freeze "now" so minutes-until-delivery is deterministic.
    # Fixture ETA is 2026-08-04T23:04:51Z -> 4m51s -> 5 minutes.
    freezer.move_to("2026-08-04T23:00:00+00:00")
    payload = json.loads(FIXTURE.read_text())
    live = parse_tracking(payload)
    assert live.status == STATUS_EN_ROUTE  # packageState IN_TRANSIT
    assert live.eta_minutes == 5
    assert live.latitude == 30.111111
    assert live.longitude == -95.222222
    assert live.updated_at is not None


def test_parse_tracking_delivered_state():
    payload = {
        "order": {
            "orderState": "ALL_PACKAGES_COMPLETE",
            "packages": [{"packageState": "DELIVERED", "packageId": "p1"}],
        },
        "packageMetrics": {"p1": {}},
    }
    live = parse_tracking(payload)
    assert live.status == STATUS_DELIVERED
    assert live.eta_minutes is None
    assert live.latitude is None


def test_parse_tracking_tolerates_missing_fields():
    live = parse_tracking({})
    assert live.status is None
    assert live.eta_minutes is None
    assert live.latitude is None


class _FakeResponse:
    def __init__(self, status: int, payload: dict) -> None:
        self.status = status
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def json(self):
        return self._payload


class _FakeSession:
    """Minimal stand-in for aiohttp.ClientSession.get (returns an async CM)."""

    def __init__(self, status: int, payload: dict) -> None:
        self._status = status
        self._payload = payload
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params or {}, headers or {}))
        return _FakeResponse(self._status, self._payload)


async def test_async_fetch_calls_endpoint_and_parses():
    payload = json.loads(FIXTURE.read_text())
    session = _FakeSession(200, payload)
    provider = TrackingProvider(session, api_key="TESTKEY")

    result = await provider.async_fetch(
        "https://myorder.wing.com/?trackingId=abc123", "abc123"
    )

    assert result is not None
    assert result.status == STATUS_EN_ROUTE
    # Called Wing's real endpoint with the trackingId + key as query params,
    # and the referrer header the (referrer-restricted) API key requires.
    url, params, headers = session.calls[0]
    assert url == TRACK_API_URL
    assert params["orderTrackingReferenceTrackingId"] == "abc123"
    assert params["key"] == "TESTKEY"
    assert headers["Referer"] == TRACK_REFERER


async def test_async_fetch_returns_none_on_error_status():
    session = _FakeSession(404, {})
    provider = TrackingProvider(session)
    assert await provider.async_fetch("u", "abc123") is None


async def test_async_fetch_returns_none_without_token():
    session = _FakeSession(200, {})
    provider = TrackingProvider(session)
    assert await provider.async_fetch("u", None) is None
    assert session.calls == []


async def test_async_fetch_returns_none_without_session():
    provider = TrackingProvider(session=None)
    assert await provider.async_fetch("u", "abc123") is None
