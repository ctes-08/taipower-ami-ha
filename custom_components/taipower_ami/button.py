"""Button entities for Taipower AMI."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import TaipowerAmiCoordinator
from .sensor import TaipowerAmiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the manual refresh button."""

    coordinator: TaipowerAmiCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TaipowerAmiRefreshButton(coordinator, entry)])


class TaipowerAmiRefreshButton(TaipowerAmiEntity, ButtonEntity):
    """Request an immediate read-only refresh."""

    _attr_translation_key = "refresh"
    _attr_device_class = ButtonDeviceClass.UPDATE

    def __init__(self, coordinator: TaipowerAmiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_refresh"

    async def async_press(self) -> None:
        """Refresh through the coordinator."""

        await self.coordinator.async_request_refresh()
