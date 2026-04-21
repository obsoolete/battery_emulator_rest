"""Number platform for the Battery Emulator REST integration."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MAX_CHARGE_SPEED, MAX_DISCHARGE_SPEED
from .coordinator import BatteryEmulatorCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Battery Emulator REST number entities from a config entry."""
    coordinator: BatteryEmulatorCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            BatteryEmulatorMaxChargeSpeed(coordinator, entry),
            BatteryEmulatorMaxDischargeSpeed(coordinator, entry),
        ]
    )


class BatteryEmulatorMaxChargeSpeed(
    CoordinatorEntity[BatteryEmulatorCoordinator], NumberEntity
):
    """Number entity for Battery Emulator max charge speed."""

    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 0.1
    _attr_mode = NumberMode.BOX
    _attr_has_entity_name = True
    _attr_name = "Max Charge Speed"

    def __init__(
        self,
        coordinator: BatteryEmulatorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_max_charge_speed"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float | None:
        """Return the current max charge speed."""
        return self.coordinator.data.get(MAX_CHARGE_SPEED)

    async def async_set_native_value(self, value: float) -> None:
        """Set the max charge speed."""
        await self.coordinator.async_set_max_charge(value)


class BatteryEmulatorMaxDischargeSpeed(
    CoordinatorEntity[BatteryEmulatorCoordinator], NumberEntity
):
    """Number entity for Battery Emulator max discharge speed."""

    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 0.1
    _attr_mode = NumberMode.BOX
    _attr_has_entity_name = True
    _attr_name = "Max Discharge Speed"

    def __init__(
        self,
        coordinator: BatteryEmulatorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_max_discharge_speed"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float | None:
        """Return the current max discharge speed."""
        return self.coordinator.data.get(MAX_DISCHARGE_SPEED)

    async def async_set_native_value(self, value: float) -> None:
        """Set the max discharge speed."""
        await self.coordinator.async_set_max_discharge(value)
