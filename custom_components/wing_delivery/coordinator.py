"""Update coordinator for the Wing Delivery integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, EVENT_STATUS_CHANGED, STATUS_NONE
from .models import EmailOrder, LiveTracking, WingDeliveryData
from .providers.email_provider import EmailProvider
from .providers.tracking_provider import TrackingProvider

_LOGGER = logging.getLogger(__name__)


class WingDeliveryCoordinator(DataUpdateCoordinator[WingDeliveryData]):
    """Poll the email and tracking providers and merge their results."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry | None,
        email_provider: EmailProvider,
        tracking_provider: TrackingProvider,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self._email = email_provider
        self._tracking = tracking_provider
        self._last_status = STATUS_NONE

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
        )

    async def _async_update_data(self) -> WingDeliveryData:
        email = await self._email.async_fetch_latest(self.hass)
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
        return data
