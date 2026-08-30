"""Sensor entities for Taipower AMI."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AmiSnapshot
from .const import DOMAIN
from .coordinator import TaipowerAmiCoordinator
from .storage import derived_values


@dataclass(frozen=True, kw_only=True)
class TaipowerAmiSensorDescription(SensorEntityDescription):
    """Describe a derived AMI sensor."""

    value_fn: Callable[[AmiSnapshot], float | str | None]


ENERGY_DESCRIPTIONS = (
    TaipowerAmiSensorDescription(
        key="latest_15m",
        translation_key="latest_15m",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=lambda snapshot: derived_values(snapshot)["latest_15m"],
    ),
    TaipowerAmiSensorDescription(
        key="today",
        translation_key="today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=3,
        value_fn=lambda snapshot: derived_values(snapshot)["today"],
    ),
    TaipowerAmiSensorDescription(
        key="this_month",
        translation_key="this_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=3,
        value_fn=lambda snapshot: derived_values(snapshot)["this_month"],
    ),
    TaipowerAmiSensorDescription(
        key="this_year",
        translation_key="this_year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=3,
        value_fn=lambda snapshot: derived_values(snapshot)["this_year"],
    ),
    TaipowerAmiSensorDescription(
        key="comparison_delta",
        translation_key="comparison_delta",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda snapshot: derived_values(snapshot)["comparison_delta"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Taipower AMI sensors."""

    coordinator: TaipowerAmiCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            TaipowerAmiSensor(coordinator, entry, description)
            for description in ENERGY_DESCRIPTIONS
        ]
        + [TaipowerAmiStatusSensor(coordinator, entry)]
    )


class TaipowerAmiEntity(CoordinatorEntity[TaipowerAmiCoordinator]):
    """Base entity shared by the integration platforms."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TaipowerAmiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Taipower AMI",
            manufacturer="Taiwan Power Company",
            model="AMI web data (unofficial)",
        )


class TaipowerAmiSensor(TaipowerAmiEntity, SensorEntity):
    """A compact derived value without large row attributes."""

    entity_description: TaipowerAmiSensorDescription

    def __init__(
        self,
        coordinator: TaipowerAmiCoordinator,
        entry: ConfigEntry,
        description: TaipowerAmiSensorDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self):
        """Return the latest derived value."""

        return self.entity_description.value_fn(self.coordinator.data)


class TaipowerAmiStatusSensor(TaipowerAmiEntity, SensorEntity):
    """Expose refresh health and small endpoint counts only."""

    _attr_translation_key = "status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:transmission-tower"

    def __init__(self, coordinator: TaipowerAmiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self) -> str:
        return "ok"

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        snapshot = self.coordinator.data
        return {
            "fetched_at": snapshot.fetched_at.isoformat(),
            "target_day": snapshot.target_day.isoformat(),
            "fifteen_minute_rows": len(snapshot.fifteen_minutes),
            "hourly_rows": len(snapshot.hourly),
            "daily_rows": len(snapshot.daily),
            "monthly_rows": len(snapshot.monthly),
            "comparison_rows": len(snapshot.comparison),
            "contains_credentials": False,
        }
