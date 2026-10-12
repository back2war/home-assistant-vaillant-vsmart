"""The Vaillant vSMART binary sensor platform (boiler warnings)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .boiler_errors import (
    BOILER_ERROR_INTERNAL,
    MAINTENANCE,
    WATER_PRESSURE,
    errors_for_device,
)
from .const import DOMAIN
from .entity import VaillantCoordinator, VaillantDeviceEntity

# Values in boiler_error which are no problem
NON_PROBLEM_ERRORS = {"boiler_responding"}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_devices: AddEntitiesCallback
):
    """Set up Vaillant vSMART binary sensors from a config entry."""

    coordinator: VaillantCoordinator = hass.data[DOMAIN][entry.entry_id]

    new_devices: list[BinarySensorEntity] = []
    for device in coordinator.data.devices.values():
        new_devices += [
            VaillantBoilerErrorBinarySensor(coordinator, device.id, WATER_PRESSURE),
            VaillantBoilerErrorBinarySensor(coordinator, device.id, MAINTENANCE),
            VaillantBoilerErrorBinarySensor(coordinator, device.id, BOILER_ERROR_INTERNAL),
            VaillantBoilerProblemBinarySensor(coordinator, device.id),
        ]

    async_add_devices(new_devices)


class _VaillantBoilerBinarySensorBase(VaillantDeviceEntity, BinarySensorEntity):
    """Common logic for sensors based on the boiler_error list."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def _errors(self) -> list[str]:
        """Return the boiler errors of this device."""

        return errors_for_device(self.coordinator.data.boiler_errors or {}, self._device_id)

    @property
    def available(self) -> bool:
        """Return False if the homestatus endpoint could not be read."""

        return super().available and self.coordinator.data.boiler_errors is not None


class VaillantBoilerErrorBinarySensor(_VaillantBoilerBinarySensorBase):
    """Binary sensor which is on while a specific boiler error is reported."""

    def __init__(self, coordinator: VaillantCoordinator, device_id: str, error_code: str) -> None:
        """Initialize."""

        super().__init__(coordinator, device_id)
        self._error_code = error_code

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this entity."""

        return f"{self._device.id}_boiler_error_{self._error_code}"

    @property
    def translation_key(self) -> str:
        """Return the translation key to translate the entity's name."""

        return f"boiler_error_{self._error_code}"

    @property
    def is_on(self) -> bool:
        """Return True if the error is active."""

        return self._error_code in self._errors


class VaillantBoilerProblemBinarySensor(_VaillantBoilerBinarySensorBase):
    """Binary sensor which is on while any boiler error is reported."""

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this entity."""

        return f"{self._device.id}_boiler_problem"

    @property
    def translation_key(self) -> str:
        """Return the translation key to translate the entity's name."""

        return "boiler_problem"

    @property
    def is_on(self) -> bool:
        """Return True if any problem is reported."""

        return any(e not in NON_PROBLEM_ERRORS for e in self._errors)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the raw error codes."""

        return {"boiler_errors": self._errors}
