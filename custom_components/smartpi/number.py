"""Number platform for the SmartPi integration.

Exposes per-phase calibration and configuration values as editable number
entities. All entities are disabled by default and only visible in the
device's entity list after the user enables them explicitly.
Changes are written directly to the SmartPi device via the AC config API.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricPotential, UnitOfFrequency
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SmartPiCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SmartPiNumberDescription(NumberEntityDescription):
    """Extends NumberEntityDescription with SmartPi-specific AC config metadata."""

    ac_config_key: str = ""
    phase: int | None = None  # None = global (not per-phase)
    config_type: str = "ac"   # "ac" or "main"


# Number entities created for all four phases (1–4)
_PHASE_NUMBERS: list[SmartPiNumberDescription] = [
    SmartPiNumberDescription(
        key="calibration_i",
        name="Current Calibration Factor",
        ac_config_key="CalibrationfactorI",
        native_min_value=0.1,
        native_max_value=10.0,
        native_step=0.001,
        mode=NumberMode.BOX,
        entity_registry_enabled_default=False,
    ),
    SmartPiNumberDescription(
        key="ct_primary_current",
        name="CT Primary Current",
        ac_config_key="CTTypePrimaryCurrent",
        native_min_value=1,
        native_max_value=9999,
        native_step=1,
        native_unit_of_measurement="A",
        mode=NumberMode.BOX,
        entity_registry_enabled_default=False,
    ),
    SmartPiNumberDescription(
        key="gui_max_current",
        name="GUI Maximum Current",
        ac_config_key="GUIMaxCurrent",
        native_min_value=1,
        native_max_value=9999,
        native_step=1,
        native_unit_of_measurement="A",
        mode=NumberMode.BOX,
        entity_registry_enabled_default=False,
    ),
]

# Number entities created only for phases 1–3 (voltage phases; phase 4 is neutral)
_PHASE_123_NUMBERS: list[SmartPiNumberDescription] = [
    SmartPiNumberDescription(
        key="voltage_ref",
        name="Reference Voltage",
        ac_config_key="Voltage",
        native_min_value=1,
        native_max_value=500,
        native_step=1,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=NumberDeviceClass.VOLTAGE,
        mode=NumberMode.BOX,
        entity_registry_enabled_default=False,
    ),
    SmartPiNumberDescription(
        key="calibration_u",
        name="Voltage Calibration Factor",
        ac_config_key="CalibrationfactorU",
        native_min_value=0.1,
        native_max_value=10.0,
        native_step=0.001,
        mode=NumberMode.BOX,
        entity_registry_enabled_default=False,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create number entities for all phases if AC configuration is available."""
    coordinator: SmartPiCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Number entities require credentials; skip setup if config could not be loaded
    if not coordinator._ac_config:
        return

    entities: list[SmartPiNumberEntity] = []

    for phase in range(1, 5):
        for desc in _PHASE_NUMBERS:
            entities.append(
                SmartPiNumberEntity(coordinator, entry, desc, phase)
            )

    for phase in range(1, 4):
        for desc in _PHASE_123_NUMBERS:
            entities.append(
                SmartPiNumberEntity(coordinator, entry, desc, phase)
            )

    async_add_entities(entities)


class SmartPiNumberEntity(NumberEntity):
    """An editable number entity backed by a SmartPi per-phase AC configuration value."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: SmartPiCoordinator,
        entry: ConfigEntry,
        description: SmartPiNumberDescription,
        phase: int,
    ) -> None:
        self._coordinator = coordinator
        self.entity_description = description
        self._phase = phase
        self._attr_unique_id = (
            f"{coordinator.serial}_cfg_{description.key}_phase{phase}"
        )
        self._attr_native_min_value = description.native_min_value
        self._attr_native_max_value = description.native_max_value
        self._attr_native_step = description.native_step
        self._attr_mode = description.mode
        if description.native_unit_of_measurement:
            self._attr_native_unit_of_measurement = (
                description.native_unit_of_measurement
            )
        if description.device_class:
            self._attr_device_class = description.device_class
        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )

    @property
    def name(self) -> str:
        return f"Phase {self._phase} {self.entity_description.name}"

    @property
    def device_info(self) -> DeviceInfo:
        info = self._coordinator.device_info
        return DeviceInfo(
            identifiers={(DOMAIN, self._coordinator.serial)},
            name=info.get("name", "SmartPi"),
            manufacturer="enerserve GmbH",
            model="SmartPi AC",
        )

    @property
    def available(self) -> bool:
        """Entity is only available when the AC configuration has been loaded."""
        return bool(self._coordinator._ac_config)

    @property
    def native_value(self) -> float | None:
        """Return the current value from the cached AC configuration."""
        phase_dict = self._coordinator._ac_config.get(
            self.entity_description.ac_config_key, {}
        )
        val = phase_dict.get(str(self._phase))
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Write the new value to the SmartPi device and update the local cache."""
        await self._coordinator.async_set_ac_config_phase_value(
            self.entity_description.ac_config_key, self._phase, value
        )
        self.async_write_ha_state()
