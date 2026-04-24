"""Unit tests for sensor value functions."""
from datetime import datetime

import pytest

from custom_components.cowboy.sensor import SENSOR_TYPES


BIKE_DATA = {
    "seen_at": "2026-04-24T09:25:32.491+02:00",
    "last_ride_mode": "static_eu",
    "last_crash_started_at": "2024-08-25T18:56:24.856+02:00",
    "warranty_ends_at": "2025-12-18T14:02:23.026+01:00",
    "battery_state_of_charge": 42,
    "autonomy": 51.1,
    "autonomies": [
        {"ride_mode": "static_eu", "full_battery_range": 51.35},
    ],
    "pending_settings": {"auto_lock": 5},
    "sku": {
        "features": {
            "displayed_speeds": {"default": 25, "offroad": None},
        }
    },
}


def _value_fn(key):
    desc = next(d for d in SENSOR_TYPES if d.key == key)
    return desc.value_fn


def test_seen_at_parses_iso_with_offset():
    """ISO 8601 with offset is parsed to a tz-aware datetime."""
    result = _value_fn("seen_at")(BIKE_DATA)
    assert isinstance(result, datetime)
    assert result.tzinfo is not None


@pytest.mark.parametrize(
    "key",
    ["seen_at", "last_crash_started_at", "warranty_ends_at"],
)
def test_timestamp_fields_return_none_when_missing(key):
    """Missing or null timestamps render as unknown rather than raising."""
    assert _value_fn(key)({}) is None
    assert _value_fn(key)({key: None}) is None


def test_last_ride_mode_direct_read():
    """Enum value reads straight from the top-level payload."""
    assert _value_fn("last_ride_mode")(BIKE_DATA) == "static_eu"
    assert _value_fn("last_ride_mode")({}) is None


def test_auto_lock_reads_nested_pending_settings():
    """auto_lock lives under pending_settings and tolerates its absence."""
    assert _value_fn("auto_lock")(BIKE_DATA) == 5
    assert _value_fn("auto_lock")({}) is None
    assert _value_fn("auto_lock")({"pending_settings": None}) is None


def test_displayed_speed_reads_deeply_nested():
    """displayed_speed is nested three levels; every level may be absent."""
    assert _value_fn("displayed_speed")(BIKE_DATA) == 25
    assert _value_fn("displayed_speed")({}) is None
    assert _value_fn("displayed_speed")({"sku": None}) is None
    assert _value_fn("displayed_speed")({"sku": {"features": None}}) is None
