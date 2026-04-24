"""Diagnostics support for the cowboy integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_BIKE_COORDINATOR, CONF_RELEASE_COORDINATOR, DOMAIN

# Keys stripped from the diagnostics dump. The goal is to make it safe for
# users to paste into a public issue without exposing credentials, PII,
# device identifiers that Cowboy support could use to look up an account,
# or the bike's current location.
TO_REDACT = {
    # credentials / session
    "username",
    "password",
    "email",
    "uid",
    "client",
    "access_token",
    "push_token",
    "passkey",
    "intercom_token",
    # personally identifying info
    "first_name",
    "last_name",
    "nickname",
    "phone_number",
    "emergency_phone_number",
    "avatar_url",
    "avatars",
    "cover_url",
    "instagram_profile_url",
    "facebook_username",
    # device identifiers
    "id",
    "bike_id",
    "mac_address",
    "serial_number",
    "sku_code",
    "uuid",
    # location
    "latitude",
    "longitude",
    "address",
    "country_code",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a Cowboy config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    bike_coordinator = data[CONF_BIKE_COORDINATOR]
    release_coordinator = data[CONF_RELEASE_COORDINATOR]

    # entry.title is user-visible and typically the bike nickname, so it's
    # dropped rather than included. Version info is plenty for debugging.
    return {
        "entry": {
            "version": entry.version,
            "minor_version": entry.minor_version,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "bike": async_redact_data(bike_coordinator.data or {}, TO_REDACT),
        "release": async_redact_data(release_coordinator.data or {}, TO_REDACT),
    }
