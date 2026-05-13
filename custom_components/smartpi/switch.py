from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SmartPiCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SmartPiSwitchDescription(SwitchEntityDescription):
    ac_config_key: str = ""


_PHASE_SWITCHES: list[SmartPiSwitchDescription] = [
    SmartPiSwitchDescription(
        key="measure_current",
        name="Strom messen",
        ac_config_key="MeasureCurrent",
        entity_registry_enabled_default=False,
    ),
    SmartPiSwitchDescription(
        key="current_direction",
        name="Stromrichtung umkehren",
        ac_config_key="CurrentDirection",
        entity_registry_enabled_default=False,
    ),
]

_PHASE_123_SWITCHES: list[SmartPiSwitchDescription] = [
    SmartPiSwitchDescription(
        key="measure_voltage",
        name="Spannung messen",
        ac_config_key="MeasureVoltage",
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

    entities: list[SmartPiSwitchEntity] = []

    for phase in range(1, 5):
        for desc in _PHASE_SWITCHES:
            entities.append(SmartPiSwitchEntity(coordinator, entry, desc, phase))

    for phase in range(1, 4):
        for desc in _PHASE_123_SWITCHES:
            entities.append(SmartPiSwitchEntity(coordinator, entry, desc, phase))

    async_add_entities(entities)


class SmartPiSwitchEntity(SwitchEntity):
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: SmartPiCoordinator,
        entry: ConfigEntry,
        description: SmartPiSwitchDescription,
        phase: int,
    ) -> None:
        self._coordinator = coordinator
        self.entity_description = description
        self._phase = phase
        self._attr_unique_id = (
            f"{coordinator.serial}_cfg_{description.key}_phase{phase}"
        )
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
    def is_on(self) -> bool | None:
        phase_dict = self._coordinator._ac_config.get(
            self.entity_description.ac_config_key, {}
        )
        val = phase_dict.get(str(self._phase))
        if val is None:
            return None
        return bool(val)

    async def async_turn_on(self, **kwargs) -> None:
        await self._coordinator.async_set_ac_config_phase_value(
            self.entity_description.ac_config_key, self._phase, True
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        await self._coordinator.async_set_ac_config_phase_value(
            self.entity_description.ac_config_key, self._phase, False
        )
        self.async_write_ha_state()
