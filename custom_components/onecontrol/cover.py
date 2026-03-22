"""1Control cover entities (gates, doors, etc.)."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import OneControlAPI, OneControlAPIError
from .const import AUTO_CLOSE_DELAY, CONF_AUTO_CLOSE_DELAY, CONF_DEVICES, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 1Control cover entities from a config entry."""
    api: OneControlAPI = hass.data[DOMAIN][entry.entry_id]

    auto_close_delay = int(entry.options.get(CONF_AUTO_CLOSE_DELAY, AUTO_CLOSE_DELAY))
    entities = [
        OneControlCover(api, device, auto_close_delay)
        for device in entry.data.get(CONF_DEVICES, [])
    ]
    async_add_entities(entities)


class OneControlCover(CoverEntity):
    """Represents a single 1Control action (gate/door) as a HA cover entity.

    Device is a Solo triggered via its paired Link2 bridge.
    State is tracked optimistically: after an open command the entity reports
    open, then auto-reverts to closed after AUTO_CLOSE_DELAY seconds to mirror
    the physical gate's auto-close behaviour.
    """

    _attr_has_entity_name = True
    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    _attr_assumed_state = True

    def __init__(self, api: OneControlAPI, device: dict, auto_close_delay: int = AUTO_CLOSE_DELAY) -> None:
        self._api = api
        self._solo_serial: int = device["serial"]
        self._link_serial: int = device["link_serial"]
        self._action: int = device["action"]

        # unique_id encodes solo serial + action so multiple actions on the
        # same Solo each get their own entity
        self._attr_unique_id = f"{DOMAIN}_{self._solo_serial}_{self._action}"
        self._attr_name = device["name"]  # e.g. "Cancello"

        self._auto_close_delay = auto_close_delay

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self._solo_serial))},
            name=device.get("device_name", f"1Control {self._solo_serial}"),
            manufacturer="1Control",
            model="Solo",
        )

        # Optimistic state — assume closed on startup
        self._is_closed = True
        self._auto_close_task: asyncio.Task | None = None

    @property
    def is_closed(self) -> bool | None:
        return self._is_closed

    async def async_open_cover(self, **kwargs) -> None:
        """Send open command and schedule auto-close."""
        try:
            await self._api.trigger_device(
                solo_serial=self._solo_serial,
                link_serial=self._link_serial,
                action=self._action,
                open=True,
            )
        except OneControlAPIError as err:
            _LOGGER.error(
                "Failed to open %s (serial=%s action=%s): %s",
                self.name,
                self._solo_serial,
                self._action,
                err,
            )
            return

        self._is_closed = False
        self.async_write_ha_state()

        # Cancel any previous auto-close timer (e.g. opened twice quickly)
        if self._auto_close_task and not self._auto_close_task.done():
            self._auto_close_task.cancel()

        self._auto_close_task = self.hass.async_create_task(
            self._schedule_auto_close()
        )

    async def async_close_cover(self, **kwargs) -> None:
        """Send close command and cancel any pending auto-close timer."""
        if self._auto_close_task and not self._auto_close_task.done():
            self._auto_close_task.cancel()
            self._auto_close_task = None

        try:
            await self._api.trigger_device(
                solo_serial=self._solo_serial,
                link_serial=self._link_serial,
                action=self._action,
                open=False,
            )
        except OneControlAPIError as err:
            _LOGGER.error(
                "Failed to close %s (serial=%s action=%s): %s",
                self.name,
                self._solo_serial,
                self._action,
                err,
            )
            return

        self._is_closed = True
        self.async_write_ha_state()

    async def _schedule_auto_close(self) -> None:
        """Mark the gate as closed after the auto-close delay."""
        try:
            await asyncio.sleep(self._auto_close_delay)
        except asyncio.CancelledError:
            return
        self._is_closed = True
        self._auto_close_task = None
        self.async_write_ha_state()
        _LOGGER.debug(
            "Gate %s auto-closed after %ss", self.name, self._auto_close_delay
        )

    async def async_will_remove_from_hass(self) -> None:
        """Clean up the auto-close task on entity removal."""
        if self._auto_close_task and not self._auto_close_task.done():
            self._auto_close_task.cancel()
