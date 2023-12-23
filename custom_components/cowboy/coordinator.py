"""Define a custom data update coordinator for Cowboy."""

import asyncio
from datetime import timedelta
import logging

from requests import HTTPError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from ._client import CowboyAPIClient
from .const import ATTRIBUTION, DOMAIN

_LOGGER = logging.getLogger(__name__)


class CowboyUpdateCoordinator(DataUpdateCoordinator):
    """Abstract Cowboy coordinator to fetch data from the inofficial API at a set interval."""

    config_entry: ConfigEntry
    device_info: DeviceInfo

    def __init__(
        self,
        hass: HomeAssistant,
        device: DeviceInfo,
        cowboy_api: CowboyAPIClient,
        update_interval=timedelta(minutes=1),
    ) -> None:
        """Initialize the coordinator with the given API client."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)
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
                # can change over time, so we need to update it
                self.device_info["sw_version"] = bike.get("firmware_version")
                self.device_info["name"] = bike.get("nickname")
                _LOGGER.debug("bike data fetched: %s", bike)
                return bike
        except HTTPError as http_err:
            if http_err.response.status_code == 401:
                raise UpdateFailed("Unable to fetch data from Cowboy API") from http_err
            raise UpdateFailed(
                f"Error communicating with API: {http_err}"
            ) from http_err


class CowboyReleaseUpdateCoordinator(CowboyUpdateCoordinator):
    """Cowboy coordinator to fetch release data."""

    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoint."""
        try:
            async with asyncio.timeout(30):
                releases = await self.hass.async_add_executor_job(
                    self.cowboy_api.get_releases
                )
                _LOGGER.debug("release data fetched: %s", releases)
                return releases
        except HTTPError as http_err:
            if http_err.response.status_code == 401:
                raise UpdateFailed("Unable to fetch data from Cowboy API") from http_err
            raise UpdateFailed(
                f"Error communicating with API: {http_err}"
            ) from http_err


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
