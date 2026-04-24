"""Tests for cowboy integration."""
from datetime import timedelta
from unittest.mock import patch
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import device_registry as dr, entity_registry as er
from custom_components.cowboy.const import (
    CONF_BIKE_COORDINATOR,
    CONF_BIKE_ID,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)

MOCK_CONFIG = {
    CONF_USERNAME: "test@example.com",
    CONF_PASSWORD: "test_password",
    CONF_BIKE_ID: 123,
}

MOCK_BIKE_RESPONSE = {
    "data": {
        "bike": {
            "id": 123,
            "nickname": "Test Bike",
            "model": {"name": "Test Model"},
            "serial_number": "CB123456",
            "firmware_version": "1.0.0"
        }
    }
}


def _configure_mock(mock_requests, bike_id=123, nickname="Test Bike"):
    """Wire a mock requests instance to return a well-formed bike response."""
    bike_payload = {
        "data": {
            "bike": {
                "id": bike_id,
                "nickname": nickname,
                "model": {"name": "Test Model"},
                "serial_number": f"CB-{bike_id}",
                "firmware_version": "1.0.0",
            }
        }
    }

    post_response = mock_requests.post.return_value
    post_response.status_code = 200
    post_response.json.return_value = bike_payload
    post_response.headers = {
        "Access-Token": "test-token",
        "Uid": "test@example.com",
        "Client": "test-client",
        "Expiry": "9999999999",
    }

    get_response = mock_requests.get.return_value
    get_response.status_code = 200
    # GET /bikes/{id} returns the bike object directly (not wrapped in "data").
    get_response.json.return_value = bike_payload["data"]["bike"]

    return bike_payload


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for testing."""
    yield


async def test_setup_unload_and_reload_entry(hass: HomeAssistant):
    """Test setup and unload of an entry."""
    with patch('custom_components.cowboy._client.requests') as mock_requests:
        _configure_mock(mock_requests)

        entry = config_entries.ConfigEntry(
            version=2,
            minor_version=1,
            domain=DOMAIN,
            title="Test",
            data=MOCK_CONFIG,
            source="test",
            options={},
            unique_id="123",
            discovery_keys=set(),
        )

        hass.config_entries._entries[entry.entry_id] = entry

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert DOMAIN in hass.data
        assert entry.entry_id in hass.data[DOMAIN]

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        device_registry = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        for device in devices:
            device_registry.async_remove_device(device.id)

        hass.config_entries._entries.pop(entry.entry_id)
        assert not hass.data.get(DOMAIN)


async def test_setup_entry_fails_on_auth_error(hass: HomeAssistant):
    """Test setup with authentication failure."""
    with patch('custom_components.cowboy._client.requests') as mock_requests:
        mock_requests.post.side_effect = Exception("Auth failed")

        entry = config_entries.ConfigEntry(
            version=2,
            minor_version=1,
            domain=DOMAIN,
            title="Test",
            data=MOCK_CONFIG,
            source="test",
            options={},
            unique_id="123",
            discovery_keys=set(),
        )

        hass.config_entries._entries[entry.entry_id] = entry

        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        device_registry = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        for device in devices:
            device_registry.async_remove_device(device.id)

        hass.config_entries._entries.pop(entry.entry_id)
        assert DOMAIN not in hass.data

async def test_scan_interval_option_applied(hass: HomeAssistant):
    """scan_interval from entry options is wired into the bike coordinator."""
    with patch('custom_components.cowboy._client.requests') as mock_requests:
        _configure_mock(mock_requests)

        entry = config_entries.ConfigEntry(
            version=2,
            minor_version=1,
            domain=DOMAIN,
            title="Test",
            data=MOCK_CONFIG,
            source="test",
            options={CONF_SCAN_INTERVAL: 5},
            unique_id="123",
            discovery_keys=set(),
        )

        hass.config_entries._entries[entry.entry_id] = entry

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        bike_coordinator = hass.data[DOMAIN][entry.entry_id][CONF_BIKE_COORDINATOR]
        assert bike_coordinator.update_interval == timedelta(minutes=5)

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        device_registry = dr.async_get(hass)
        for device in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            device_registry.async_remove_device(device.id)

        hass.config_entries._entries.pop(entry.entry_id)




async def test_config_flow_validation(hass: HomeAssistant):
    """Test the config flow validation captures bike_id as unique_id."""
    with patch('custom_components.cowboy._client.requests') as mock_requests:
        _configure_mock(mock_requests)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == "form"
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "test_password",
            },
        )

        assert result["type"] == "create_entry"
        assert result["data"][CONF_BIKE_ID] == 123

        created = next(
            e for e in hass.config_entries._entries.values()
            if e.domain == DOMAIN and e.unique_id == "123"
        )
        assert created is not None

        device_registry = dr.async_get(hass)
        for entry in hass.config_entries._entries.values():
            if entry.domain == DOMAIN:
                devices = dr.async_entries_for_config_entry(
                    device_registry, entry.entry_id
                )
                for device in devices:
                    device_registry.async_remove_device(device.id)

        for entry in hass.config_entries._entries.copy():
            await hass.config_entries.async_remove(entry)


async def test_config_flow_aborts_on_duplicate_bike(hass: HomeAssistant):
    """Adding the same bike twice should abort, not replace."""
    with patch('custom_components.cowboy._client.requests') as mock_requests:
        _configure_mock(mock_requests, bike_id=123, nickname="Bike A")

        existing = config_entries.ConfigEntry(
            version=2,
            minor_version=1,
            domain=DOMAIN,
            title="Bike A",
            data=MOCK_CONFIG,
            source="user",
            options={},
            unique_id="123",
            discovery_keys=set(),
        )
        hass.config_entries._entries[existing.entry_id] = existing

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "test_password",
            },
        )

        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"

        hass.config_entries._entries.pop(existing.entry_id)


async def test_config_flow_allows_second_bike(hass: HomeAssistant):
    """A second bike (different id) from the same account should be allowed."""
    with patch('custom_components.cowboy._client.requests') as mock_requests:
        _configure_mock(mock_requests, bike_id=123, nickname="Bike A")

        first = config_entries.ConfigEntry(
            version=2,
            minor_version=1,
            domain=DOMAIN,
            title="Bike A",
            data=MOCK_CONFIG,
            source="user",
            options={},
            unique_id="123",
            discovery_keys=set(),
        )
        hass.config_entries._entries[first.entry_id] = first

        # Second Cowboy account → different bike in the login response.
        _configure_mock(mock_requests, bike_id=456, nickname="Bike B")

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "test_password",
            },
        )

        assert result["type"] == "create_entry"
        assert result["data"][CONF_BIKE_ID] == 456
        assert result["result"].unique_id == "456"

        # Unload everything cleanly so the coordinator timers don't linger.
        for entry_id in list(hass.config_entries._entries):
            entry = hass.config_entries._entries[entry_id]
            if entry.state == config_entries.ConfigEntryState.LOADED:
                await hass.config_entries.async_unload(entry_id)
                await hass.async_block_till_done()
        for entry_id in list(hass.config_entries._entries):
            await hass.config_entries.async_remove(entry_id)


async def test_migrate_v1_entry_captures_bike_id(hass: HomeAssistant):
    """v1 entries without bike_id should be migrated on setup."""
    with patch('custom_components.cowboy._client.requests') as mock_requests:
        _configure_mock(mock_requests, bike_id=789)

        v1_entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="Legacy",
            data={
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "test_password",
            },
            source="user",
            options={},
            unique_id="Legacy",
            discovery_keys=set(),
        )
        hass.config_entries._entries[v1_entry.entry_id] = v1_entry

        assert await hass.config_entries.async_setup(v1_entry.entry_id)
        await hass.async_block_till_done()

        assert v1_entry.version == 2
        assert v1_entry.data[CONF_BIKE_ID] == 789
        assert v1_entry.unique_id == "789"

        await hass.config_entries.async_unload(v1_entry.entry_id)
        await hass.async_block_till_done()

        device_registry = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(
            device_registry, v1_entry.entry_id
        )
        for device in devices:
            device_registry.async_remove_device(device.id)

        hass.config_entries._entries.pop(v1_entry.entry_id)


async def test_migration_preserves_existing_entities_and_device(hass: HomeAssistant):
    """Migration should keep pre-existing device_tracker entity and device.

    A v1 install has:
      - device registry entry with identifier (DOMAIN, entry_id)
      - device_tracker entity with unique_id "{title}tracker"

    Post-migration both should still resolve to the same records so users
    don't lose history or have to fix up automations.
    """
    with patch('custom_components.cowboy._client.requests') as mock_requests:
        _configure_mock(mock_requests, bike_id=789, nickname="Legacy")

        v1_entry = config_entries.ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="Legacy",
            data={
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "test_password",
            },
            source="user",
            options={},
            unique_id="Legacy",
            discovery_keys=set(),
        )
        hass.config_entries._entries[v1_entry.entry_id] = v1_entry

        # Seed the registries as a v1 install would have them.
        device_registry = dr.async_get(hass)
        pre_device = device_registry.async_get_or_create(
            config_entry_id=v1_entry.entry_id,
            identifiers={(DOMAIN, v1_entry.entry_id)},
            name="Legacy",
        )
        entity_registry = er.async_get(hass)
        pre_tracker = entity_registry.async_get_or_create(
            "device_tracker",
            DOMAIN,
            f"{v1_entry.title}tracker",
            config_entry=v1_entry,
            device_id=pre_device.id,
        )

        assert await hass.config_entries.async_setup(v1_entry.entry_id)
        await hass.async_block_till_done()

        # Device now keyed on bike_id, but it's the SAME device row.
        post_device = device_registry.async_get_device(
            identifiers={(DOMAIN, "789")}
        )
        assert post_device is not None
        assert post_device.id == pre_device.id

        # Tracker unique_id migrated but entity_id (and hence state history)
        # stays the same.
        post_tracker = entity_registry.async_get(pre_tracker.entity_id)
        assert post_tracker is not None
        assert post_tracker.unique_id == f"{v1_entry.entry_id}_tracker"

        await hass.config_entries.async_unload(v1_entry.entry_id)
        await hass.async_block_till_done()

        for device in dr.async_entries_for_config_entry(
            device_registry, v1_entry.entry_id
        ):
            device_registry.async_remove_device(device.id)
        hass.config_entries._entries.pop(v1_entry.entry_id)
