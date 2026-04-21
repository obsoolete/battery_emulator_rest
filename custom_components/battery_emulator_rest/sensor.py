"""Sensor platform for the Battery Emulator REST integration."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LAST_SUCCESSFUL_UPDATE
from .coordinator import BatteryEmulatorCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Battery Emulator REST sensor entities from a config entry."""
    coordinator: BatteryEmulatorCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([BatteryEmulatorLastUpdate(coordinator, entry)])


class BatteryEmulatorLastUpdate(
    CoordinatorEntity[BatteryEmulatorCoordinator], SensorEntity
):
    """Sensor showing the last successful data update time."""

    _attr_has_entity_name = True
    _attr_name = "Last Successful Update"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:clock-check-outline"

    def __init__(
        self,
        coordinator: BatteryEmulatorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_last_successful_update"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> datetime | None:
        """Return the last successful update timestamp."""
        return self.coordinator.data.get(LAST_SUCCESSFUL_UPDATE)
