"""1Control Dory sensor entities (battery, last state change)."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DORY_DEVICES,
    DOMAIN,
    DORY_BATTERY_HIGH_MV,
    DORY_BATTERY_MEDIUM_MV,
)
from .coordinator import DoryCoordinator

BATTERY_LEVEL_HIGH = "high"
BATTERY_LEVEL_MEDIUM = "medium"
BATTERY_LEVEL_LOW = "low"


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
    """Battery level categorised from the Dory's 2x CR2032 cell-pair voltage.

    The 1Control API exposes a raw float (e.g. 5929.0) that maps to mV across
    both cells in series. Field reports peg ~5900 as "fresh" (close to the
    2x3.0V nominal). We bucket into low/medium/high per the thresholds in
    const.py and expose the raw value as an attribute for power users.
    """

    _attr_translation_key = "battery"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [BATTERY_LEVEL_LOW, BATTERY_LEVEL_MEDIUM, BATTERY_LEVEL_HIGH]

    def __init__(self, coordinator: DoryCoordinator, device: dict) -> None:
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{DOMAIN}_dory_{self._serial}_battery"

    def _raw_mv(self) -> float | None:
        data = self._state()
        if data is None:
            return None
        value = data.get("battery")
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @property
    def native_value(self) -> str | None:
        mv = self._raw_mv()
        if mv is None:
            return None
        if mv >= DORY_BATTERY_HIGH_MV:
            return BATTERY_LEVEL_HIGH
        if mv >= DORY_BATTERY_MEDIUM_MV:
            return BATTERY_LEVEL_MEDIUM
        return BATTERY_LEVEL_LOW

    @property
    def icon(self) -> str:
        # ENUM device class doesn't auto-pick an icon. Render a battery glyph
        # that matches the current bucket so dashboards get a visual cue.
        state = self.native_value
        if state == BATTERY_LEVEL_HIGH:
            return "mdi:battery"
        if state == BATTERY_LEVEL_MEDIUM:
            return "mdi:battery-50"
        if state == BATTERY_LEVEL_LOW:
            return "mdi:battery-alert"
        return "mdi:battery-unknown"

    @property
    def extra_state_attributes(self) -> dict:
        mv = self._raw_mv()
        return {"raw_mv": mv} if mv is not None else {}


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
