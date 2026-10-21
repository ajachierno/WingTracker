"""Email provider: discover the active Wing order from mailbox messages."""
from __future__ import annotations

import email
import imaplib
import re
from email.message import Message
from email.utils import parsedate_to_datetime

from homeassistant.core import HomeAssistant
from homeassistant.util.ssl import client_context

from ..const import (
    STATUS_ARRIVING,
    STATUS_DELIVERED,
    STATUS_EN_ROUTE,
    STATUS_ORDERED,
    STATUS_PREPARING,
)
from ..models import EmailOrder

# Status keywords, most-progressed first so the strongest match wins. Wing only
# emails an order receipt (no en-route/delivered mails), so in practice the
# receipt's "reviewing your order" / "thank you for ordering" wins as `ordered`;
# the later states are kept for robustness and for status fed from live tracking.
# NOTE: the terminal-state phrases must be specific. A Wing receipt says "your
# order will be delivered to the location", so a bare "delivered" would falsely
# match an ordered receipt — require past-tense "has been delivered" instead.
_STATUS_KEYWORDS: list[tuple[str, str]] = [
    (STATUS_DELIVERED, "has been delivered"),
    (STATUS_DELIVERED, "was delivered"),
    (STATUS_DELIVERED, "delivered to your"),
    (STATUS_ARRIVING, "arriving"),
    (STATUS_EN_ROUTE, "on the way"),
    (STATUS_EN_ROUTE, "en route"),
    (STATUS_PREPARING, "preparing"),
    (STATUS_ORDERED, "reviewing your order"),
    (STATUS_ORDERED, "thank you for ordering"),
    (STATUS_ORDERED, "order received"),
    (STATUS_ORDERED, "order confirmed"),
]

# Order id: prefer the body "Order ID: <id>" label, then a "#<id>" in the
# subject ("Wing Order Receipt #Ab12Cd34Ef56"), then a legacy "Order <ID>", then
# an "order=" URL param. Ids are mixed-case, so match upper+lower.
_ORDER_ID_RE = re.compile(r"Order ID:\s*([A-Za-z0-9]+)", re.IGNORECASE)
_ORDER_HASH_RE = re.compile(r"#([A-Za-z0-9]{6,})")
_ORDER_RE = re.compile(r"[Oo]rder\s+([A-Z0-9]{4,})")
_ORDER_PARAM_RE = re.compile(r"[?&]order=([A-Za-z0-9]+)")
# Tracking link. Wing's real link (https://myorder.wing.com/?trackingId=...)
# lives ONLY in the HTML part. Match on the trackingId param specifically: a
# looser "contains track" match wrongly grabs asset URLs — notably the email
# logo at .../order_tracking/images/WingLogoEmail.png, which appears first.
# The delimiter-safe class stops the match at HTML quotes/brackets.
_TRACK_URL_RE = re.compile(
    r"https?://[^\s\"'<>]*trackingId=[^\s\"'<>]+", re.IGNORECASE
)
# Token param is `trackingId` on real Wing links; `token` kept as a fallback.
_TOKEN_RE = re.compile(r"[?&](?:trackingId|token)=([A-Za-z0-9_\-]+)", re.IGNORECASE)


def _part_text(msg: Message, content_type: str) -> str:
    """Return the decoded text of the first part matching content_type, or ""."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == content_type:
                payload = part.get_payload(decode=True)
                if payload is not None:
                    return payload.decode(
                        part.get_content_charset() or "utf-8", "replace"
                    )
        return ""
    if msg.get_content_type() == content_type:
        payload = msg.get_payload(decode=True)
        if payload is not None:
            return payload.decode(msg.get_content_charset() or "utf-8", "replace")
    return ""


def _extract_order_id(subject: str, plain: str, tracking_url: str | None) -> str | None:
    text = f"{subject}\n{plain}"
    if (m := _ORDER_ID_RE.search(text)):
        return m.group(1)
    if (m := _ORDER_HASH_RE.search(subject)):
        return m.group(1)
    if (m := _ORDER_RE.search(text)):
        return m.group(1)
    if tracking_url and (m := _ORDER_PARAM_RE.search(tracking_url)):
        return m.group(1)
    return None


def _extract_items(plain: str) -> list[str]:
    """Item names from a Wing receipt: the line after each 'PKGID #<id>'.

    Receipt layout is: `PKGID #<id>`, a blank line, the item description, a
    blank line, then the `$price`. Best-effort; unknown layouts yield [].
    """
    lines = [ln.strip() for ln in plain.splitlines()]
    items: list[str] = []
    for i, line in enumerate(lines):
        if re.match(r"PKGID\s*#", line, re.IGNORECASE):
            for nxt in lines[i + 1:]:
                if not nxt:
                    continue
                if nxt.startswith("$"):
                    break  # hit the price with no description
                items.append(nxt)
                break
    return items


def parse_email(raw: bytes) -> EmailOrder | None:
    """Parse a raw RFC822 message into an EmailOrder, or None if not a Wing order."""
    msg = email.message_from_bytes(raw)
    subject = msg.get("Subject", "")
    plain = _part_text(msg, "text/plain")
    html = _part_text(msg, "text/html")

    # Status and order id come from the subject/plaintext; the tracking link is
    # usually HTML-only, so search HTML first and fall back to plaintext.
    haystack = f"{subject}\n{plain}".lower()
    status = next((s for s, kw in _STATUS_KEYWORDS if kw in haystack), None)
    if status is None:
        return None

    url_match = _TRACK_URL_RE.search(html) or _TRACK_URL_RE.search(plain)
    tracking_url = url_match.group(0) if url_match else None

    order_id = _extract_order_id(subject, plain, tracking_url)

    tracking_token = None
    if tracking_url and (t := _TOKEN_RE.search(tracking_url)):
        tracking_token = t.group(1)

    last_update = None
    if (date_hdr := msg.get("Date")):
        try:
            last_update = parsedate_to_datetime(date_hdr)
        except (TypeError, ValueError):
            last_update = None

    return EmailOrder(
        order_id=order_id,
        status=status,
        tracking_url=tracking_url,
        tracking_token=tracking_token,
        last_update=last_update,
        items=_extract_items(plain),
    )


class InvalidAuth(Exception):
    """The IMAP server rejected the username or password."""


class EmailProvider:
    """Fetch the most recent Wing order email over IMAP."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        folder: str,
        sender: str,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._folder = folder
        self._sender = sender

    async def async_fetch_latest(self, hass: HomeAssistant) -> EmailOrder | None:
        """Return the newest Wing order email as an EmailOrder, or None."""
        return await hass.async_add_executor_job(self._fetch_latest)

    def _connect(self) -> imaplib.IMAP4_SSL:
        """Open a certificate-verified IMAP connection and log in.

        Without an explicit context imaplib uses an unverified one, so the
        password could be read by anyone able to intercept the connection.
        """
        client = imaplib.IMAP4_SSL(
            self._host, self._port, ssl_context=client_context()
        )
        try:
            client.login(self._username, self._password)
        except imaplib.IMAP4.error as err:
            _logout(client)
            raise InvalidAuth(str(err)) from err
        except BaseException:
            _logout(client)
            raise
        return client

    def _fetch_latest(self) -> EmailOrder | None:
        client = self._connect()
        try:
            client.select(self._folder, readonly=True)
            typ, data = client.search(None, "FROM", f'"{self._sender}"')
            if typ != "OK" or not data or not data[0]:
                return None
            ids = data[0].split()
            for msg_id in reversed(ids):  # newest first
                typ, msg_data = client.fetch(msg_id, "(RFC822)")
                if typ != "OK" or not msg_data or not msg_data[0]:
                    continue
                raw = msg_data[0][1]
                order = parse_email(raw)
                if order is not None:
                    return order
            return None
        finally:
            _logout(client)

    def verify_login(self) -> None:
        """Login and logout to validate credentials.

        Raises InvalidAuth for rejected credentials, OSError (including
        ssl.SSLCertVerificationError) for connection problems.
        """
        _logout(self._connect())


def _logout(client: imaplib.IMAP4) -> None:
    try:
        client.logout()
    except Exception:  # noqa: BLE001 - best-effort cleanup
        pass
