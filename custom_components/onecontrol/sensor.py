"""1Control Dory sensor entities (battery, last state change)."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
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
    """Set up Dory sensor entities from a config entry."""
    coordinator: DoryCoordinator = hass.data[DOMAIN][entry.entry_id]["dory_coordinator"]
    configured = entry.data.get(CONF_DORY_DEVICES, [])

    entities: list[SensorEntity] = []
    for device in configured:
        entities.append(OneControlDoryBatterySensor(coordinator, device))
        entities.append(OneControlDoryLastChangedSensor(coordinator, device))
    async_add_entities(entities)


class _DorySensorBase(CoordinatorEntity[DoryCoordinator], SensorEntity):
    """Shared plumbing for Dory-derived sensor entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DoryCoordinator, device: dict) -> None:
        super().__init__(coordinator)
        self._serial: int = device["serial"]

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
        # Mirror binary_sensor logic: stay available as long as we have any
        # cached snapshot for this serial. See binary_sensor.py for rationale.
        return self._state() is not None


class OneControlDoryBatterySensor(_DorySensorBase):
    """Raw battery reading reported by the Dory.

    Units unverified — the 1Control API exposes the value as a float (e.g. 5929.0)
    with no documented scale. Surfaced as-is so users can build their own
    template sensors / thresholds without us guessing wrong.
    """

    _attr_translation_key = "battery"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:battery"

    def __init__(self, coordinator: DoryCoordinator, device: dict) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{DOMAIN}_dory_{self._serial}_battery"

    @property
    def native_value(self) -> float | None:
        data = self._state()
        if data is None:
            return None
        value = data.get("battery")
        return float(value) if value is not None else None


class OneControlDoryLastChangedSensor(_DorySensorBase):
    """Timestamp of the Dory's most recent open/close transition."""

    _attr_translation_key = "last_state_change"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DoryCoordinator, device: dict) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{DOMAIN}_dory_{self._serial}_last_state_change"

    @property
    def native_value(self) -> datetime | None:
        data = self._state()
        if data is None:
            return None
        raw = data.get("opened_state_date")
        if not raw:
            return None
        # API returns ISO-8601 with a "Z" suffix; fromisoformat needs +00:00.
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None
