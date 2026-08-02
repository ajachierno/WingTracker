"""Binary sensor platform for Wing Delivery."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ACTIVE_STATUSES, DOMAIN
from .coordinator import WingDeliveryCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: WingDeliveryCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WingActiveBinarySensor(coordinator, entry.entry_id)])


class WingActiveBinarySensor(
    CoordinatorEntity[WingDeliveryCoordinator], BinarySensorEntity
):
    _attr_name = "Wing Delivery Active"
    _attr_icon = "mdi:quadcopter"

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_active"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.status in ACTIVE_STATUSES
