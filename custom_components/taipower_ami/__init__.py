"""Taipower AMI Home Assistant integration."""

from __future__ import annotations

import asyncio

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTRY_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, SERVICE_REFRESH_DATA
from .coordinator import TaipowerAmiCoordinator

PLATFORMS = (Platform.SENSOR, Platform.BUTTON)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up integration-level Taipower AMI service actions."""

    _async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Taipower AMI from a config entry."""

    coordinator = TaipowerAmiCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Taipower AMI config entry."""

    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    hass.data[DOMAIN].pop(entry.entry_id, None)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
    return True


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_REFRESH_DATA):
        return

    async def _async_refresh(call: ServiceCall) -> None:
        coordinators = hass.data.get(DOMAIN, {})
        entry_id = call.data.get(CONF_ENTRY_ID)
        if entry_id is not None:
            coordinator = coordinators.get(entry_id)
            if coordinator is None:
                raise ServiceValidationError(
                    "No loaded Taipower AMI config entry exists for "
                    f"entry_id {entry_id!r}"
                )
            await coordinator.async_request_refresh()
            return
        await asyncio.gather(
            *(
                coordinator.async_request_refresh()
                for coordinator in coordinators.values()
            )
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_DATA,
        _async_refresh,
        schema=vol.Schema({vol.Optional(CONF_ENTRY_ID): cv.string}),
    )
