from __future__ import annotations

import logging
from dataclasses import dataclass, field

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CT_TYPES, DOMAIN
from .coordinator import SmartPiCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SmartPiSelectDescription(SelectEntityDescription):
    ac_config_key: str = ""
    options_list: list[str] = field(default_factory=list)


_PHASE_SELECTS: list[SmartPiSelectDescription] = [
    SmartPiSelectDescription(
        key="ct_type",
        name="Stromwandler-Typ",
        ac_config_key="CTType",
        options_list=CT_TYPES,
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

    entities: list[SmartPiSelectEntity] = []

    for phase in range(1, 5):
        for desc in _PHASE_SELECTS:
            entities.append(SmartPiSelectEntity(coordinator, entry, desc, phase))

    async_add_entities(entities)


class SmartPiSelectEntity(SelectEntity):
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: SmartPiCoordinator,
        entry: ConfigEntry,
        description: SmartPiSelectDescription,
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

        # Build options list, adding current value if unknown
        current = (
            coordinator._ac_config.get(description.ac_config_key, {}).get(
                str(phase), ""
            )
        )
        opts = list(description.options_list)
        if current and current not in opts:
            opts.insert(0, current)
        self._attr_options = opts

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
    def current_option(self) -> str | None:
        return self._coordinator._ac_config.get(
            self.entity_description.ac_config_key, {}
        ).get(str(self._phase))

    async def async_select_option(self, option: str) -> None:
        await self._coordinator.async_set_ac_config_phase_value(
            self.entity_description.ac_config_key, self._phase, option
        )
        self.async_write_ha_state()
