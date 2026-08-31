"""Cowboy device tracker."""

import math

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LOC_NAME,
    ATTR_LOC_RECEIVED_AT,
    ATTR_LONGITUDE,
    CONF_BIKE_COORDINATOR,
    DOMAIN,
)
from .coordinator import CowboyBikeCoordinatedEntity, CowboyBikeUpdateCoordinator

PARALLEL_UPDATES = 1


def _coordinate(value, minimum, maximum) -> float | None:
    """Return a valid numeric coordinate."""
    try:
        coordinate = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(coordinate) or not minimum <= coordinate <= maximum:
        return None
    return coordinate


def _accuracy(value) -> float:
    """Return a valid GPS accuracy in meters."""
    try:
        accuracy = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(accuracy) or accuracy < 0:
        return 0.0
    return accuracy


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cowboy sensor entries."""
    cowboy_coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_BIKE_COORDINATOR]
    async_add_entities([CowboyTracker(cowboy_coordinator)])


class CowboyTracker(CowboyBikeCoordinatedEntity, TrackerEntity):
    """Cowboy device tracker."""

    _attr_force_update = False
    _attr_icon = "mdi:bike"
    _attr_name = None
    _attr_source_type = SourceType.GPS

    def __init__(
        self,
        coordinator: CowboyBikeUpdateCoordinator,
    ) -> None:
        """Initialize the Tracker."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_tracker"
        self._attr_name = None
        self._update_position()

    def _update_position(self) -> None:
        """Replace the current position with the latest coordinator snapshot."""
        data = self.coordinator.data or {}
        position = data.get("position") or {}
        if not isinstance(position, dict):
            position = {}

        latitude = _coordinate(position.get(ATTR_LATITUDE), -90, 90)
        longitude = _coordinate(position.get(ATTR_LONGITUDE), -180, 180)
        if latitude is None or longitude is None:
            latitude = longitude = None

        accuracy = _accuracy(position.get(ATTR_ACCURACY))
        self._attr_latitude = latitude
        self._attr_longitude = longitude
        self._attr_location_accuracy = accuracy
        self._attr_extra_state_attributes = {
            ATTR_ACCURACY: accuracy,
            ATTR_LOC_NAME: position.get("address"),
            ATTR_LOC_RECEIVED_AT: position.get("received_at"),
        }
        if latitude is not None and longitude is not None:
            self._attr_extra_state_attributes.update(
                {
                    ATTR_LATITUDE: latitude,
                    ATTR_LONGITUDE: longitude,
                }
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_position()
        self.async_write_ha_state()
