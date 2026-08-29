"""Tests for the Cowboy device tracker."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components import zone
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.cowboy.const import (
    ATTR_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LOC_NAME,
    ATTR_LOC_RECEIVED_AT,
    ATTR_LONGITUDE,
)
from custom_components.cowboy.device_tracker import CowboyTracker


def _coordinator(position):
    """Build a coordinator with a bike position."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "entry-1"
    coordinator.device_info = {}
    coordinator.data = {"position": position}
    return coordinator


def _position(**overrides):
    """Build a complete Cowboy position payload."""
    position = {
        "latitude": "51.5074",
        "longitude": "-0.1278",
        "accuracy": "1.45",
        "address": "London",
        "received_at": "2026-08-29T20:00:00Z",
    }
    position.update(overrides)
    return position


def test_tracker_initializes_from_coordinator_data():
    """The first coordinator refresh should seed the tracker immediately."""
    tracker = CowboyTracker(_coordinator(_position()))

    assert tracker.latitude == 51.5074
    assert tracker.longitude == -0.1278
    assert tracker.location_accuracy == 1.45
    assert tracker.extra_state_attributes == {
        ATTR_ACCURACY: 1.45,
        ATTR_LATITUDE: 51.5074,
        ATTR_LONGITUDE: -0.1278,
        ATTR_LOC_NAME: "London",
        ATTR_LOC_RECEIVED_AT: "2026-08-29T20:00:00Z",
    }


async def test_tracker_coordinates_support_home_zone_lookup(hass: HomeAssistant):
    """Normalized coordinates should work with Home Assistant zone matching."""
    assert await async_setup_component(hass, "zone", {})
    tracker = CowboyTracker(
        _coordinator(
            _position(
                latitude=str(hass.config.latitude),
                longitude=str(hass.config.longitude),
            )
        )
    )

    active_zone = zone.async_active_zone(
        hass, tracker.latitude, tracker.longitude, tracker.location_accuracy
    )

    assert active_zone is not None
    assert active_zone.entity_id == zone.ENTITY_ID_HOME


def test_tracker_replaces_position_on_coordinator_update():
    """A new coordinator snapshot should replace every location field."""
    coordinator = _coordinator(_position())
    tracker = CowboyTracker(coordinator)
    tracker.async_write_ha_state = MagicMock()
    coordinator.data = {
        "position": _position(
            latitude=48.8566,
            longitude=2.3522,
            accuracy=2,
            address="Paris",
            received_at="2026-08-29T21:00:00Z",
        )
    }

    tracker._handle_coordinator_update()

    assert tracker.latitude == 48.8566
    assert tracker.longitude == 2.3522
    assert tracker.location_accuracy == 2.0
    assert tracker.extra_state_attributes[ATTR_LOC_NAME] == "Paris"
    assert tracker.extra_state_attributes[ATTR_LOC_RECEIVED_AT] == (
        "2026-08-29T21:00:00Z"
    )
    tracker.async_write_ha_state.assert_called_once_with()


def test_missing_optional_position_fields_do_not_block_update():
    """Optional location metadata should not prevent fresh GPS coordinates."""
    coordinator = _coordinator(_position())
    tracker = CowboyTracker(coordinator)
    tracker.async_write_ha_state = MagicMock()
    coordinator.data = {
        "position": {
            "latitude": "48.8566",
            "longitude": "2.3522",
        }
    }

    tracker._handle_coordinator_update()

    assert tracker.latitude == 48.8566
    assert tracker.longitude == 2.3522
    assert tracker.location_accuracy == 0.0
    assert tracker.extra_state_attributes[ATTR_LOC_NAME] is None
    assert tracker.extra_state_attributes[ATTR_LOC_RECEIVED_AT] is None


@pytest.mark.parametrize(
    "position",
    [
        None,
        {},
        {"latitude": 51.5074},
        {"longitude": -0.1278},
        "invalid",
    ],
)
def test_incomplete_position_clears_stale_coordinates(position):
    """An incomplete snapshot should not leave old coordinates displayed."""
    coordinator = _coordinator(_position())
    tracker = CowboyTracker(coordinator)
    tracker.async_write_ha_state = MagicMock()
    coordinator.data = {"position": position}

    tracker._handle_coordinator_update()

    assert tracker.latitude is None
    assert tracker.longitude is None
    assert tracker.location_accuracy == 0.0
    assert ATTR_LATITUDE not in tracker.extra_state_attributes
    assert ATTR_LONGITUDE not in tracker.extra_state_attributes
    tracker.async_write_ha_state.assert_called_once_with()


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        ("invalid", -0.1278),
        (51.5074, "invalid"),
        (float("nan"), -0.1278),
        (51.5074, float("inf")),
        (91, -0.1278),
        (51.5074, -181),
    ],
)
def test_invalid_coordinates_are_cleared(latitude, longitude):
    """Invalid Cowboy coordinates should produce an unknown location."""
    tracker = CowboyTracker(
        _coordinator(_position(latitude=latitude, longitude=longitude))
    )

    assert tracker.latitude is None
    assert tracker.longitude is None
    assert ATTR_LATITUDE not in tracker.extra_state_attributes
    assert ATTR_LONGITUDE not in tracker.extra_state_attributes


@pytest.mark.parametrize("accuracy", [None, "invalid", -1, float("nan")])
def test_invalid_accuracy_uses_safe_default(accuracy):
    """Invalid GPS accuracy should not discard otherwise valid coordinates."""
    tracker = CowboyTracker(_coordinator(_position(accuracy=accuracy)))

    assert tracker.latitude == 51.5074
    assert tracker.longitude == -0.1278
    assert tracker.location_accuracy == 0.0
    assert tracker.extra_state_attributes[ATTR_ACCURACY] == 0.0
