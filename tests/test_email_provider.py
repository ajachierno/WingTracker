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
    assert order.tracking_url.startswith("https://myorder.wing.com")


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
    assert order.items == ["Test Snack Item, Family Pack"]


def _provider():
    from custom_components.wing_delivery.providers.email_provider import EmailProvider

    return EmailProvider(
        host="imap.example.com", port=993, username="me@example.com",
        password="pw", folder="INBOX", sender="wing.com",
    )


def test_imap_connection_verifies_certificate():
    """The IMAP socket must use a context that checks the cert and hostname."""
    import ssl
    from unittest.mock import MagicMock, patch

    with patch(
        "custom_components.wing_delivery.providers.email_provider.imaplib.IMAP4_SSL"
    ) as imap_ssl:
        imap_ssl.return_value = MagicMock()
        _provider().verify_login()

    ctx = imap_ssl.call_args.kwargs["ssl_context"]
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


def test_fetch_uses_verified_connection():
    import ssl
    from unittest.mock import MagicMock, patch

    client = MagicMock()
    client.search.return_value = ("OK", [b""])
    with patch(
        "custom_components.wing_delivery.providers.email_provider.imaplib.IMAP4_SSL",
        return_value=client,
    ) as imap_ssl:
        assert _provider()._fetch_latest() is None

    assert imap_ssl.call_args.kwargs["ssl_context"].verify_mode == ssl.CERT_REQUIRED
    client.logout.assert_called_once()


def test_rejected_login_raises_invalid_auth():
    import imaplib
    from unittest.mock import MagicMock, patch

    import pytest

    from custom_components.wing_delivery.providers.email_provider import InvalidAuth

    client = MagicMock()
    client.login.side_effect = imaplib.IMAP4.error("AUTHENTICATIONFAILED")
    with patch(
        "custom_components.wing_delivery.providers.email_provider.imaplib.IMAP4_SSL",
        return_value=client,
    ):
        with pytest.raises(InvalidAuth):
            _provider().verify_login()
    client.logout.assert_called_once()
