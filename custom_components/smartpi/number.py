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
    ac_config_key: str = ""
    phase: int | None = None  # None = global (not per-phase)
    config_type: str = "ac"  # "ac" or "main"


# Per-phase number entities (phase 1-4)
_PHASE_NUMBERS: list[SmartPiNumberDescription] = [
    SmartPiNumberDescription(
        key="calibration_i",
        name="Kalibrierungsfaktor Strom",
        ac_config_key="CalibrationfactorI",
        native_min_value=0.1,
        native_max_value=10.0,
        native_step=0.001,
        mode=NumberMode.BOX,
        entity_registry_enabled_default=False,
    ),
    SmartPiNumberDescription(
        key="ct_primary_current",
        name="CT Primärstrom",
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
        name="Anzeige Maximalstrom",
        ac_config_key="GUIMaxCurrent",
        native_min_value=1,
        native_max_value=9999,
        native_step=1,
        native_unit_of_measurement="A",
        mode=NumberMode.BOX,
        entity_registry_enabled_default=False,
    ),
]

# Phase 1-3 only (no neutral)
_PHASE_123_NUMBERS: list[SmartPiNumberDescription] = [
    SmartPiNumberDescription(
        key="voltage_ref",
        name="Referenzspannung",
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
        name="Kalibrierungsfaktor Spannung",
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
    coordinator: SmartPiCoordinator = hass.data[DOMAIN][entry.entry_id]

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
        # Apply description attributes
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
        return bool(self._coordinator._ac_config)

    @property
    def native_value(self) -> float | None:
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
        await self._coordinator.async_set_ac_config_phase_value(
            self.entity_description.ac_config_key, self._phase, value
        )
        self.async_write_ha_state()
