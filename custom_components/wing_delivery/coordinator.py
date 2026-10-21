"""Update coordinator for the Wing Delivery integration."""
from __future__ import annotations

import imaplib
import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVENT_STATUS_CHANGED, STATUS_DELIVERED, STATUS_NONE
from .models import EmailOrder, LiveTracking, WingDeliveryData
from .providers.email_provider import EmailProvider, InvalidAuth
from .providers.tracking_provider import TrackingProvider
from .state import MODE_GRACE, MODE_LIVE, merge as _merge, resolve

_LOGGER = logging.getLogger(__name__)

# How often to re-check the delivered-order grace countdown.
_GRACE_POLL = 60  # seconds

STORAGE_VERSION = 1


def storage_key(entry_id: str) -> str:
    """Storage key for the per-entry record of the last delivered order."""
    return f"{DOMAIN}.{entry_id}"


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
        # Lifecycle state (see state.resolve): the last order we finished, and
        # when the current order first showed delivered.
        self._completed_order_id: str | None = None
        self._delivered_at: datetime | None = None
        # The last delivered order id is saved to disk so a restart doesn't
        # replay its lingering receipt as a fresh "delivered" (which would
        # re-fire status-change events and any automations watching it).
        self._store: Store[dict[str, str]] | None = (
            Store(hass, STORAGE_VERSION, storage_key(config_entry.entry_id))
            if config_entry is not None
            else None
        )
        self._saved_order_id: str | None = None

    async def _async_setup(self) -> None:
        """Restore the last delivered order before the first refresh."""
        if self._store is None:
            return
        stored = await self._store.async_load()
        if stored:
            self._saved_order_id = stored.get("delivered_order_id")
            self._completed_order_id = self._saved_order_id

    @staticmethod
    def merge(
        email: EmailOrder | None, live: LiveTracking | None
    ) -> WingDeliveryData:
        """Combine email and live data; live fields win when present."""
        if email is None:
            return WingDeliveryData.empty()
        return _merge(email, live)

    async def _async_fetch_email(self) -> EmailOrder | None:
        """Return the latest order email, re-fetching at most every email interval.

        Between fetches the previous result is reused, so fast live-tracking ticks
        don't hit the mailbox. Raises on IMAP/OS errors; the caller decides how to
        handle them.
        """
        now = dt_util.utcnow()
        due = (
            self._last_email_fetch is None
            or (now - self._last_email_fetch).total_seconds()
            >= self._email_interval
        )
        if due:
            self._cached_email = await self._email.async_fetch_latest(self.hass)
            self._last_email_fetch = now
        return self._cached_email

    async def _async_update_data(self) -> WingDeliveryData:
        try:
            email = await self._async_fetch_email()
        except InvalidAuth as err:
            # A rejected password won't fix itself. Fail loudly so HA starts
            # the reauth flow instead of silently keeping stale state.
            raise ConfigEntryAuthFailed(
                f"Mailbox login rejected: {err}"
            ) from err
        except (imaplib.IMAP4.error, OSError) as err:
            # First-ever fetch failing means setup can't validate -> surface it.
            # A later transient hiccup must NOT flap entities to "unavailable":
            # keep the last state instead.
            if self.data is None:
                raise UpdateFailed(f"Error fetching Wing email: {err}") from err
            _LOGGER.debug("Wing email fetch failed; keeping last state: %s", err)
            return self.data

        # Only hit the tracking API for a current order that isn't already
        # delivered (in its grace countdown) — a completed/delivered order is
        # never re-polled, which is what stopped the flapping.
        in_grace_same_order = (
            self._delivered_at is not None
            and self.data is not None
            and email is not None
            and self.data.order_id == email.order_id
        )
        need_live = (
            email is not None
            and email.order_id != self._completed_order_id
            and bool(email.tracking_token)
            and not in_grace_same_order
        )
        live = (
            await self._tracking.async_fetch(email.tracking_url, email.tracking_token)
            if need_live
            else None
        )

        decision = resolve(
            self.data,
            self._completed_order_id,
            self._delivered_at,
            email,
            live,
            dt_util.utcnow(),
        )
        self._completed_order_id = decision.completed_order_id
        self._delivered_at = decision.delivered_at
        data = decision.data

        if (
            self._store is not None
            and data.status == STATUS_DELIVERED
            and data.order_id is not None
            and data.order_id != self._saved_order_id
        ):
            self._saved_order_id = data.order_id
            await self._store.async_save({"delivered_order_id": data.order_id})

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

        if decision.mode == MODE_LIVE:
            interval = self._live_interval
        elif decision.mode == MODE_GRACE:
            interval = _GRACE_POLL
        else:
            interval = self._email_interval
        self.update_interval = timedelta(seconds=interval)
        return data
