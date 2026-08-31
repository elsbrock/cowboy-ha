"""Tests for Cowboy binary sensors."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from custom_components.cowboy.binary_sensor import (
    SENSOR_TYPES,
    CowboyBinarySensor,
    CowboyUpdateBinarySensor,
)
from custom_components.cowboy.sensor import CowboySensorEntityDescription


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("stolen", False),
        ("crashed", True),
        ("battery_inserted", False),
    ],
)
def test_binary_sensor_uses_initial_data_and_clears_missing_values(key, value):
    """Binary sensors should use the first refresh and not retain stale data."""
    description = next(desc for desc in SENSOR_TYPES if desc.key == key)
    coordinator = MagicMock()
    coordinator.data = {key: value}
    coordinator.config_entry.entry_id = "entry-1"
    coordinator.device_info = {}

    entity = CowboyBinarySensor(coordinator, description)
    assert entity.is_on is value

    coordinator.data = {}
    entity._update_state()
    assert entity.is_on is None


@pytest.mark.parametrize("data", [[1], "invalid"])
def test_binary_sensor_tolerates_malformed_coordinator_data(data):
    """Malformed top-level coordinator data should render unknown."""
    description = next(desc for desc in SENSOR_TYPES if desc.key == "stolen")
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.config_entry.entry_id = "entry-1"
    coordinator.device_info = {}

    entity = CowboyBinarySensor(coordinator, description)
    assert entity.is_on is None

    coordinator.data = {"stolen": True}
    entity._update_state()
    assert entity.is_on is True


def test_update_binary_sensor_uses_initial_data():
    """The legacy update sensor should also use the first refresh."""
    coordinator = MagicMock()
    coordinator.data = {
        "firmware": {"name": "v4.22", "status": "deployed"},
    }
    coordinator.config_entry.entry_id = "entry-1"
    coordinator.device_info = {"sw_version": "v4.21"}
    description = CowboySensorEntityDescription(
        key="update_available",
        device_class=BinarySensorDeviceClass.UPDATE,
    )

    entity = CowboyUpdateBinarySensor(coordinator, description)
    assert entity.is_on is True
