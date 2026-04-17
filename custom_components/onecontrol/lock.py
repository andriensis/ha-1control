"""1Control lock entities — PIN-protected gate/door.

Used instead of the cover platform when the user has configured a PIN in
the integration options. Exposing the gate as a lock gives us HA's native
code prompt (via `code_format`) in the default Lovelace lock card — no
custom service needed.
"""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import OneControlAPI, OneControlAPIError
from .const import (
    AUTO_CLOSE_DELAY,
    CONF_AUTO_CLOSE_DELAY,
    CONF_DEVICES,
    CONF_PIN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 1Control lock entities from a config entry."""
    api: OneControlAPI = hass.data[DOMAIN][entry.entry_id]["api"]

    auto_close_delay = int(entry.options.get(CONF_AUTO_CLOSE_DELAY, AUTO_CLOSE_DELAY))
    pin: str = entry.options.get(CONF_PIN, "")

    entities = [
        OneControlLock(api, device, pin, auto_close_delay)
        for device in entry.data.get(CONF_DEVICES, [])
    ]
    async_add_entities(entities)


def _code_format_for(pin: str) -> str:
    """Regex fed to the frontend — controls whether the code pad is numeric.

    All-digit PINs get a fixed-length digit pattern so Lovelace shows a
    numeric keypad of the right size. Anything else falls back to a plain
    text prompt of matching length.
    """
    if pin.isdigit():
        return rf"^\d{{{len(pin)}}}$"
    return rf"^.{{{len(pin)}}}$"


class OneControlLock(LockEntity):
    """PIN-protected gate/door exposed as a lock entity.

    Unlock = send open command to the Solo. Auto-locks after the configured
    delay to mirror the gate's physical auto-close. Locking also requires
    the PIN so a bystander can't re-lock mid-transit.
    """

    _attr_has_entity_name = True
    _attr_assumed_state = True

    def __init__(
        self,
        api: OneControlAPI,
        device: dict,
        pin: str,
        auto_close_delay: int = AUTO_CLOSE_DELAY,
    ) -> None:
        self._api = api
        self._solo_serial: int = device["serial"]
        self._link_serial: int = device["link_serial"]
        self._action: int = device["action"]
        self._pin = pin
        self._attr_code_format = _code_format_for(pin)

        # Match the cover entity's unique_id so migrating (cover→lock) reuses
        # the same device row in the registry.
        self._attr_unique_id = f"{DOMAIN}_{self._solo_serial}_{self._action}"
        self._attr_name = device["name"]
        self._auto_close_delay = auto_close_delay

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self._solo_serial))},
            name=device.get("device_name", f"1Control {self._solo_serial}"),
            manufacturer="1Control",
            model="Solo",
        )

        self._attr_is_locked = True
        self._auto_lock_task: asyncio.Task | None = None

    def _check_pin(self, code: str | None) -> None:
        if code != self._pin:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="invalid_pin"
            )

    async def async_unlock(self, **kwargs) -> None:
        """Validate the PIN and send an open command."""
        self._check_pin(kwargs.get("code"))
        try:
            await self._api.trigger_device(
                solo_serial=self._solo_serial,
                link_serial=self._link_serial,
                action=self._action,
                open=True,
            )
        except OneControlAPIError as err:
            _LOGGER.error(
                "Failed to unlock %s (serial=%s action=%s): %s",
                self.name,
                self._solo_serial,
                self._action,
                err,
            )
            return

        self._attr_is_locked = False
        self.async_write_ha_state()

        if self._auto_lock_task and not self._auto_lock_task.done():
            self._auto_lock_task.cancel()
        self._auto_lock_task = self.hass.async_create_task(self._schedule_auto_lock())

    async def async_lock(self, **kwargs) -> None:
        """Validate the PIN and send a close command."""
        self._check_pin(kwargs.get("code"))

        if self._auto_lock_task and not self._auto_lock_task.done():
            self._auto_lock_task.cancel()
            self._auto_lock_task = None

        try:
            await self._api.trigger_device(
                solo_serial=self._solo_serial,
                link_serial=self._link_serial,
                action=self._action,
                open=False,
            )
        except OneControlAPIError as err:
            _LOGGER.error(
                "Failed to lock %s (serial=%s action=%s): %s",
                self.name,
                self._solo_serial,
                self._action,
                err,
            )
            return

        self._attr_is_locked = True
        self.async_write_ha_state()

    async def _schedule_auto_lock(self) -> None:
        try:
            await asyncio.sleep(self._auto_close_delay)
        except asyncio.CancelledError:
            return
        self._attr_is_locked = True
        self._auto_lock_task = None
        self.async_write_ha_state()
        _LOGGER.debug(
            "Gate %s auto-locked after %ss", self.name, self._auto_close_delay
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._auto_lock_task and not self._auto_lock_task.done():
            self._auto_lock_task.cancel()
