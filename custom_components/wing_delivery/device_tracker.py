"""Device tracker platform for Wing Delivery (drone position)."""
from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WingDeliveryCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: WingDeliveryCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WingDroneTracker(coordinator, entry.entry_id)])


class WingDroneTracker(
    CoordinatorEntity[WingDeliveryCoordinator], TrackerEntity
):
    _attr_name = "Wing Drone"
    _attr_icon = "mdi:quadcopter"

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_drone"

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        return self.coordinator.data.latitude

    @property
    def longitude(self) -> float | None:
        return self.coordinator.data.longitude
