from pathlib import Path

from custom_components.wing_delivery.providers.email_provider import parse_email
from custom_components.wing_delivery.const import STATUS_EN_ROUTE, STATUS_ORDERED

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE = FIXTURE_DIR / "wing_order_en_route.eml"
RECEIPT_FIXTURE = FIXTURE_DIR / "wing_receipt.eml"


def test_parse_email_extracts_order_and_token():
    order = parse_email(FIXTURE.read_bytes())
    assert order is not None
    assert order.order_id == "A1B2C3"
    assert order.status == STATUS_EN_ROUTE
    assert order.tracking_token == "trk_abc123"
    assert order.tracking_url.startswith("https://wing.com/track")


def test_parse_email_returns_none_for_unrelated_mail():
    raw = b"From: someone@example.com\r\nSubject: lunch?\r\n\r\nfree at noon?"
    assert parse_email(raw) is None


def test_parse_email_returns_none_when_no_status_keyword():
    raw = (
        b"From: Wing Orders <no-reply@wing.com>\r\n"
        b"Subject: Your Wing receipt\r\n\r\n"
        b"Thanks. Track: https://wing.com/track?order=Z9&token=trk_z9\r\n"
    )
    assert parse_email(raw) is None


def test_parse_email_real_wing_receipt_format():
    """Matches the real Wing receipt: sender wing.google.com, HTML-only tracking
    link with a trackingId param, mixed-case order id, "reviewing" wording."""
    order = parse_email(RECEIPT_FIXTURE.read_bytes())
    assert order is not None
    assert order.status == STATUS_ORDERED
    assert order.order_id == "TESTORD123ABC"
    assert order.tracking_token == "faketrk123ABC"
    assert order.tracking_url == "https://myorder.wing.com/?trackingId=faketrk123ABC"
