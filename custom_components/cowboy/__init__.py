"""The cowboy integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from ._client import CowboyAPIClient
from .const import (
    CONF_API,
    CONF_BIKE_COORDINATOR,
    CONF_RELEASE_COORDINATOR,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import CowboyBikeUpdateCoordinator, CowboyReleaseUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up cowboy from a config entry."""
    cowboy_api = CowboyAPIClient()
    await hass.async_add_executor_job(
        cowboy_api.login, entry.data["username"], entry.data["password"]
    )

    # all coordinators shall share the same device
    device = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer=MANUFACTURER,
        model=cowboy_api.model,
        serial_number=cowboy_api.serial_number,
    )

    bike_coordinator = CowboyBikeUpdateCoordinator(hass, device, cowboy_api)
    release_coordinator = CowboyReleaseUpdateCoordinator(
        hass, device, cowboy_api, update_interval=timedelta(hours=1)
    )

    await bike_coordinator.async_config_entry_first_refresh()
    await release_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_API: cowboy_api,
        CONF_BIKE_COORDINATOR: bike_coordinator,
        CONF_RELEASE_COORDINATOR: release_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    try:  # noqa: SIM105
        # logging out any of them suffices; we don't care which one
        await hass.async_add_executor_job(
            hass.data[DOMAIN][entry.entry_id][CONF_BIKE_COORDINATOR].logout
        )
    except:  # noqa: E722
        # ignore any errors
        pass
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
