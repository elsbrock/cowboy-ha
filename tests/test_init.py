"""Tests for cowboy integration."""
from unittest.mock import patch
import pytest
from homeassistant import config_entries, setup
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import device_registry as dr
from custom_components.cowboy.const import DOMAIN
from custom_components.cowboy._client import CowboyAPIClient

# This is an example configuration entry
MOCK_CONFIG = {
    CONF_USERNAME: "test@example.com",
    CONF_PASSWORD: "test_password"
}

MOCK_BIKE_RESPONSE = {
    "data": {
        "bike": {
            "id": "123",
            "nickname": "Test Bike",
            "model": {"name": "Test Model"},
            "serial_number": "CB123456",
            "firmware_version": "1.0.0"
        }
    }
}

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for testing."""
    yield

async def test_setup_unload_and_reload_entry(hass: HomeAssistant):
    """Test setup and unload of an entry."""
    # Mock both the API client and requests to avoid actual API calls
    with patch('custom_components.cowboy._client.requests') as mock_requests:
        # Configure the mock response
        mock_response = mock_requests.post.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_BIKE_RESPONSE
        mock_response.headers = {
            "Access-Token": "test-token",
            "Uid": "test@example.com",
            "Client": "test-client",
            "Expiry": "9999999999"
        }

        # Test that we can setup the entry
        entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="Test",
            data=MOCK_CONFIG,
            source="test",
            options={},
            unique_id="uniqueid",
            discovery_keys=set(),
        )

        # Add entry to Home Assistant
        hass.config_entries._entries[entry.entry_id] = entry

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check that the entry is loaded
        assert DOMAIN in hass.data
        assert entry.entry_id in hass.data[DOMAIN]

        # Test that we can unload the entry
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        # Clean up devices
        device_registry = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        for device in devices:
            device_registry.async_remove_device(device.id)

        # Clean up the entry
        hass.config_entries._entries.pop(entry.entry_id)
        assert not hass.data.get(DOMAIN)

async def test_setup_entry_fails_on_auth_error(hass: HomeAssistant):
    """Test setup with authentication failure."""
    with patch('custom_components.cowboy._client.requests') as mock_requests:
        # Configure the mock to simulate auth failure
        mock_requests.post.side_effect = Exception("Auth failed")

        entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="Test",
            data=MOCK_CONFIG,
            source="test",
            options={},
            unique_id="uniqueid",
            discovery_keys=set(),
        )

        # Add entry to Home Assistant
        hass.config_entries._entries[entry.entry_id] = entry

        # Setup should fail
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Clean up devices
        device_registry = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        for device in devices:
            device_registry.async_remove_device(device.id)

        # Clean up the entry
        hass.config_entries._entries.pop(entry.entry_id)
        # Entry should not be loaded
        assert DOMAIN not in hass.data

async def test_config_flow_validation(hass: HomeAssistant):
    """Test the config flow validation."""
    with patch('custom_components.cowboy._client.requests') as mock_requests:
        # Configure the mock response
        mock_response = mock_requests.post.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_BIKE_RESPONSE
        mock_response.headers = {
            "Access-Token": "test-token",
            "Uid": "test@example.com",
            "Client": "test-client",
            "Expiry": "9999999999"
        }

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == "form"
        assert result["step_id"] == "user"

        # Test form submission
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_CONFIG
        )

        assert result["type"] == "create_entry"

        # Clean up devices for any created entries
        device_registry = dr.async_get(hass)
        for entry in hass.config_entries._entries.values():
            if entry.domain == DOMAIN:
                devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
                for device in devices:
                    device_registry.async_remove_device(device.id)

        # Clean up any config entries that were created
        for entry in hass.config_entries._entries.copy():
            await hass.config_entries.async_remove(entry)
