"""The cowboy integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo

from ._client import CowboyAPIClient
from .const import (
    CONF_API,
    CONF_BIKE_COORDINATOR,
    CONF_BIKE_ID,
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
    Platform.UPDATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up cowboy from a config entry."""
    bike_id = entry.data[CONF_BIKE_ID]
    cowboy_api = CowboyAPIClient(bike_id=bike_id)
    await hass.async_add_executor_job(
        cowboy_api.login, entry.data["username"], entry.data["password"]
    )

    # Fetch the pinned bike explicitly — the active bike in the login response
    # may not be the one this entry tracks.
    bike = await hass.async_add_executor_job(cowboy_api.get_bike)

    # Device identifier is keyed on bike_id so the registry entry survives
    # config-entry recreation and stays stable across reloads.
    device = DeviceInfo(
        identifiers={(DOMAIN, str(bike_id))},
        name=bike.get("nickname") or bike["model"]["name"],
        manufacturer=MANUFACTURER,
        model=bike["model"]["name"],
        serial_number=bike.get("serial_number"),
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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries to the current schema."""
    _LOGGER.debug("Migrating cowboy entry from version %s", entry.version)

    if entry.version == 1:
        # v1 entries don't know their bike_id. Log in with stored credentials
        # and capture it from the active bike. Safe: v1 users only had one
        # bike on their account because the integration couldn't handle more.
        client = CowboyAPIClient()
        try:
            response = await hass.async_add_executor_job(
                client.login, entry.data["username"], entry.data["password"]
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Cowboy v1→v2 migration failed: unable to log in: %s", err)
            return False

        bike_id = response["data"]["bike"]["id"]

        # Rewrite the device_tracker entity's unique_id from the old
        # "{title}tracker" format to "{entry_id}_tracker" so its entity_id
        # stays stable across the upgrade.
        ent_reg = er.async_get(hass)
        old_tracker_uid = f"{entry.title}tracker"
        new_tracker_uid = f"{entry.entry_id}_tracker"
        tracker_entity = ent_reg.async_get_entity_id(
            "device_tracker", DOMAIN, old_tracker_uid
        )
        if tracker_entity is not None:
            ent_reg.async_update_entity(
                tracker_entity, new_unique_id=new_tracker_uid
            )

        # Rewrite the device registry identifier from (DOMAIN, entry_id) to
        # (DOMAIN, str(bike_id)) so sensor/binary_sensor/device_tracker
        # entities stay linked to the same device across the upgrade.
        dev_reg = dr.async_get(hass)
        existing_device = dev_reg.async_get_device(
            identifiers={(DOMAIN, entry.entry_id)}
        )
        if existing_device is not None:
            dev_reg.async_update_device(
                existing_device.id,
                new_identifiers={(DOMAIN, str(bike_id))},
            )

        new_data = {**entry.data, CONF_BIKE_ID: bike_id}
        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            unique_id=str(bike_id),
            version=2,
        )

        try:  # noqa: SIM105
            await hass.async_add_executor_job(client.logout)
        except Exception:  # noqa: BLE001
            pass

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    try:  # noqa: SIM105
        # Best-effort: invalidate the session on Cowboy's side. May 401 if
        # the token already expired, which is fine.
        await hass.async_add_executor_job(
            hass.data[DOMAIN][entry.entry_id][CONF_API].logout
        )
    except:  # noqa: E722
        # ignore any errors
        pass
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
