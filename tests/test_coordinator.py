"""Tests for Cowboy data update coordinators."""

from unittest.mock import MagicMock

import pytest
from requests import ConnectionError, HTTPError, Response, Timeout

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.cowboy._client import CowboyAPIClient
from custom_components.cowboy.const import CONF_BIKE_ID, DOMAIN
from custom_components.cowboy.coordinator import (
    CowboyBikeUpdateCoordinator,
    CowboyReleaseUpdateCoordinator,
    CowboyTripsUpdateCoordinator,
)


def _config_entry() -> config_entries.ConfigEntry:
    """Create a Cowboy config entry."""
    return config_entries.ConfigEntry(
        version=2,
        minor_version=1,
        domain=DOMAIN,
        title="Test",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test_password",
            CONF_BIKE_ID: 123,
        },
        source="test",
        options={},
        unique_id="123",
        discovery_keys=set(),
    )


def _coordinator(hass, coordinator_class):
    """Create a coordinator with successful API defaults."""
    api = MagicMock(spec=CowboyAPIClient)
    api.get_bike.return_value = {"nickname": "Test", "firmware_version": "1.0"}
    api.get_releases.return_value = {}
    api.get_trips_recent.return_value = {"trips": []}
    api.get_trips_highlights.return_value = []
    device = DeviceInfo(identifiers={(DOMAIN, "123")})
    return coordinator_class(hass, device, api, _config_entry()), api


def _http_error(status: int) -> HTTPError:
    """Create an HTTP error with a real requests response."""
    response = Response()
    response.status_code = status
    return HTTPError(f"{status} response", response=response)


@pytest.mark.parametrize(
    ("coordinator_class", "method"),
    [
        (CowboyBikeUpdateCoordinator, "get_bike"),
        (CowboyReleaseUpdateCoordinator, "get_releases"),
        (CowboyTripsUpdateCoordinator, "get_trips_recent"),
    ],
)
async def test_auth_errors_request_reauthentication(
    hass, coordinator_class, method
):
    """Authentication failures should start Home Assistant reauthentication."""
    coordinator, api = _coordinator(hass, coordinator_class)
    error = _http_error(401)
    getattr(api, method).side_effect = error

    with pytest.raises(ConfigEntryAuthFailed) as err:
        await coordinator._async_update_data()

    assert err.value.__cause__ is error


@pytest.mark.parametrize(
    "error",
    [
        ConnectionError("offline"),
        Timeout("timed out"),
        TimeoutError("timed out"),
        _http_error(500),
        HTTPError("missing response"),
    ],
)
async def test_api_errors_are_update_failures(hass, error):
    """Transient API errors should mark coordinator data unavailable."""
    coordinator, api = _coordinator(hass, CowboyBikeUpdateCoordinator)
    api.get_bike.side_effect = error

    with pytest.raises(UpdateFailed) as err:
        await coordinator._async_update_data()

    assert err.value.__cause__ is error


@pytest.mark.parametrize(
    ("coordinator_class", "method", "payload"),
    [
        (CowboyBikeUpdateCoordinator, "get_bike", None),
        (CowboyReleaseUpdateCoordinator, "get_releases", []),
        (
            CowboyReleaseUpdateCoordinator,
            "get_releases",
            {"firmware": "invalid"},
        ),
        (CowboyTripsUpdateCoordinator, "get_trips_recent", []),
        (
            CowboyTripsUpdateCoordinator,
            "get_trips_recent",
            {"trips": [None]},
        ),
        (CowboyTripsUpdateCoordinator, "get_trips_highlights", [None]),
    ],
)
async def test_malformed_responses_are_update_failures(
    hass, coordinator_class, method, payload
):
    """Malformed cloud responses should not escape as unexpected exceptions."""
    coordinator, api = _coordinator(hass, coordinator_class)
    getattr(api, method).return_value = payload

    with pytest.raises(UpdateFailed, match="Unexpected response"):
        await coordinator._async_update_data()


async def test_successful_bike_update_refreshes_device_info(hass):
    """A successful update should return data and update device metadata."""
    coordinator, api = _coordinator(hass, CowboyBikeUpdateCoordinator)

    data = await coordinator._async_update_data()

    assert data is api.get_bike.return_value
    assert coordinator.device_info["name"] == "Test"
    assert coordinator.device_info["sw_version"] == "1.0"
