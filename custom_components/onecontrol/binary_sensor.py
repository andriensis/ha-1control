"""1Control Dory binary sensor entities (door/gate position sensors)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DORY_DEVICES, DOMAIN
from .coordinator import DoryCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 1Control Dory binary sensors from a config entry."""
    coordinator: DoryCoordinator = hass.data[DOMAIN][entry.entry_id]["dory_coordinator"]
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
