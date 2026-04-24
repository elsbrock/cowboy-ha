"""Firmware update entity for Cowboy bikes."""
from __future__ import annotations

from homeassistant.components.update import UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    CONF_BIKE_COORDINATOR,
    CONF_RELEASE_COORDINATOR,
    DOMAIN,
)
from .coordinator import CowboyBikeUpdateCoordinator, CowboyReleaseUpdateCoordinator

# HA caps release_summary at 255 characters.
RELEASE_SUMMARY_MAX_LENGTH = 255


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Cowboy firmware update entity."""
    bike_coordinator: CowboyBikeUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ][CONF_BIKE_COORDINATOR]
    release_coordinator: CowboyReleaseUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ][CONF_RELEASE_COORDINATOR]
    async_add_entities(
        [CowboyFirmwareUpdate(release_coordinator, bike_coordinator)]
    )


class CowboyFirmwareUpdate(
    CoordinatorEntity[CowboyReleaseUpdateCoordinator], UpdateEntity
):
    """Firmware update entity backed by both coordinators.

    The release coordinator drives the entity's primary update cadence
    (it's the source of "what's available"). The bike coordinator
    supplies the installed version, so we also subscribe to its
    listener to re-render whenever it ticks.
    """

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_translation_key = "firmware"
    _attr_title = "Firmware"

    def __init__(
        self,
        release_coordinator: CowboyReleaseUpdateCoordinator,
        bike_coordinator: CowboyBikeUpdateCoordinator,
    ) -> None:
        """Initialize the firmware update entity."""
        super().__init__(release_coordinator)
        self._bike_coordinator = bike_coordinator
        self._attr_device_info = release_coordinator.device_info
        self._attr_unique_id = (
            f"{release_coordinator.config_entry.entry_id}_firmware_update"
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to both coordinators when added to HA."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._bike_coordinator.async_add_listener(
                self._handle_coordinator_update
            )
        )

    @property
    def installed_version(self) -> str | None:
        """Currently installed firmware on the bike."""
        bike = self._bike_coordinator.data or {}
        return bike.get("firmware_version")

    @property
    def latest_version(self) -> str | None:
        """Latest firmware advertised as deployed by the API.

        Returns ``None`` for non-deployed releases (e.g. ``testing``)
        so we don't push test builds at users.
        """
        releases = self.coordinator.data or {}
        firmware = releases.get("firmware") or {}
        if firmware.get("status") != "deployed":
            return None
        return firmware.get("name")

    @property
    def release_summary(self) -> str | None:
        """Short release notes, truncated to HA's 255-char limit."""
        releases = self.coordinator.data or {}
        firmware = releases.get("firmware") or {}
        comment = firmware.get("comment")
        if comment is None:
            return None
        return comment[:RELEASE_SUMMARY_MAX_LENGTH]
