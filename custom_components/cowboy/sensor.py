"""Platform for sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfMass, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_BIKE_COORDINATOR, DOMAIN
from .coordinator import CowboyBikeCoordinatedEntity, CowboyBikeUpdateCoordinator


@dataclass
class CowboySensorEntityDescription(SensorEntityDescription):
    """Describes Cowboy sensor entity."""

    attrs: Callable[[dict[str, Any]], dict[str, Any]] = lambda data: {}


SENSOR_TYPES: tuple[CowboySensorEntityDescription, ...] = (
    CowboySensorEntityDescription(
        key="total_distance",
        translation_key="total_distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        suggested_display_precision=0,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    CowboySensorEntityDescription(
        key="total_duration",
        translation_key="total_duration",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:clock-outline",
    ),
    CowboySensorEntityDescription(
        key="total_co2_saved",
        translation_key="total_co2_saved",
        native_unit_of_measurement=UnitOfMass.GRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:cloud-check",
    ),
    CowboySensorEntityDescription(
        key="battery_state_of_charge",
        translation_key="battery_state_of_charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    CowboySensorEntityDescription(
        key="pcb_battery_state_of_charge",
        translation_key="pcb_battery_state_of_charge",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-heart",
        entity_registry_visible_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cowboy sensor entries."""
    cowboy_coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_BIKE_COORDINATOR]
    async_add_entities(
        CowboySensor(cowboy_coordinator, description) for description in SENSOR_TYPES
    )


class CowboySensor(CowboyBikeCoordinatedEntity, SensorEntity):
    """Representation of a Cowboy Bike."""

    entity_description: CowboySensorEntityDescription

    def __init__(
        self,
        coordinator: CowboyBikeUpdateCoordinator,
        description: CowboySensorEntityDescription,
    ) -> None:
        """Initialize a Cowboy sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.coordinator.data[self.entity_description.key]
        self._attr_extra_state_attributes = self.entity_description.attrs(
            self.coordinator.data
        )
        self.async_write_ha_state()
