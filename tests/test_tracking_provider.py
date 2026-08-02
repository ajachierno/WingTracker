import json
from pathlib import Path

from custom_components.wing_delivery.providers.tracking_provider import (
    parse_tracking,
    TrackingProvider,
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


async def test_provider_stub_returns_none():
    provider = TrackingProvider(session=None)
    result = await provider.async_fetch("https://wing.com/track?x", "tok")
    assert result is None
