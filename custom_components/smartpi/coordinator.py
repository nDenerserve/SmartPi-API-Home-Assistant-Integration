"""DataUpdateCoordinator for the SmartPi integration.

Handles all HTTP communication with the SmartPi device:
- Periodic live-data polling (livedata + livepower endpoints)
- JWT-based authentication with automatic token refresh
- Read/write access to the device's main and AC configuration
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_AC_CONFIG_READ,
    API_AC_CONFIG_WRITE,
    API_LIVEDATA,
    API_LIVEPOWER,
    API_LOGIN,
    API_MAIN_CONFIG_READ,
    API_MAIN_CONFIG_WRITE,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    TOTAL_POWER_KEY,
)

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=10)


class SmartPiCoordinator(DataUpdateCoordinator[dict[tuple[int, str], dict[str, Any]]]):
    """Coordinator that polls the SmartPi device and exposes its data to entities.

    The coordinator data dict is keyed by (phase_number, measurement_type).
    Phase 0 is used for global values (e.g. total power).
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the coordinator with connection parameters from the config entry."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._host = entry.data[CONF_HOST]
        self._port = entry.data.get(CONF_PORT, DEFAULT_PORT)
        self._username = entry.data.get(CONF_USERNAME, "")
        self._password = entry.data.get(CONF_PASSWORD, "")
        self._token: str | None = None
        self.device_info: dict[str, str] = {}
        self.serial: str = entry.unique_id or entry.entry_id
        # Cached SmartPi configuration (loaded once at startup)
        self._ac_config: dict[str, Any] = {}
        self._main_config: dict[str, Any] = {}

    @property
    def base_url(self) -> str:
        """Base HTTP URL of the SmartPi device."""
        return f"http://{self._host}:{self._port}"

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def _authenticate(self) -> bool:
        """Obtain a JWT from the SmartPi login endpoint and store it in self._token."""
        if not self._username or not self._password:
            return False
        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                f"{self.base_url}{API_LOGIN}",
                json={"username": self._username, "password": self._password},
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    self._token = data.get("token")
                    return True
                _LOGGER.warning("SmartPi authentication failed: HTTP %s", resp.status)
                self._token = None
                return False
        except aiohttp.ClientError as err:
            _LOGGER.warning("SmartPi authentication error: %s", err)
            self._token = None
            return False

    async def _auth_headers(self) -> dict[str, str]:
        """Return Authorization headers, authenticating first if no token is cached."""
        if not self._token:
            await self._authenticate()
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    # ------------------------------------------------------------------
    # Live data polling
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[tuple[int, str], dict[str, Any]]:
        """Fetch live measurements from the SmartPi device.

        Called by the coordinator on every poll interval. Fetches both the
        per-phase livedata and the aggregated total-power value, then returns
        a unified dict keyed by (phase, measurement_type).
        """
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                f"{self.base_url}{API_LIVEDATA}", timeout=_TIMEOUT
            ) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"SmartPi returned HTTP {resp.status}")
                raw = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise UpdateFailed(
                f"Cannot connect to SmartPi at {self._host}: {err}"
            ) from err

        self.device_info = {
            "serial": raw.get("serial", ""),
            "name": raw.get("name", "SmartPi"),
            "ip": raw.get("ipaddress", self._host),
            "sw_version": raw.get("softwareversion", ""),
        }

        result = self._parse_livedata(raw)

        # Also fetch total power
        try:
            async with session.get(
                f"{self.base_url}{API_LIVEPOWER}", timeout=_TIMEOUT
            ) as resp:
                if resp.status == 200:
                    power_raw = await resp.json(content_type=None)
                    result[(0, TOTAL_POWER_KEY)] = {
                        "value": power_raw.get("power"),
                        "unit": "W",
                        "phase": 0,
                        "phase_name": "total",
                        "type": TOTAL_POWER_KEY,
                    }
        except (aiohttp.ClientError, ValueError) as err:
            # ValueError covers json.JSONDecodeError when the reverse proxy
            # returns an HTML page instead of JSON for this endpoint.
            _LOGGER.debug("Could not fetch livepower: %s", err)

        return result

    def _parse_livedata(self, raw: dict) -> dict[tuple[int, str], dict[str, Any]]:
        """Extract per-phase measurement values from the livedata API response."""
        result: dict[tuple[int, str], dict[str, Any]] = {}
        datasets = raw.get("datasets", [])
        if not datasets:
            return result
        dataset = datasets[-1]
        for phase in dataset.get("phases", []):
            phase_num: int = phase.get("phase", 0)
            phase_name: str = phase.get("name", f"Phase {phase_num}")
            for value in phase.get("values", []):
                value_type: str = value.get("type", "")
                if not value_type:
                    continue
                result[(phase_num, value_type)] = {
                    "value": value.get("data"),
                    "unit": value.get("unity") or None,
                    "phase": phase_num,
                    "phase_name": phase_name,
                    "type": value_type,
                }
        return result

    # ------------------------------------------------------------------
    # SmartPi configuration (main settings + AC measurements)
    # ------------------------------------------------------------------

    async def async_load_config(self) -> None:
        """Load both AC and main configuration from SmartPi.

        Called once during entry setup. Configuration values are cached in
        _ac_config and _main_config to avoid repeated API calls from entities.
        Skipped silently when no credentials are provided.
        """
        if not self._username or not self._password:
            return
        try:
            self._ac_config = await self._fetch_config(API_AC_CONFIG_READ)
            self._main_config = await self._fetch_config(API_MAIN_CONFIG_READ)
        except Exception as err:
            _LOGGER.warning("Could not load SmartPi configuration: %s", err)

    async def _fetch_config(self, path: str) -> dict[str, Any]:
        """GET a configuration endpoint, retrying once on 401 (token expired)."""
        headers = await self._auth_headers()
        if not headers:
            return {}
        session = async_get_clientsession(self.hass)
        async with session.get(
            f"{self.base_url}{path}", headers=headers, timeout=_TIMEOUT
        ) as resp:
            if resp.status == 401:
                # Token has expired — re-authenticate and retry once
                self._token = None
                headers = await self._auth_headers()
                async with session.get(
                    f"{self.base_url}{path}", headers=headers, timeout=_TIMEOUT
                ) as retry:
                    retry.raise_for_status()
                    return await retry.json(content_type=None)
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def _write_config(self, path: str, config_type: str, config: dict) -> None:
        """POST a configuration update, retrying once on 401 (token expired)."""
        headers = await self._auth_headers()
        if not headers:
            raise PermissionError("No credentials configured")
        session = async_get_clientsession(self.hass)
        payload = {"type": config_type, "msg": config}
        async with session.post(
            f"{self.base_url}{path}", json=payload, headers=headers, timeout=_TIMEOUT
        ) as resp:
            if resp.status == 401:
                self._token = None
                headers = await self._auth_headers()
                async with session.post(
                    f"{self.base_url}{path}",
                    json=payload,
                    headers=headers,
                    timeout=_TIMEOUT,
                ) as retry:
                    retry.raise_for_status()
            else:
                resp.raise_for_status()

    # AC configuration (per-phase measurement settings)

    async def async_get_ac_config(self) -> dict[str, Any]:
        """Fetch the current AC configuration from the device (not the cache)."""
        return await self._fetch_config(API_AC_CONFIG_READ)

    async def async_write_ac_config(self) -> None:
        """Write the cached AC configuration back to the device."""
        await self._write_config(API_AC_CONFIG_WRITE, "smartpiacconfig", self._ac_config)

    async def async_set_ac_config_value(self, key: str, value: Any) -> None:
        """Update a global AC configuration key and persist to the device."""
        self._ac_config[key] = value
        await self.async_write_ac_config()

    async def async_set_ac_config_phase_value(
        self, key: str, phase: int, value: Any
    ) -> None:
        """Update a per-phase AC configuration value and persist to the device."""
        self._ac_config.setdefault(key, {})[str(phase)] = value
        await self.async_write_ac_config()

    # Main configuration (device name, location, logging)

    async def async_get_main_config(self) -> dict[str, Any]:
        """Fetch the current main configuration from the device (not the cache)."""
        return await self._fetch_config(API_MAIN_CONFIG_READ)

    async def async_write_main_config(self) -> None:
        """Write the cached main configuration back to the device."""
        await self._write_config(
            API_MAIN_CONFIG_WRITE, "smartpiconfig", self._main_config
        )

    async def async_set_main_config_fields(self, fields: dict[str, Any]) -> None:
        """Update selected fields in main config and write to SmartPi.

        Only the keys present in *fields* are updated; all other settings
        already stored on the device are preserved.
        """
        config = await self.async_get_main_config()
        key_map = {
            "name": "Name",
            "lat": "Lat",
            "lng": "Lng",
            "loglevel": "LogLevel",
        }
        for form_key, config_key in key_map.items():
            if form_key in fields:
                config[config_key] = fields[form_key]
        self._main_config = config
        await self._write_config(API_MAIN_CONFIG_WRITE, "smartpiconfig", config)

    async def async_set_ac_config_fields(self, fields: dict[str, Any]) -> None:
        """Update global AC measurement fields and write to SmartPi.

        Only the keys present in *fields* are updated; all other settings
        already stored on the device are preserved.
        """
        config = await self.async_get_ac_config()
        key_map = {
            "powerfrequency": "PowerFrequency",
            "samplerate": "Samplerate",
            "integrator": "Integrator",
        }
        for form_key, config_key in key_map.items():
            if form_key in fields:
                config[config_key] = fields[form_key]
        self._ac_config = config
        await self._write_config(API_AC_CONFIG_WRITE, "smartpiacconfig", config)
