"""The Wing Delivery integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_EMAIL_INTERVAL,
    CONF_FOLDER,
    CONF_LIVE_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_SENDER,
    DEFAULT_EMAIL_INTERVAL,
    DEFAULT_LIVE_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import WingDeliveryCoordinator
from .providers.email_provider import EmailProvider
from .providers.tracking_provider import TrackingProvider


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Wing Delivery from a config entry."""
    email_provider = EmailProvider(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        folder=entry.data[CONF_FOLDER],
        sender=entry.data[CONF_SENDER],
    )
    tracking_provider = TrackingProvider(async_get_clientsession(hass))
    # email interval falls back to the legacy single "scan_interval" for entries
    # created before the split; options override data.
    email_interval = entry.options.get(
        CONF_EMAIL_INTERVAL,
        entry.data.get(
            CONF_EMAIL_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_EMAIL_INTERVAL),
        ),
    )
    live_interval = entry.options.get(
        CONF_LIVE_INTERVAL,
        entry.data.get(CONF_LIVE_INTERVAL, DEFAULT_LIVE_INTERVAL),
    )
    coordinator = WingDeliveryCoordinator(
        hass, entry, email_provider, tracking_provider, email_interval, live_interval
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
