from pathlib import Path

from custom_components.wing_delivery.providers.email_provider import parse_email
from custom_components.wing_delivery.const import STATUS_EN_ROUTE

FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "wing_order_en_route.eml"
)


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
