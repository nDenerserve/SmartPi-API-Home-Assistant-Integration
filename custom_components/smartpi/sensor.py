"""Sensor platform for the SmartPi integration.

Creates one SensorEntity per enabled (phase, measurement_type) combination.
All sensors are read-only and updated by the SmartPiCoordinator.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ALL_MEASUREMENT_KEYS,
    CONF_ENABLED_MEASUREMENTS,
    DOMAIN,
    TOTAL_POWER_KEY,
)
from .coordinator import SmartPiCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SmartPiSensorEntityDescription(SensorEntityDescription):
    """Extends SensorEntityDescription with a display label used in the entity name."""

    value_label: str = ""


# Static description for every supported measurement type.
# The phase number is added dynamically when entities are instantiated.
SENSOR_DESCRIPTIONS: dict[str, SmartPiSensorEntityDescription] = {
    "current": SmartPiSensorEntityDescription(
        key="current",
        value_label="Current",
        native_unit_of_measurement="A",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    "voltage": SmartPiSensorEntityDescription(
        key="voltage",
        value_label="Voltage",
        native_unit_of_measurement="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "power": SmartPiSensorEntityDescription(
        key="power",
        value_label="Active Power",
        native_unit_of_measurement="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "cosphi": SmartPiSensorEntityDescription(
        key="cosphi",
        value_label="Power Factor",
        native_unit_of_measurement=None,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    "frequency": SmartPiSensorEntityDescription(
        key="frequency",
        value_label="Frequency",
        native_unit_of_measurement="Hz",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    "energyconsumed": SmartPiSensorEntityDescription(
        key="energyconsumed",
        value_label="Energy Consumed",
        native_unit_of_measurement="Wh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
    ),
    "energyproduced": SmartPiSensorEntityDescription(
        key="energyproduced",
        value_label="Energy Produced",
        native_unit_of_measurement="Wh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
    ),
    "energybalanced": SmartPiSensorEntityDescription(
        key="energybalanced",
        value_label="Energy Balance",
        native_unit_of_measurement="Wh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
    ),
    TOTAL_POWER_KEY: SmartPiSensorEntityDescription(
        key=TOTAL_POWER_KEY,
        value_label="Total Power",
        native_unit_of_measurement="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create SmartPiSensor entities for all enabled (phase, measurement_type) pairs."""
    coordinator: SmartPiCoordinator = hass.data[DOMAIN][entry.entry_id]

    enabled = set(
        entry.options.get(CONF_ENABLED_MEASUREMENTS, ALL_MEASUREMENT_KEYS)
    )

    entities: list[SmartPiSensor] = []
    for (phase_num, value_type), value_data in coordinator.data.items():
        if value_type not in enabled:
            continue
        description = SENSOR_DESCRIPTIONS.get(value_type)
        if description is None:
            _LOGGER.debug("SmartPi: ignoring unknown measurement type '%s'", value_type)
            continue
        entities.append(
            SmartPiSensor(
                coordinator=coordinator,
                entry=entry,
                phase_num=phase_num,
                phase_name=value_data["phase_name"],
                description=description,
            )
        )

    async_add_entities(entities)


class SmartPiSensor(CoordinatorEntity[SmartPiCoordinator], SensorEntity):
    """A single SmartPi measurement value exposed as a HA sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SmartPiCoordinator,
        entry: ConfigEntry,
        phase_num: int,
        phase_name: str,
        description: SmartPiSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._phase_num = phase_num
        self._phase_name = phase_name
        self._attr_unique_id = (
            f"{coordinator.serial}_phase_{phase_num}_{description.key}"
        )

    @property
    def name(self) -> str:
        """Return the entity name, prefixed with the phase name for per-phase sensors."""
        if self._phase_num == 0:
            return self.entity_description.value_label
        return f"{self._phase_name.title()} {self.entity_description.value_label}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information so all sensors share one device entry."""
        info = self.coordinator.device_info
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.serial)},
            name=info.get("name", "SmartPi"),
            manufacturer="enerserve GmbH",
            model="SmartPi AC",
            sw_version=info.get("sw_version") or None,
            configuration_url=(
                f"http://{info.get('ip', self.coordinator._host)}"
                f":{self.coordinator._port}"
            ),
        )

    @property
    def native_value(self) -> float | None:
        """Return the current measurement value from the coordinator data cache."""
        entry: dict[str, Any] | None = self.coordinator.data.get(
            (self._phase_num, self.entity_description.key)
        )
        if entry is None:
            return None
        return entry.get("value")
