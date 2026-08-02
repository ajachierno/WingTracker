"""Email provider: discover the active Wing order from mailbox messages."""
from __future__ import annotations

import email
import imaplib
import re
from email.message import Message
from email.utils import parsedate_to_datetime

from homeassistant.core import HomeAssistant

from ..const import (
    STATUS_ARRIVING,
    STATUS_DELIVERED,
    STATUS_EN_ROUTE,
    STATUS_ORDERED,
    STATUS_PREPARING,
)
from ..models import EmailOrder

# Ordered most-progressed first so the strongest match wins.
_STATUS_KEYWORDS: list[tuple[str, str]] = [
    (STATUS_DELIVERED, "delivered"),
    (STATUS_ARRIVING, "arriving"),
    (STATUS_EN_ROUTE, "on the way"),
    (STATUS_EN_ROUTE, "en route"),
    (STATUS_PREPARING, "preparing"),
    (STATUS_ORDERED, "order received"),
    (STATUS_ORDERED, "order confirmed"),
]

_ORDER_RE = re.compile(r"[Oo]rder\s+([A-Z0-9]{4,})")
_TRACK_URL_RE = re.compile(r"https?://\S*track\S*", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[?&]token=([A-Za-z0-9_\-]+)")
_ORDER_PARAM_RE = re.compile(r"[?&]order=([A-Za-z0-9]+)")


def _body_text(msg: Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", "replace"
                )
        return ""
    payload = msg.get_payload(decode=True)
    if payload is None:
        return ""
    return payload.decode(msg.get_content_charset() or "utf-8", "replace")


def parse_email(raw: bytes) -> EmailOrder | None:
    """Parse a raw RFC822 message into an EmailOrder, or None if not a Wing order."""
    msg = email.message_from_bytes(raw)
    subject = msg.get("Subject", "")
    body = _body_text(msg)
    haystack = f"{subject}\n{body}".lower()

    status = next(
        (s for s, kw in _STATUS_KEYWORDS if kw in haystack), None
    )
    url_match = _TRACK_URL_RE.search(body)
    if status is None and url_match is None:
        return None

    order_id = None
    if (m := _ORDER_RE.search(f"{subject}\n{body}")):
        order_id = m.group(1)

    tracking_url = url_match.group(0) if url_match else None
    tracking_token = None
    if tracking_url:
        if (t := _TOKEN_RE.search(tracking_url)):
            tracking_token = t.group(1)
        if order_id is None and (o := _ORDER_PARAM_RE.search(tracking_url)):
            order_id = o.group(1)

    last_update = None
    if (date_hdr := msg.get("Date")):
        try:
            last_update = parsedate_to_datetime(date_hdr)
        except (TypeError, ValueError):
            last_update = None

    return EmailOrder(
        order_id=order_id,
        status=status or STATUS_ORDERED,
        tracking_url=tracking_url,
        tracking_token=tracking_token,
        last_update=last_update,
    )


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

    def _fetch_latest(self) -> EmailOrder | None:
        client = imaplib.IMAP4_SSL(self._host, self._port)
        try:
            client.login(self._username, self._password)
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
            try:
                client.logout()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                pass

    def verify_login(self) -> None:
        """Login and logout to validate credentials. Raises on failure."""
        client = imaplib.IMAP4_SSL(self._host, self._port)
        try:
            client.login(self._username, self._password)
        finally:
            try:
                client.logout()
            except Exception:  # noqa: BLE001
                pass
