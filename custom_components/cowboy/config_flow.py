"""Config flow for cowboy integration."""
from __future__ import annotations

import logging
from typing import Any

from requests import HTTPError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from ._client import CowboyAPIClient
from .const import CONF_AUTH, CONF_BIKE_ID, CONF_NAME, CONF_SCAN_INTERVAL, DOMAIN

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
    bike_id = None

    def __init__(self, bike_id: int | None = None) -> None:
        """Initialize."""
        self.auth = None
        self.bike_id = bike_id

    def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        try:
            self.cowboy_api = CowboyAPIClient(bike_id=self.bike_id)
            resp = self.cowboy_api.login(username, password)
            bike = (
                self.cowboy_api.get_bike()
                if self.bike_id is not None
                else resp["data"]["bike"]
            )
            self.bike_id = bike["id"]
            self.name = bike.get("nickname") or bike["model"]["name"]
        except HTTPError as http_err:
            response = http_err.response
            if response is not None and response.status_code == 401:
                raise InvalidAuth from http_err
            _LOGGER.error("HTTP error while authenticating: %s", http_err)
            raise CannotConnect from http_err
        except Exception as err:
            _LOGGER.error("Unexpected error: %s", err)
            raise CannotConnect from err
        return True


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any], bike_id: int | None = None
) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    hub = CowboyHub(bike_id)

    result = await hass.async_add_executor_job(
        hub.authenticate, data[CONF_USERNAME], data[CONF_PASSWORD]
    )
    if not result:
        raise InvalidAuth

    return {
        f"{CONF_NAME}": hub.name,
        f"{CONF_AUTH}": hub.auth,
        f"{CONF_BIKE_ID}": hub.bike_id,
        f"{CONF_USERNAME}": data[CONF_USERNAME],
        f"{CONF_PASSWORD}": data[CONF_PASSWORD],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for cowboy."""

    VERSION = 2

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Handle configuration by an expired authentication token."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm updated Cowboy credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_input(
                    self.hass,
                    user_input,
                    self._reauth_entry.data[CONF_BIKE_ID],
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._reauth_entry,
                    data_updates={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

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
                await self.async_set_unique_id(str(info[CONF_BIKE_ID]))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info[CONF_NAME], data=info)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return CowboyOptionsFlow()


class CowboyOptionsFlow(config_entries.OptionsFlow):
    """Handle the options flow for cowboy."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            result = self.async_create_entry(title="", data=user_input)
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
            return result

        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, 1)
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=60)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
