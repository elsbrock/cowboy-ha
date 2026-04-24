# Firmware update entity

Replace the existing `binary_sensor.update_available` with a proper Home
Assistant `update` entity that surfaces installed and latest firmware
versions side by side.

## Intent

The integration currently signals firmware updates via
`binary_sensor.update_available`. In practice users report it shows
`unknown` in the UI: it compares `firmware.name` from the release
coordinator with `device_info.sw_version` populated as a side-effect of
the bike coordinator's refresh, and that coupling between two
coordinators sharing one `DeviceInfo` dict is fragile (timing, `None`
vs missing keys, `device_info` not re-evaluated on release-coordinator
ticks).

Home Assistant has a first-class `UpdateEntity` for exactly this case.
It shows installed and latest versions, release notes, and integrates
with the device card and the dashboard "updates" affordance. Switching
to it gets us the right UX and lets us drop the brittle
cross-coordinator state passing.

## API shape (observed)

`GET /bikes/{id}` (bike coordinator's data):

```json
{"firmware_version": "v4.21.5", "nickname": "...", "model": {...}, ...}
```

`GET /releases` (release coordinator's data):

```json
{
  "firmware": {"name": "v4.21.5", "status": "deployed", "comment": "...", "url": "..."},
  "battery": {...},
  "controller": {...}
}
```

`firmware.status` is observed as `"deployed"` or `"testing"`. Test
builds should not be advertised to end users — only `"deployed"`
releases.

## Approach

Add a new `update` platform with one entity per config entry.

### Coordinator wiring

The entity needs data from both coordinators:

- `installed_version` from the **bike** coordinator (`bike.firmware_version`).
- `latest_version`, `release_summary` from the **release** coordinator.

Subclass `CoordinatorEntity` against the **release coordinator** (it's
the "what's available" source) and read the bike coordinator directly
out of `hass.data[DOMAIN][entry_id][CONF_BIKE_COORDINATOR]`. To make
sure HA re-renders when either coordinator ticks, also listen to the
bike coordinator via `self.async_on_remove(bike_coordinator.async_add_listener(...))`
in `async_added_to_hass`.

This is option A from the planning notes: cleaner than juggling two
parents and avoids needing a new shared base class. The entity reads
both `coordinator.data`s lazily on every property access, so there's
no internal state to drift.

### Properties

| Property | Source | Notes |
|----------|--------|-------|
| `installed_version` | `bike.firmware_version` | `None` if bike coordinator has no data yet. |
| `latest_version` | `releases.firmware.name` | Only when `releases.firmware.status == "deployed"`. `None` otherwise (HA renders this as "no update info" rather than wrongly announcing a test build). |
| `release_summary` | `releases.firmware.comment` | Truncated to 255 chars (HA's documented limit). |
| `release_url` | — | Skipped: the API's `url` is a raw firmware zip, not user-friendly. |
| `title` | `"Firmware"` (via translation key) | Differentiates from the device name. |

`supported_features` stays at the default `0` — we cannot trigger
firmware installs via the API, so no `INSTALL` flag.

### Existing binary sensor

Don't delete `binary_sensor.update_available` — that would silently
break user automations referencing the entity ID. Mark it with
`entity_registry_enabled_default=False` so new installs get the
`update` entity as the recommended path while existing users keep
their entity until they choose to remove it.

### Bug fix in the existing binary sensor

Investigation: the most likely cause of the `unknown` state is that
`get("firmware", {})` returns `None` when the response actually has
`"firmware": null` (the `cockpit` and `wireless_charger` keys in the
sample payload are `null`, so this is a real shape the API returns).
A `None.get(...)` then raises `AttributeError` and HA leaves the
state as `unknown`.

Apply a small defensive fix: `firmware = data.get("firmware") or {}`
and the same for `device_info`. The new `update` entity does the same
thing structurally, so this keeps the legacy entity functional for
users who haven't migrated.

## Translations

Add a `firmware` translation key under `entity.update.firmware` in
`strings.json` and `translations/en.json`. The existing
`binary_sensor.update_available` translation stays — that entity still
exists.

## Tests

Unit-style tests in `tests/test_update.py` using `MagicMock`
coordinators (no full HA bootstrap, mirroring the diagnostics-test
pattern). Cover:

- `installed_version` reflects the bike coordinator's
  `firmware_version`.
- `latest_version` is the release `firmware.name` when status is
  `"deployed"`.
- `latest_version` is `None` when status is `"testing"`.
- `latest_version` is `None` when the release coordinator has no data
  yet.
- `release_summary` is `firmware.comment`, truncated to 255
  characters.

## Non-goals

- No install support — the Cowboy app handles firmware updates
  over BLE.
- No skip/release-notes UX beyond the short `release_summary`.
- No removal of the existing binary sensor.

## Implementation checklist

- [x] Write spec
- [ ] Add `update.py` with `CowboyFirmwareUpdate`
- [ ] Register `Platform.UPDATE` in `__init__.py`
- [ ] Add translation keys
- [ ] Disable `binary_sensor.update_available` by default
- [ ] Defensive fix for the legacy binary sensor's `None` handling
- [ ] `pytest` and `ruff check` pass
