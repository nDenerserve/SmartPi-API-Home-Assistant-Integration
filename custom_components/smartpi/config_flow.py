from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    ALL_MEASUREMENT_KEYS,
    API_LIVEDATA,
    API_LOGIN,
    CONF_ENABLED_MEASUREMENTS,
    DEFAULT_PORT,
    DOMAIN,
    LOG_LEVELS,
    MEASUREMENT_TYPES,
    POWER_FREQUENCIES,
    TOTAL_POWER_KEY,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_USERNAME, default=""): str,
        vol.Optional(CONF_PASSWORD, default=""): str,
    }
)

MEASUREMENT_LABELS: dict[str, str] = {
    "current": "Strom (A)",
    "voltage": "Spannung (V)",
    "power": "Wirkleistung (W)",
    "cosphi": "Leistungsfaktor (cos φ)",
    "frequency": "Frequenz (Hz)",
    "energyconsumed": "Bezogene Energie (Wh)",
    "energyproduced": "Eingespeiste Energie (Wh)",
    "energybalanced": "Bilanzierte Energie (Wh)",
    TOTAL_POWER_KEY: "Gesamtleistung (W)",
}


class CannotConnect(Exception):
    pass


class InvalidAuth(Exception):
    pass


async def validate_connection(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    host = data[CONF_HOST]
    port = data.get(CONF_PORT, DEFAULT_PORT)
    username = data.get(CONF_USERNAME, "")
    password = data.get(CONF_PASSWORD, "")

    session = async_get_clientsession(hass)
    base_url = f"http://{host}:{port}"

    try:
        async with session.get(
            f"{base_url}{API_LIVEDATA}",
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                raise CannotConnect(f"Unexpected status {resp.status}")
            device_data = await resp.json(content_type=None)
    except aiohttp.ClientError as err:
        raise CannotConnect(str(err)) from err

    if username and password:
        try:
            async with session.post(
                f"{base_url}{API_LOGIN}",
                json={"username": username, "password": password},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuth
                if resp.status != 200:
                    raise CannotConnect(f"Login returned {resp.status}")
        except aiohttp.ClientError as err:
            raise CannotConnect(str(err)) from err

    return {
        "serial": device_data.get("serial", ""),
        "name": device_data.get("name") or f"SmartPi {host}",
    }


class SmartPiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_connection(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during SmartPi setup")
                errors["base"] = "unknown"
            else:
                serial = info["serial"]
                if serial:
                    await self.async_set_unique_id(serial)
                    self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["name"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._reauth_entry

        if user_input is not None:
            new_data = {**entry.data, **user_input}
            try:
                await validate_connection(self.hass, new_data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during SmartPi reauth")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(entry, data=new_data)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=entry.data.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={"host": entry.data.get(CONF_HOST, "")},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SmartPiOptionsFlow:
        return SmartPiOptionsFlow()


class SmartPiOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["sensors", "grundeinstellungen", "messungen"],
        )

    # ------------------------------------------------------------------
    # Sensor selection
    # ------------------------------------------------------------------

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            new_options = {
                **self.config_entry.options,
                CONF_ENABLED_MEASUREMENTS: user_input[CONF_ENABLED_MEASUREMENTS],
            }
            return self.async_create_entry(data=new_options)

        enabled = self.config_entry.options.get(
            CONF_ENABLED_MEASUREMENTS, ALL_MEASUREMENT_KEYS
        )

        return self.async_show_form(
            step_id="sensors",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENABLED_MEASUREMENTS, default=list(enabled)
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": k, "label": MEASUREMENT_LABELS.get(k, k)}
                                for k in ALL_MEASUREMENT_KEYS
                            ],
                            multiple=True,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    # ------------------------------------------------------------------
    # Grundeinstellungen (writes to SmartPi, not stored in HA options)
    # ------------------------------------------------------------------

    async def async_step_grundeinstellungen(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]

        if user_input is not None:
            try:
                await coordinator.async_set_main_config_fields(user_input)
            except PermissionError:
                errors["base"] = "no_credentials"
            except Exception:
                _LOGGER.exception("Failed to write SmartPi Grundeinstellungen")
                errors["base"] = "write_failed"
            else:
                return self.async_create_entry(data=dict(self.config_entry.options))

        try:
            config = await coordinator.async_get_main_config()
        except Exception:
            _LOGGER.exception("Failed to read SmartPi main config")
            return self.async_abort(reason="cannot_connect")

        return self.async_show_form(
            step_id="grundeinstellungen",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "name", default=config.get("Name", "")
                    ): str,
                    vol.Optional(
                        "lat", default=config.get("Lat", 0.0)
                    ): vol.Coerce(float),
                    vol.Optional(
                        "lng", default=config.get("Lng", 0.0)
                    ): vol.Coerce(float),
                    vol.Optional(
                        "loglevel", default=config.get("LogLevel", "info")
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=LOG_LEVELS,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Messungen – global AC settings (per-phase via entities)
    # ------------------------------------------------------------------

    async def async_step_messungen(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]

        if user_input is not None:
            try:
                await coordinator.async_set_ac_config_fields(user_input)
            except PermissionError:
                errors["base"] = "no_credentials"
            except Exception:
                _LOGGER.exception("Failed to write SmartPi Messungen")
                errors["base"] = "write_failed"
            else:
                return self.async_create_entry(data=dict(self.config_entry.options))

        try:
            config = await coordinator.async_get_ac_config()
        except Exception:
            _LOGGER.exception("Failed to read SmartPi AC config")
            return self.async_abort(reason="cannot_connect")

        freq_default = str(config.get("PowerFrequency", 50))

        return self.async_show_form(
            step_id="messungen",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "powerfrequency",
                        default=freq_default,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[str(f) for f in POWER_FREQUENCIES],
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                    vol.Optional(
                        "samplerate",
                        default=config.get("Samplerate", 1),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                    vol.Optional(
                        "integrator",
                        default=config.get("Integrator", False),
                    ): bool,
                }
            ),
            errors=errors,
        )
