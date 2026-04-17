"""1Control integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OneControlAPI
from .const import CONF_PIN, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _platforms_for_entry(entry: ConfigEntry) -> list[str]:
    """Pick the platform based on whether a PIN is configured.

    No PIN → cover (default). PIN set → lock (prompts for code in the UI).
    """
    if entry.options.get(CONF_PIN):
        return ["lock"]
    return ["cover"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up 1Control from a config entry."""
    session = async_get_clientsession(hass)
    api = OneControlAPI(session, entry.data["email"], entry.data["password"])
    platforms = _platforms_for_entry(entry)

    _purge_stale_entities(hass, entry, platforms)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "platforms": platforms,
    }

    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


def _purge_stale_entities(
    hass: HomeAssistant, entry: ConfigEntry, active_platforms: list[str]
) -> None:
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.domain not in active_platforms:
            _LOGGER.debug(
                "Removing stale %s entity %s (active platforms: %s)",
                entity.domain, entity.entity_id, active_platforms,
            )
            registry.async_remove(entity.entity_id)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    stored = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    # Use the platforms that were actually loaded — options may have already
    # changed (reload flow reads new options before unload runs).
    platforms = stored["platforms"] if stored else _platforms_for_entry(entry)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
