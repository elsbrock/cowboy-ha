"""Platform for sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfMass,
    UnitOfSpeed,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CONF_BIKE_COORDINATOR, CONF_TRIPS_COORDINATOR, DOMAIN
from .coordinator import (
    CowboyBikeCoordinatedEntity,
    CowboyBikeUpdateCoordinator,
    CowboyTripsUpdateCoordinator,
)


PARALLEL_UPDATES = 1


RIDE_MODE_OPTIONS = [
    "adaptive_eu",
    "static_eu",
    "static_offroad",
    "adaptive_eco_eu",
    "adaptive_us",
    "static_us",
    "adaptive_eco_us",
    "assistance_off",
]


def _parse_iso(value: str | None) -> datetime | None:
    """ISO 8601 string → datetime, tolerant of missing/malformed values."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@dataclass
class CowboySensorEntityDescription(SensorEntityDescription):
    """Describes Cowboy sensor entity."""

    attrs: Callable[[dict[str, Any]], dict[str, Any]] = lambda data: {}
    value_fn: Callable[[dict[str, Any]], StateType] | None = None



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
        entity_registry_visible_default=False,
    ),
    CowboySensorEntityDescription(
        key="remaining_range",
        translation_key="remaining_range",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data['battery_state_of_charge'] / 100 * (
            next(
                (autonomy['full_battery_range'] for autonomy in data.get('autonomies', []) if autonomy['ride_mode'] == data.get('last_ride_mode')),
                data.get('autonomy', 0)
            )
        ),
    ),
    CowboySensorEntityDescription(
        key="battery_health",
        translation_key="battery_health",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:battery-heart",
        value_fn=lambda data: data['autonomy'] / next(
            (autonomy['full_battery_range'] for autonomy in data['autonomies'] if autonomy['ride_mode'] == data['last_ride_mode']),
            None
        ) * 100
    ),
    CowboySensorEntityDescription(
        key="seen_at",
        translation_key="seen_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:cloud-clock",
        value_fn=lambda data: _parse_iso(data.get("seen_at")),
    ),
    CowboySensorEntityDescription(
        key="last_ride_mode",
        translation_key="last_ride_mode",
        device_class=SensorDeviceClass.ENUM,
        options=RIDE_MODE_OPTIONS,
        value_fn=lambda data: data.get("last_ride_mode"),
    ),
    CowboySensorEntityDescription(
        key="last_crash_started_at",
        translation_key="last_crash_started_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alert-circle-outline",
        value_fn=lambda data: _parse_iso(data.get("last_crash_started_at")),
    ),
    CowboySensorEntityDescription(
        key="warranty_ends_at",
        translation_key="warranty_ends_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:shield-check-outline",
        value_fn=lambda data: _parse_iso(data.get("warranty_ends_at")),
    ),
    CowboySensorEntityDescription(
        key="auto_lock",
        translation_key="auto_lock",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:lock-clock",
        value_fn=lambda data: (data.get("pending_settings") or {}).get("auto_lock"),
    ),
    CowboySensorEntityDescription(
        key="displayed_speed",
        translation_key="displayed_speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:speedometer",
        value_fn=lambda data: (
            ((data.get("sku") or {}).get("features") or {}).get("displayed_speeds") or {}
        ).get("default"),
    ),
)


def _last_trip_value(key: str) -> Callable[[dict[str, Any]], StateType]:
    """Build a value function that returns last_trip[key] or None."""
    def _fn(data: dict[str, Any]) -> StateType:
        last_trip = data.get("last_trip")
        if not last_trip:
            return None
        return last_trip.get(key)
    return _fn


def _last_trip_ended_at(data: dict[str, Any]) -> StateType:
    """Return the parsed `ended_at` timestamp from the last trip, if any."""
    last_trip = data.get("last_trip")
    if not last_trip:
        return None
    return _parse_iso(last_trip.get("ended_at"))


TRIPS_SENSOR_TYPES: tuple[CowboySensorEntityDescription, ...] = (
    CowboySensorEntityDescription(
        key="last_trip_distance",
        translation_key="last_trip_distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        suggested_display_precision=1,
        value_fn=_last_trip_value("distance"),
    ),
    CowboySensorEntityDescription(
        key="last_trip_ended_at",
        translation_key="last_trip_ended_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_last_trip_ended_at,
    ),
    CowboySensorEntityDescription(
        key="last_trip_duration",
        translation_key="last_trip_duration",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_last_trip_value("moving_time"),
    ),
    CowboySensorEntityDescription(
        key="last_trip_co2_saved",
        translation_key="last_trip_co2_saved",
        native_unit_of_measurement=UnitOfMass.GRAMS,
        icon="mdi:cloud-check",
        value_fn=_last_trip_value("co2_saved"),
    ),
    CowboySensorEntityDescription(
        key="last_trip_calories",
        translation_key="last_trip_calories",
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=_last_trip_value("calories_burned"),
    ),
    CowboySensorEntityDescription(
        key="last_trip_title",
        translation_key="last_trip_title",
        icon="mdi:bike",
        value_fn=_last_trip_value("title"),
    ),
    CowboySensorEntityDescription(
        key="today_distance",
        translation_key="today_distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        suggested_display_precision=1,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.get("today_distance"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cowboy sensor entries."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    cowboy_coordinator = entry_data[CONF_BIKE_COORDINATOR]
    trips_coordinator = entry_data[CONF_TRIPS_COORDINATOR]
    entities: list[SensorEntity] = [
        CowboySensor(cowboy_coordinator, description) for description in SENSOR_TYPES
    ]
    entities.extend(
        CowboyTripsSensor(trips_coordinator, cowboy_coordinator.device_info, description)
        for description in TRIPS_SENSOR_TYPES
    )
    async_add_entities(entities)


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
        if not self.entity_description.value_fn:
            self._attr_native_value = self.coordinator.data[self.entity_description.key]
        else:
            self._attr_native_value = self.entity_description.value_fn(
                self.coordinator.data
            )
        self._attr_extra_state_attributes = self.entity_description.attrs(
            self.coordinator.data
        )
        self.async_write_ha_state()


class CowboyTripsSensor(
    CoordinatorEntity[CowboyTripsUpdateCoordinator], SensorEntity
):
    """Representation of a Cowboy trip sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    entity_description: CowboySensorEntityDescription

    def __init__(
        self,
        coordinator: CowboyTripsUpdateCoordinator,
        device_info,
        description: CowboySensorEntityDescription,
    ) -> None:
        """Initialize a Cowboy trips sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = device_info
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> StateType | datetime:
        """Return the sensor value derived from coordinator data."""
        data = self.coordinator.data or {}
        if self.entity_description.value_fn:
            return self.entity_description.value_fn(data)
        return data.get(self.entity_description.key)
