"""1Control Dory binary sensor entities (door/gate position sensors)."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import OneControlAPI, OneControlAPIError
from .const import (
    CONF_DORY_DEVICES,
    CONF_DORY_UPDATE_INTERVAL,
    DOMAIN,
    DORY_UPDATE_INTERVAL,
    DORY_UPDATE_INTERVAL_MIN,
)

_LOGGER = logging.getLogger(__name__)


class DoryCoordinator(DataUpdateCoordinator[dict[int, dict]]):
    """Polls /devices/dory and keys state by Dory serial."""

    def __init__(
        self, hass: HomeAssistant, api: OneControlAPI, interval_seconds: int
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="1Control Dory",
            update_interval=timedelta(seconds=interval_seconds),
        )
        self._api = api

    async def _async_update_data(self) -> dict[int, dict]:
        try:
            devices = await self._api.get_dory_devices()
        except OneControlAPIError as err:
            raise UpdateFailed(f"Failed to fetch Dory state: {err}") from err
        return {d["serial"]: d for d in devices}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 1Control Dory binary sensors from a config entry."""
    api: OneControlAPI = hass.data[DOMAIN][entry.entry_id]["api"]

    interval = max(
        DORY_UPDATE_INTERVAL_MIN,
        int(entry.options.get(CONF_DORY_UPDATE_INTERVAL, DORY_UPDATE_INTERVAL)),
    )
    coordinator = DoryCoordinator(hass, api, interval)
    await coordinator.async_config_entry_first_refresh()

    configured = entry.data.get(CONF_DORY_DEVICES, [])
    async_add_entities(
        OneControlDorySensor(coordinator, device) for device in configured
    )


class OneControlDorySensor(CoordinatorEntity[DoryCoordinator], BinarySensorEntity):
    """A Dory door/gate position sensor."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_device_class = BinarySensorDeviceClass.GARAGE_DOOR

    def __init__(self, coordinator: DoryCoordinator, device: dict) -> None:
        super().__init__(coordinator)
        self._serial: int = device["serial"]
        self._attr_unique_id = f"{DOMAIN}_dory_{self._serial}"

        firmware = device.get("firmware_version")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"dory_{self._serial}")},
            name=device.get("name") or f"Dory {self._serial}",
            manufacturer="1Control",
            model="Dory",
            sw_version=str(firmware) if firmware is not None else None,
        )

    def _state(self) -> dict | None:
        return (self.coordinator.data or {}).get(self._serial)

    @property
    def available(self) -> bool:
        return self._state() is not None

    @property
    def is_on(self) -> bool | None:
        data = self._state()
        if data is None:
            return None
        return bool(data.get("opened"))

    @property
    def extra_state_attributes(self) -> dict:
        data = self._state() or {}
        attrs: dict = {}
        if data.get("opened_state_date"):
            attrs["opened_state_date"] = data["opened_state_date"]
        if data.get("battery") is not None:
            attrs["battery_raw"] = data["battery"]
        if data.get("firmware_version") is not None:
            attrs["firmware_version"] = data["firmware_version"]
        return attrs
