"""Tests for the Cowboy firmware update entity."""
from unittest.mock import MagicMock

from custom_components.cowboy.update import (
    RELEASE_SUMMARY_MAX_LENGTH,
    CowboyFirmwareUpdate,
)


def _make_entity(bike_data, release_data):
    """Build a CowboyFirmwareUpdate with MagicMock coordinators."""
    bike_coordinator = MagicMock()
    bike_coordinator.data = bike_data

    release_coordinator = MagicMock()
    release_coordinator.data = release_data
    release_coordinator.config_entry.entry_id = "entry-1"
    release_coordinator.device_info = {}

    return CowboyFirmwareUpdate(release_coordinator, bike_coordinator)


def test_installed_version_reflects_bike_coordinator():
    """`installed_version` reads `firmware_version` from the bike coordinator."""
    entity = _make_entity(
        bike_data={"firmware_version": "v4.21.5"},
        release_data={"firmware": {"name": "v4.21.5", "status": "deployed"}},
    )
    assert entity.installed_version == "v4.21.5"


def test_installed_version_none_when_bike_data_missing():
    """`installed_version` is None when the bike coordinator has no data yet."""
    entity = _make_entity(
        bike_data=None,
        release_data={"firmware": {"name": "v4.21.5", "status": "deployed"}},
    )
    assert entity.installed_version is None


def test_latest_version_returns_deployed_release():
    """`latest_version` is the release name when status is 'deployed'."""
    entity = _make_entity(
        bike_data={"firmware_version": "v4.21.4"},
        release_data={"firmware": {"name": "v4.21.5", "status": "deployed"}},
    )
    assert entity.latest_version == "v4.21.5"


def test_latest_version_none_for_testing_release():
    """Test releases shouldn't be advertised — `latest_version` is None."""
    entity = _make_entity(
        bike_data={"firmware_version": "v4.21.4"},
        release_data={"firmware": {"name": "v4.21.6", "status": "testing"}},
    )
    assert entity.latest_version is None


def test_latest_version_none_when_release_data_missing():
    """`latest_version` is None when the release coordinator has no data yet."""
    entity = _make_entity(
        bike_data={"firmware_version": "v4.21.5"},
        release_data=None,
    )
    assert entity.latest_version is None


def test_latest_version_handles_null_firmware_block():
    """A `null` firmware block (the API does this for some keys) is handled."""
    entity = _make_entity(
        bike_data={"firmware_version": "v4.21.5"},
        release_data={"firmware": None},
    )
    assert entity.latest_version is None


def test_release_summary_returns_comment():
    """`release_summary` exposes the firmware comment unchanged when short."""
    entity = _make_entity(
        bike_data={"firmware_version": "v4.21.4"},
        release_data={
            "firmware": {
                "name": "v4.21.5",
                "status": "deployed",
                "comment": "Fixes a battery reporting bug.",
            }
        },
    )
    assert entity.release_summary == "Fixes a battery reporting bug."


def test_release_summary_truncated_to_255_chars():
    """Long release notes are truncated to HA's 255-character limit."""
    long_comment = "x" * 1000
    entity = _make_entity(
        bike_data={"firmware_version": "v4.21.4"},
        release_data={
            "firmware": {
                "name": "v4.21.5",
                "status": "deployed",
                "comment": long_comment,
            }
        },
    )
    summary = entity.release_summary
    assert summary is not None
    assert len(summary) == RELEASE_SUMMARY_MAX_LENGTH
    assert summary == "x" * RELEASE_SUMMARY_MAX_LENGTH


def test_release_summary_none_when_comment_missing():
    """`release_summary` is None when the comment field is absent."""
    entity = _make_entity(
        bike_data={"firmware_version": "v4.21.4"},
        release_data={"firmware": {"name": "v4.21.5", "status": "deployed"}},
    )
    assert entity.release_summary is None
