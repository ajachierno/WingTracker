import json
from pathlib import Path

from custom_components.wing_delivery.providers.tracking_provider import (
    parse_tracking,
    TrackingProvider,
    TRACK_API_URL,
)

FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "wing_tracking_live.json"
)


def test_parse_tracking_maps_fields():
    payload = json.loads(FIXTURE.read_text())
    live = parse_tracking(payload)
    assert live.status == "arriving"
    assert live.eta_minutes == 6
    assert live.latitude == 32.9101
    assert live.longitude == -96.9500
    assert live.updated_at is not None


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

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params or {}))
        return _FakeResponse(self._status, self._payload)


async def test_async_fetch_calls_endpoint_and_parses():
    payload = json.loads(FIXTURE.read_text())
    session = _FakeSession(200, payload)
    provider = TrackingProvider(session, api_key="TESTKEY")

    result = await provider.async_fetch(
        "https://myorder.wing.com/?trackingId=abc123", "abc123"
    )

    assert result is not None
    assert result.status == "arriving"
    # Called Wing's real endpoint with the trackingId + key as query params.
    url, params = session.calls[0]
    assert url == TRACK_API_URL
    assert params["orderTrackingReferenceTrackingId"] == "abc123"
    assert params["key"] == "TESTKEY"


async def test_async_fetch_returns_none_on_error_status():
    session = _FakeSession(404, {})
    provider = TrackingProvider(session)
    assert await provider.async_fetch("u", "abc123") is None


async def test_async_fetch_returns_none_without_token():
    session = _FakeSession(200, {"status": "arriving"})
    provider = TrackingProvider(session)
    assert await provider.async_fetch("u", None) is None
    # No HTTP call attempted when there's no trackingId.
    assert session.calls == []


async def test_async_fetch_returns_none_without_session():
    provider = TrackingProvider(session=None)
    assert await provider.async_fetch("u", "abc123") is None
