"""Define a custom data update coordinator for Cowboy."""

import asyncio
from datetime import timedelta
import logging
from typing import NoReturn

from requests import HTTPError, RequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from ._client import CowboyAPIClient
from .const import ATTRIBUTION, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _raise_update_error(err: RequestException | TimeoutError) -> NoReturn:
    """Translate Cowboy API errors to Home Assistant coordinator errors."""
    if isinstance(err, HTTPError):
        response = err.response
        if response is not None and response.status_code == 401:
            raise ConfigEntryAuthFailed("Invalid Cowboy authentication") from err
    raise UpdateFailed(f"Error communicating with Cowboy API: {err}") from err


def _raise_invalid_response() -> NoReturn:
    """Raise a coordinator error for an unexpected Cowboy response."""
    raise UpdateFailed("Unexpected response from Cowboy API")


class CowboyUpdateCoordinator(DataUpdateCoordinator):
    """Abstract Cowboy coordinator to fetch data from the inofficial API at a set interval."""

    config_entry: ConfigEntry
    device_info: DeviceInfo

    def __init__(
        self,
        hass: HomeAssistant,
        device: DeviceInfo,
        cowboy_api: CowboyAPIClient,
        config_entry: ConfigEntry,
        update_interval=timedelta(minutes=1),
    ) -> None:
        """Initialize the coordinator with the given API client."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=update_interval,
        )
        _LOGGER.info("Initializing CowboyCoordinator")
        self.cowboy_api = cowboy_api
        self.device_info = device


class CowboyBikeUpdateCoordinator(CowboyUpdateCoordinator):
    """Cowboy coordinator to fetch bike data."""

    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoint."""
        try:
            async with asyncio.timeout(30):
                bike = await self.hass.async_add_executor_job(self.cowboy_api.get_bike)
                if not isinstance(bike, dict):
                    _raise_invalid_response()
                # can change over time, so we need to update it
                self.device_info["sw_version"] = bike.get("firmware_version")
                self.device_info["name"] = bike.get("nickname")
                _LOGGER.debug("bike data fetched: %s", bike)
                return bike
        except (RequestException, TimeoutError) as err:
            _raise_update_error(err)


class CowboyReleaseUpdateCoordinator(CowboyUpdateCoordinator):
    """Cowboy coordinator to fetch release data."""

    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoint."""
        try:
            async with asyncio.timeout(30):
                releases = await self.hass.async_add_executor_job(
                    self.cowboy_api.get_releases
                )
                if releases is None:
                    releases = {}
                if not isinstance(releases, dict):
                    _raise_invalid_response()
                firmware = releases.get("firmware")
                if firmware is not None and not isinstance(firmware, dict):
                    _raise_invalid_response()
                _LOGGER.debug("release data fetched: %s", releases)
                return releases
        except (RequestException, TimeoutError) as err:
            _raise_update_error(err)


class CowboyTripsUpdateCoordinator(CowboyUpdateCoordinator):
    """Cowboy coordinator to fetch trip data."""

    async def _async_update_data(self) -> dict:
        """Fetch recent trips and today highlight in a single pass."""
        try:
            async with asyncio.timeout(30):
                recent = await self.hass.async_add_executor_job(
                    self.cowboy_api.get_trips_recent
                )
                highlights = await self.hass.async_add_executor_job(
                    self.cowboy_api.get_trips_highlights
                )
                _LOGGER.debug(
                    "trip data fetched: recent=%s highlights=%s", recent, highlights
                )

                if recent is None:
                    recent = {}
                if highlights is None:
                    highlights = []
                if not isinstance(recent, dict) or not isinstance(highlights, list):
                    _raise_invalid_response()

                trips = recent.get("trips") or []
                if not isinstance(trips, list):
                    _raise_invalid_response()
                last_trip = trips[0] if trips else None
                if trips and not isinstance(last_trip, dict):
                    _raise_invalid_response()

                today_distance = None
                for entry in highlights:
                    if not isinstance(entry, dict):
                        _raise_invalid_response()
                    if entry.get("type") == "today_highlight":
                        payload = entry.get("payload") or {}
                        if not isinstance(payload, dict):
                            _raise_invalid_response()
                        today_distance = payload.get("distance")
                        break

                return {
                    "last_trip": last_trip,
                    "today_distance": today_distance,
                }
        except (RequestException, TimeoutError) as err:
            _raise_update_error(err)


class CowboyBikeCoordinatedEntity(CoordinatorEntity[CowboyBikeUpdateCoordinator]):
    """Defines a base Cowboy entity."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CowboyBikeUpdateCoordinator,
    ) -> None:
        """Initialize the coordinated Cowboy Device."""
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        self._attr_device_info = coordinator.device_info
