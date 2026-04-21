"""Button platform for the Battery Emulator REST integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BatteryEmulatorCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Battery Emulator REST button entities from a config entry."""
    coordinator: BatteryEmulatorCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([BatteryEmulatorCalibrateSOC(coordinator, entry)])


class BatteryEmulatorCalibrateSOC(
    CoordinatorEntity[BatteryEmulatorCoordinator], ButtonEntity
):
    """Button to trigger SOC calibration on the Battery Emulator."""

    _attr_has_entity_name = True
    _attr_name = "Calibrate SOC"

    def __init__(
        self,
        coordinator: BatteryEmulatorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_calibrate_soc"
        self._attr_device_info = coordinator.device_info

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_calibrate_soc()
