"""SmartPi integration for Home Assistant.

Registers the SmartPi AC energy meter as a config entry and sets up all
supported platforms (sensor, number, switch, select).
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SmartPiCoordinator

PLATFORMS = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SELECT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SmartPi from a config entry.

    Creates the coordinator, performs the first data refresh, loads the device
    configuration (requires credentials), stores the coordinator in hass.data,
    and forwards the entry to all supported platforms.
    """
    coordinator = SmartPiCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    # Load SmartPi device config for writable config entities (requires credentials)
    await coordinator.async_load_config()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when options change (sensor selection)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a SmartPi config entry and clean up hass.data."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
