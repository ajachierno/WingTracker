"""Update coordinator for the Wing Delivery integration."""
from __future__ import annotations

import imaplib
import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import ACTIVE_STATUSES, DOMAIN, EVENT_STATUS_CHANGED, STATUS_NONE
from .models import EmailOrder, LiveTracking, WingDeliveryData
from .providers.email_provider import EmailProvider
from .providers.tracking_provider import TrackingProvider

_LOGGER = logging.getLogger(__name__)


class WingDeliveryCoordinator(DataUpdateCoordinator[WingDeliveryData]):
    """Poll email (for orders) and live tracking (for an active delivery).

    Two independent cadences:
    - the mailbox is checked every ``email_interval`` seconds;
    - while a delivery is active the coordinator ticks every ``live_interval``
      seconds to refresh the ETA and drone position.

    On the fast (live) ticks the email check is still throttled to
    ``email_interval``, so Gmail isn't hit on every fast tick.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry | None,
        email_provider: EmailProvider,
        tracking_provider: TrackingProvider,
        email_interval: int,
        live_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=email_interval),
        )
        self._email = email_provider
        self._tracking = tracking_provider
        self._email_interval = email_interval
        self._live_interval = live_interval
        self._last_status = STATUS_NONE
        self._cached_email: EmailOrder | None = None
        self._last_email_fetch: datetime | None = None

    @staticmethod
    def merge(
        email: EmailOrder | None, live: LiveTracking | None
    ) -> WingDeliveryData:
        """Combine email and live data; live fields win when present."""
        if email is None:
            return WingDeliveryData.empty()
        status = email.status
        if live is not None and live.status:
            status = live.status
        return WingDeliveryData(
            status=status,
            order_id=email.order_id,
            eta_minutes=live.eta_minutes if live else None,
            latitude=live.latitude if live else None,
            longitude=live.longitude if live else None,
            tracking_url=email.tracking_url,
            last_update=email.last_update,
            items=email.items,
        )

    async def _async_fetch_email(self) -> EmailOrder | None:
        """Return the latest order email, re-fetching at most every email interval.

        Between fetches the previous result is reused, so fast live-tracking ticks
        don't hit the mailbox.
        """
        now = dt_util.utcnow()
        due = (
            self._last_email_fetch is None
            or (now - self._last_email_fetch).total_seconds()
            >= self._email_interval
        )
        if due:
            try:
                self._cached_email = await self._email.async_fetch_latest(self.hass)
            except (imaplib.IMAP4.error, OSError) as err:
                raise UpdateFailed(f"Error fetching Wing email: {err}") from err
            self._last_email_fetch = now
        return self._cached_email

    async def _async_update_data(self) -> WingDeliveryData:
        email = await self._async_fetch_email()

        live = None
        if email is not None and email.tracking_token:
            live = await self._tracking.async_fetch(
                email.tracking_url, email.tracking_token
            )
        data = self.merge(email, live)

        if data.status != self._last_status:
            self.hass.bus.async_fire(
                EVENT_STATUS_CHANGED,
                {
                    "order_id": data.order_id,
                    "old_status": self._last_status,
                    "new_status": data.status,
                },
            )
            self._last_status = data.status

        # Tick fast while a delivery is active, slow when idle.
        active = data.status in ACTIVE_STATUSES
        self.update_interval = timedelta(
            seconds=self._live_interval if active else self._email_interval
        )
        return data
