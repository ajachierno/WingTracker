"""Sensor platform for Wing Delivery."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
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
    async_add_entities(
        [
            WingStatusSensor(coordinator, entry.entry_id),
            WingEtaSensor(coordinator, entry.entry_id),
        ]
    )


class _BaseEntity(CoordinatorEntity[WingDeliveryCoordinator]):
    def __init__(
        self, coordinator: WingDeliveryCoordinator, entry_id: str, key: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_{key}"


class WingStatusSensor(_BaseEntity, SensorEntity):
    _attr_name = "Wing Delivery Status"
    _attr_icon = "mdi:package-variant"

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id, "status")

    @property
    def native_value(self) -> str:
        return self.coordinator.data.status

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        return {
            "order_id": data.order_id,
            "items": data.items,
            "tracking_url": data.tracking_url,
            "last_update": data.last_update,
        }


class WingEtaSensor(_BaseEntity, SensorEntity):
    _attr_name = "Wing Delivery ETA"
    _attr_icon = "mdi:timer-outline"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id, "eta")

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.eta_minutes
