"""Tests for cowboy integration."""
from datetime import timedelta
from unittest.mock import MagicMock, patch
import pytest
from requests import ConnectionError, HTTPError, Response
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
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


def _entry(hass: HomeAssistant, **kwargs) -> MockConfigEntry:
    """Create a Cowboy config entry and register it with Home Assistant."""
    entry = MockConfigEntry(
        version=2,
        minor_version=1,
        domain=DOMAIN,
        title="Test",
        data=MOCK_CONFIG,
        source="test",
        options={},
        unique_id="123",
        **kwargs,
    )
    entry.add_to_hass(hass)
    return entry


def _http_error(status: int) -> HTTPError:
    """Create an HTTP error with a real requests response."""
    response = Response()
    response.status_code = status
    return HTTPError(f"{status} response", response=response)


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
    get_response.headers = {}
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

        entry = MockConfigEntry(
            version=2,
            minor_version=1,
            domain=DOMAIN,
            title="Test",
            data=MOCK_CONFIG,
            source="test",
            options={},
            unique_id="123",
        )

        entry.add_to_hass(hass)

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

        await hass.config_entries.async_remove(entry.entry_id)
        assert not hass.data.get(DOMAIN)


async def test_setup_entry_fails_on_auth_error(hass: HomeAssistant):
    """Test setup with authentication failure."""
    entry = _entry(hass)

    client = MagicMock()
    client.login.side_effect = _http_error(401)
    with patch("custom_components.cowboy.CowboyAPIClient", return_value=client):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR
    assert DOMAIN not in hass.data


async def test_setup_entry_retries_connection_errors(hass: HomeAssistant):
    """Test setup retries transient API failures."""
    entry = _entry(hass)

    client = MagicMock()
    client.login.side_effect = ConnectionError("offline")
    with patch("custom_components.cowboy.CowboyAPIClient", return_value=client):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY
    assert DOMAIN not in hass.data


async def test_setup_entry_retries_malformed_bike_response(hass: HomeAssistant):
    """Test setup retries when the API returns incomplete bike data."""
    entry = _entry(hass)

    client = MagicMock()
    client.get_bike.return_value = {"nickname": "Test"}
    with patch("custom_components.cowboy.CowboyAPIClient", return_value=client):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY
    assert DOMAIN not in hass.data


async def test_setup_entry_ignores_secondary_endpoint_failure(hass: HomeAssistant):
    """Test a release API outage does not block core bike entities."""
    entry = _entry(hass)

    client = MagicMock()
    client.get_bike.return_value = MOCK_BIKE_RESPONSE["data"]["bike"]
    client.get_releases.side_effect = ConnectionError("offline")
    client.get_trips_recent.return_value = {"trips": []}
    client.get_trips_highlights.return_value = []
    with patch("custom_components.cowboy.CowboyAPIClient", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is config_entries.ConfigEntryState.LOADED
        assert await hass.config_entries.async_unload(entry.entry_id)

async def test_scan_interval_option_applied(hass: HomeAssistant):
    """scan_interval from entry options is wired into the bike coordinator."""
    with patch('custom_components.cowboy._client.requests') as mock_requests:
        _configure_mock(mock_requests)

        entry = MockConfigEntry(
            version=2,
            minor_version=1,
            domain=DOMAIN,
            title="Test",
            data=MOCK_CONFIG,
            source="test",
            options={CONF_SCAN_INTERVAL: 5},
            unique_id="123",
        )

        entry.add_to_hass(hass)

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

        await hass.config_entries.async_remove(entry.entry_id)


async def test_options_flow_reloads_with_new_interval(hass: HomeAssistant):
    """Changing the polling interval should reload and take effect.

    Asserting only that a reload was requested is not enough: the options are
    written by the options flow manager *after* async_step_init returns, so a
    reload triggered from inside that step runs against the old options and the
    new interval is silently ignored.
    """
    with patch("custom_components.cowboy._client.requests") as mock_requests:
        _configure_mock(mock_requests)
        entry = _entry(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][entry.entry_id][CONF_BIKE_COORDINATOR]
        assert coordinator.update_interval == timedelta(minutes=1)

        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_SCAN_INTERVAL: 5}
        )
        await hass.async_block_till_done()

        assert result["type"] == "create_entry"
        assert entry.options[CONF_SCAN_INTERVAL] == 5

        reloaded = hass.data[DOMAIN][entry.entry_id][CONF_BIKE_COORDINATOR]
        assert reloaded.update_interval == timedelta(minutes=5)

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()




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
            e for e in hass.config_entries.async_entries(DOMAIN)
            if e.unique_id == "123"
        )
        assert created is not None

        device_registry = dr.async_get(hass)
        for entry in hass.config_entries.async_entries(DOMAIN):
            devices = dr.async_entries_for_config_entry(
                device_registry, entry.entry_id
            )
            for device in devices:
                device_registry.async_remove_device(device.id)

        for entry in hass.config_entries.async_entries(DOMAIN):
            await hass.config_entries.async_remove(entry.entry_id)


async def test_reauthentication_updates_credentials(hass: HomeAssistant):
    """Test successful reauthentication updates the existing entry."""
    entry = _entry(hass)

    with patch("custom_components.cowboy._client.requests") as mock_requests:
        _configure_mock(mock_requests)
        login_payload = MOCK_BIKE_RESPONSE | {
            "data": {
                "bike": MOCK_BIKE_RESPONSE["data"]["bike"] | {"id": 456}
            }
        }
        mock_requests.post.return_value.json.return_value = login_payload
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )

        assert result["type"] == "form"
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "new@example.com",
                CONF_PASSWORD: "new_password",
            },
        )
        # A successful reauth reloads the entry. Let that finish while the
        # transport is still mocked, or it races with test teardown.
        await hass.async_block_till_done()

        assert result["type"] == "abort"
        assert result["reason"] == "reauth_successful"
        assert entry.data[CONF_USERNAME] == "new@example.com"
        assert entry.data[CONF_PASSWORD] == "new_password"
        assert entry.data[CONF_BIKE_ID] == 123
        # The reload issues further requests, so assert the pinned bike was
        # fetched rather than that it was fetched last.
        assert any(
            call.args[0].endswith("/bikes/123")
            for call in mock_requests.get.call_args_list
        )

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_reauthentication_rejects_invalid_credentials(hass: HomeAssistant):
    """Test invalid updated credentials keep the reauthentication form open."""
    entry = _entry(hass)

    with patch("custom_components.cowboy._client.requests") as mock_requests:
        mock_requests.post.return_value.raise_for_status.side_effect = _http_error(401)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "wrong_password",
            },
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_config_flow_aborts_on_duplicate_bike(hass: HomeAssistant):
    """Adding the same bike twice should abort, not replace."""
    with patch('custom_components.cowboy._client.requests') as mock_requests:
        _configure_mock(mock_requests, bike_id=123, nickname="Bike A")

        existing = MockConfigEntry(
            version=2,
            minor_version=1,
            domain=DOMAIN,
            title="Bike A",
            data=MOCK_CONFIG,
            source="user",
            options={},
            unique_id="123",
        )
        existing.add_to_hass(hass)

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

        await hass.config_entries.async_remove(existing.entry_id)


async def test_config_flow_allows_second_bike(hass: HomeAssistant):
    """A second bike (different id) from the same account should be allowed."""
    with patch('custom_components.cowboy._client.requests') as mock_requests:
        _configure_mock(mock_requests, bike_id=123, nickname="Bike A")

        first = MockConfigEntry(
            version=2,
            minor_version=1,
            domain=DOMAIN,
            title="Bike A",
            data=MOCK_CONFIG,
            source="user",
            options={},
            unique_id="123",
        )
        first.add_to_hass(hass)

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
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state == config_entries.ConfigEntryState.LOADED:
                await hass.config_entries.async_unload(entry.entry_id)
                await hass.async_block_till_done()
        for entry in hass.config_entries.async_entries(DOMAIN):
            await hass.config_entries.async_remove(entry.entry_id)


async def test_migrate_v1_entry_captures_bike_id(hass: HomeAssistant):
    """v1 entries without bike_id should be migrated on setup."""
    with patch('custom_components.cowboy._client.requests') as mock_requests:
        _configure_mock(mock_requests, bike_id=789)

        v1_entry = MockConfigEntry(
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
        )
        v1_entry.add_to_hass(hass)

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

        await hass.config_entries.async_remove(v1_entry.entry_id)


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

        v1_entry = MockConfigEntry(
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
        )
        v1_entry.add_to_hass(hass)

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
        await hass.config_entries.async_remove(v1_entry.entry_id)
