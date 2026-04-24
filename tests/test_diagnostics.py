"""Tests for cowboy diagnostics."""
from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from custom_components.cowboy.const import (
    CONF_API,
    CONF_BIKE_COORDINATOR,
    CONF_BIKE_ID,
    CONF_RELEASE_COORDINATOR,
    DOMAIN,
)
from custom_components.cowboy.diagnostics import async_get_config_entry_diagnostics

REDACTED = "**REDACTED**"

# Shape mirrors a real GET /bikes/{id} response, trimmed to the interesting bits.
BIKE_FIXTURE = {
    "id": 224846,
    "mac_address": "EE0FBBB85496",
    "nickname": "Manfred",
    "serial_number": "CBFM22FM00215",
    "sku_code": "CBA2590GR2-11",
    "firmware_version": "v4.21.5",
    "battery_state_of_charge": 42,
    "autonomy": 51.1,
    "position": {
        "latitude": "52.5200",
        "longitude": "13.4050",
        "address": "Some street in Berlin",
        "accuracy": 1.45,
        "elevation": 84.7,
    },
    "model": {"name": "Cowboy 3", "description": "Cowboy 3"},
}

RELEASE_FIXTURE = {
    "firmware_version": "v4.21.5",
    "release_notes": "Bugfixes",
}


async def test_diagnostics_redacts_sensitive_fields(hass: HomeAssistant):
    """Credentials, identifiers, PII, and GPS coords are masked."""
    entry = ConfigEntry(
        version=2,
        minor_version=1,
        domain=DOMAIN,
        title="Manfred",
        data={
            CONF_USERNAME: "alice@example.com",
            CONF_PASSWORD: "hunter2",
            CONF_BIKE_ID: 224846,
        },
        source="user",
        options={},
        unique_id="224846",
        discovery_keys=set(),
    )

    bike_coordinator = MagicMock()
    bike_coordinator.data = BIKE_FIXTURE
    release_coordinator = MagicMock()
    release_coordinator.data = RELEASE_FIXTURE

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_API: MagicMock(),
        CONF_BIKE_COORDINATOR: bike_coordinator,
        CONF_RELEASE_COORDINATOR: release_coordinator,
    }

    result = await async_get_config_entry_diagnostics(hass, entry)

    # Credentials + bike_id in entry data are masked.
    assert result["entry"]["data"][CONF_USERNAME] == REDACTED
    assert result["entry"]["data"][CONF_PASSWORD] == REDACTED
    assert result["entry"]["data"][CONF_BIKE_ID] == REDACTED
    # title is dropped entirely because it often equals the nickname.
    assert "title" not in result["entry"]

    # Bike payload: identifiers and location gone, telemetry stays.
    bike = result["bike"]
    assert bike["id"] == REDACTED
    assert bike["mac_address"] == REDACTED
    assert bike["nickname"] == REDACTED
    assert bike["serial_number"] == REDACTED
    assert bike["sku_code"] == REDACTED
    assert bike["position"]["latitude"] == REDACTED
    assert bike["position"]["longitude"] == REDACTED
    assert bike["position"]["address"] == REDACTED

    # Non-sensitive telemetry and nested model info survives.
    assert bike["battery_state_of_charge"] == 42
    assert bike["autonomy"] == 51.1
    assert bike["firmware_version"] == "v4.21.5"
    assert bike["position"]["accuracy"] == 1.45
    assert bike["position"]["elevation"] == 84.7
    assert bike["model"] == {"name": "Cowboy 3", "description": "Cowboy 3"}

    # Release payload passes through untouched.
    assert result["release"] == RELEASE_FIXTURE

    hass.data[DOMAIN].pop(entry.entry_id)


async def test_diagnostics_handles_empty_coordinator_data(hass: HomeAssistant):
    """If a coordinator hasn't populated data yet, return empty dicts."""
    entry = ConfigEntry(
        version=2,
        minor_version=1,
        domain=DOMAIN,
        title="Manfred",
        data={
            CONF_USERNAME: "alice@example.com",
            CONF_PASSWORD: "hunter2",
            CONF_BIKE_ID: 1,
        },
        source="user",
        options={},
        unique_id="1",
        discovery_keys=set(),
    )

    bike_coordinator = MagicMock()
    bike_coordinator.data = None
    release_coordinator = MagicMock()
    release_coordinator.data = None

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_API: MagicMock(),
        CONF_BIKE_COORDINATOR: bike_coordinator,
        CONF_RELEASE_COORDINATOR: release_coordinator,
    }

    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["bike"] == {}
    assert result["release"] == {}

    hass.data[DOMAIN].pop(entry.entry_id)
