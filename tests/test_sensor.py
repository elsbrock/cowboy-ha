"""Unit tests for sensor value functions."""
from datetime import datetime

import pytest

from custom_components.cowboy.sensor import SENSOR_TYPES, TRIPS_SENSOR_TYPES, _parse_iso


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


def _trip_descriptions_by_key() -> dict:
    return {desc.key: desc for desc in TRIPS_SENSOR_TYPES}


SAMPLE_TRIP = {
    "id": 42,
    "distance": 1.83,
    "moving_time": 414,
    "duration": 488,
    "ended_at": "2026-04-14T21:40:49+02:00",
    "title": "Cloudy Evening Ride",
    "co2_saved": 229,
    "calories_burned": 21.228,
}


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


def test_parse_iso_valid():
    """ISO strings parse into datetimes."""
    parsed = _parse_iso("2026-04-14T21:40:49+02:00")
    assert isinstance(parsed, datetime)
    assert parsed.year == 2026
    assert parsed.month == 4
    assert parsed.day == 14


def test_parse_iso_handles_none_and_bad_input():
    """None and garbage return None rather than raising."""
    assert _parse_iso(None) is None
    assert _parse_iso("") is None
    assert _parse_iso("not-a-date") is None


def test_trip_value_functions_with_last_trip():
    """Value functions return the expected fields when a trip is present."""
    data = {"last_trip": SAMPLE_TRIP, "today_distance": 4.2}
    descriptions = _trip_descriptions_by_key()

    assert descriptions["last_trip_distance"].value_fn(data) == 1.83
    assert descriptions["last_trip_duration"].value_fn(data) == 414
    assert descriptions["last_trip_co2_saved"].value_fn(data) == 229
    assert descriptions["last_trip_calories"].value_fn(data) == 21.228
    assert descriptions["last_trip_title"].value_fn(data) == "Cloudy Evening Ride"

    ended_at = descriptions["last_trip_ended_at"].value_fn(data)
    assert isinstance(ended_at, datetime)
    assert ended_at.year == 2026

    assert descriptions["today_distance"].value_fn(data) == 4.2


def test_trip_value_functions_tolerate_missing_last_trip():
    """All last_trip sensors return None when no trip is present."""
    data = {"last_trip": None, "today_distance": None}
    descriptions = _trip_descriptions_by_key()

    for key in (
        "last_trip_distance",
        "last_trip_ended_at",
        "last_trip_duration",
        "last_trip_co2_saved",
        "last_trip_calories",
        "last_trip_title",
    ):
        assert descriptions[key].value_fn(data) is None, f"{key} should be None"

    assert descriptions["today_distance"].value_fn(data) is None


def test_trip_value_functions_tolerate_empty_dict():
    """Sensors tolerate a completely empty payload as well."""
    data: dict = {}

    for desc in TRIPS_SENSOR_TYPES:
        assert desc.value_fn(data) is None, f"{desc.key} should be None on empty data"
