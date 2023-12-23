"""Config flow for cowboy integration."""
from __future__ import annotations

import logging
from typing import Any

from requests import HTTPError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from ._client import CowboyAPIClient
from .const import CONF_AUTH, CONF_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class CowboyHub:
    """Cowboy Hub that authenticates with the API."""

    cowboy_api = None
    name = None

    def __init__(self) -> None:
        """Initialize."""
        self.auth = None

    def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        try:
            self.cowboy_api = CowboyAPIClient()
            resp = self.cowboy_api.login(username, password)
            self.name = resp["data"]["bike"]["nickname"]
        except HTTPError as http_err:
            if http_err.response.status_code == 401:
                raise InvalidAuth
        except Exception as err:
            _LOGGER.error("Unexpected error: %s", err)
            raise CannotConnect
        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    hub = CowboyHub()

    result = await hass.async_add_executor_job(
        hub.authenticate, data[CONF_USERNAME], data[CONF_PASSWORD]
    )
    if not result:
        raise InvalidAuth

    return {
        f"{CONF_NAME}": hub.name,
        f"{CONF_AUTH}": hub.auth,
        f"{CONF_USERNAME}": data[CONF_USERNAME],
        f"{CONF_PASSWORD}": data[CONF_PASSWORD],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for cowboy."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info[CONF_NAME])
                return self.async_create_entry(title=info[CONF_NAME], data=info)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
