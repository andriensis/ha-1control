"""Shared DataUpdateCoordinator for Dory door/gate sensors.

Both the binary_sensor and sensor platforms read from this single coordinator
so the cloud is only polled once per interval regardless of how many entity
types we expose per Dory.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OneControlAPI, OneControlAPIError

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
