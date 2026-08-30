"""Diagnostics support for Taipower AMI."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_CREDENTIAL_FILE, DOMAIN
from .coordinator import TaipowerAmiCoordinator
from .storage import snapshot_summary

TO_REDACT = {CONF_CREDENTIAL_FILE, "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return compact diagnostics with paths and all secrets removed."""

    coordinator: TaipowerAmiCoordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "last_exception_type": (
            type(coordinator.last_exception).__name__
            if coordinator.last_exception is not None
            else None
        ),
        "snapshot": (
            snapshot_summary(coordinator.data) if coordinator.data is not None else None
        ),
        "contains_credentials": False,
    }
