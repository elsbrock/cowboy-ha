"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_BIKE_COORDINATOR, CONF_RELEASE_COORDINATOR, DOMAIN
from .coordinator import CowboyBikeCoordinatedEntity, CowboyUpdateCoordinator
from .sensor import CowboySensorEntityDescription

PARALLEL_UPDATES = 1

SENSOR_TYPES: tuple[CowboySensorEntityDescription, ...] = (
    CowboySensorEntityDescription(
        key="stolen",
        translation_key="stolen",
        icon="mdi:car-emergency",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    CowboySensorEntityDescription(
        key="crashed",
        translation_key="crashed",
        icon="mdi:alert",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    CowboySensorEntityDescription(
        key="battery_inserted",
        translation_key="battery_inserted",
        icon="mdi:battery",
        device_class=BinarySensorDeviceClass.PLUG,
    )
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cowboy sensor entries."""
    bike_coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_BIKE_COORDINATOR]
    release_coordinator = hass.data[DOMAIN][config_entry.entry_id][
        CONF_RELEASE_COORDINATOR
    ]
    async_add_entities(
        CowboyBinarySensor(bike_coordinator, description)
        for description in SENSOR_TYPES
    )
    async_add_entities(
        [
            CowboyUpdateBinarySensor(
                release_coordinator,
                description=CowboySensorEntityDescription(
                    key="update_available",
                    translation_key="update_available",
                    icon="mdi:update",
                    device_class=BinarySensorDeviceClass.UPDATE,
                    # Superseded by the `update` platform entity. Kept
                    # registered so existing automations don't break,
                    # but disabled by default for new installs.
                    entity_registry_enabled_default=False,
                ),
            )
        ]
    )


class CowboyBinarySensor(CowboyBikeCoordinatedEntity, BinarySensorEntity):
    """Binary state of a Cowboy."""

    entity_description: CowboySensorEntityDescription

    def __init__(
        self,
        coordinator: CowboyUpdateCoordinator,
        description: CowboySensorEntityDescription,
    ) -> None:
        """Initialize a Cowboy sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._update_state()

    def _update_state(self) -> None:
        """Update state from the latest coordinator snapshot."""
        coordinator_data = self.coordinator.data
        data = coordinator_data if isinstance(coordinator_data, dict) else {}
        self._attr_is_on = data.get(self.entity_description.key)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_state()
        self.async_write_ha_state()


class CowboyUpdateBinarySensor(CowboyBinarySensor):
    """Availability of an update for a Cowboy bike."""

    def _update_state(self) -> None:
        """Update firmware availability from the latest coordinator snapshot.

        This sensor is on if there is a firmware update available and
        the bike firmware is not the latest release. The firmware update
        must not have status: testing.
        """
        coordinator_data = self.coordinator.data
        data = coordinator_data if isinstance(coordinator_data, dict) else {}
        # The API returns `null` (not just missing) for some keys in
        # /releases (e.g. cockpit, wireless_charger). `firmware` itself
        # has been observed null too, and `dict.get(k, default)` only
        # uses the default when the key is *absent*, not when the value
        # is None — hence `or {}` to guard against AttributeError.
        firmware = data.get("firmware") or {}
        firmware_name = firmware.get("name") or ""
        firmware_status = firmware.get("status") or ""

        device_info = self.coordinator.device_info or {}
        sw_version = device_info.get("sw_version") or ""

        self._attr_is_on = (
            firmware_name != sw_version and firmware_status != "testing"
        )
