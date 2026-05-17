"""Config flow for the 1Control integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import OneControlAPI, OneControlAuthError, OneControlAPIError
from .const import (
    AUTO_CLOSE_DELAY,
    CONF_AUTO_CLOSE_DELAY,
    CONF_DEVICES,
    CONF_DORY_DEVICES,
    CONF_DORY_UPDATE_INTERVAL,
    CONF_PIN,
    CONF_UID,
    DOMAIN,
    DORY_UPDATE_INTERVAL,
    DORY_UPDATE_INTERVAL_MAX,
    DORY_UPDATE_INTERVAL_MIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required("email"): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="email")
        ),
        vol.Required("password"): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
    }
)


class OneControlOptionsFlow(OptionsFlow):
    """Handle 1Control options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            # Normalise: treat whitespace-only PIN as unset so the entity
            # swap back to a cover triggers cleanly.
            pin = (user_input.get(CONF_PIN) or "").strip()
            user_input[CONF_PIN] = pin
            return self.async_create_entry(data=user_input)

        current_delay = self.config_entry.options.get(CONF_AUTO_CLOSE_DELAY, AUTO_CLOSE_DELAY)
        current_pin = self.config_entry.options.get(CONF_PIN, "")
        current_dory_interval = self.config_entry.options.get(
            CONF_DORY_UPDATE_INTERVAL, DORY_UPDATE_INTERVAL
        )
        has_dory = bool(self.config_entry.data.get(CONF_DORY_DEVICES))

        schema_dict: dict = {
            vol.Required(CONF_AUTO_CLOSE_DELAY, default=current_delay): NumberSelector(
                NumberSelectorConfig(min=5, max=300, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement="s")
            ),
            # Use suggested_value rather than default= so clearing the field
            # actually clears the PIN — default= would backfill the old value
            # whenever the field comes back empty.
            vol.Optional(
                CONF_PIN,
                description={"suggested_value": current_pin},
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        }
        if has_dory:
            schema_dict[
                vol.Required(CONF_DORY_UPDATE_INTERVAL, default=current_dory_interval)
            ] = NumberSelector(
                NumberSelectorConfig(
                    min=DORY_UPDATE_INTERVAL_MIN,
                    max=DORY_UPDATE_INTERVAL_MAX,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            )
        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema_dict))


class OneControlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for 1Control."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OneControlOptionsFlow:
        return OneControlOptionsFlow()

    def __init__(self) -> None:
        self._email: str = ""
        self._password: str = ""
        self._uid: str = ""
        # Each item: {serial, link_serial, action, name, device_name}
        self._discovered_devices: list[dict] = []
        # Each item: {serial, name, opened, opened_state_date, battery, firmware_version}
        self._discovered_dory_devices: list[dict] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle credentials entry and device discovery."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._email = user_input["email"]
            self._password = user_input["password"]

            session = async_get_clientsession(self.hass)
            api = OneControlAPI(session, self._email, self._password)

            try:
                self._uid = await api.authenticate()
                self._discovered_devices = await api.get_devices()
                self._discovered_dory_devices = await api.get_dory_devices()
            except OneControlAuthError:
                errors["base"] = "invalid_auth"
            except OneControlAPIError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during authentication")
                errors["base"] = "unknown"
            else:
                if not self._discovered_devices and not self._discovered_dory_devices:
                    errors["base"] = "no_devices_found"

            if not errors:
                if self._discovered_devices:
                    return await self.async_step_select_devices()
                # Dory-only account: no Solo action selection needed.
                return self._create_entry([])

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_select_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick which discovered actions to add as cover entities."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_keys: list[str] = user_input.get("devices", [])
            if not selected_keys:
                errors["base"] = "no_devices_selected"
            else:
                selected = [
                    d for d in self._discovered_devices
                    if self._device_key(d) in selected_keys
                ]
                return self._create_entry(selected)

        options = [
            SelectOptionDict(
                value=self._device_key(d),
                label=f"{d['device_name']} — {d['name']}",
            )
            for d in self._discovered_devices
        ]

        schema = vol.Schema(
            {
                vol.Required("devices"): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="select_devices",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    def _device_key(device: dict) -> str:
        """Unique string key for a device/action combo."""
        return f"{device['serial']}_{device['action']}"

    def _create_entry(self, devices: list[dict]) -> ConfigFlowResult:
        """Create the config entry."""
        return self.async_create_entry(
            title=f"1Control ({self._email})",
            data={
                "email": self._email,
                "password": self._password,
                CONF_UID: self._uid,
                CONF_DEVICES: devices,
                CONF_DORY_DEVICES: self._discovered_dory_devices,
            },
        )
