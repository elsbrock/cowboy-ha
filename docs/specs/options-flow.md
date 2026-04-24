# Options flow: polling interval

Let users change how often the bike coordinator polls the Cowboy API.

## Intent

The bike coordinator polls `GET /bikes/{id}` every minute, hard-coded in
`async_setup_entry` via the `CowboyBikeUpdateCoordinator` default. One minute
is aggressive for an unofficial API that's really only shared with the app,
and users have no knob to back it off. Anyone worried about rate-limiting,
account flagging, or just power use on a phone acting as the API's "device"
has to patch the code.

The release coordinator already runs at a gentler hourly interval and isn't
interesting to tune — leave it alone.

## Approach

Add an options flow with a single field, `scan_interval` (minutes, 1–60), and
plumb it into `CowboyBikeUpdateCoordinator.update_interval` at setup time.
Re-read on options change via an update listener that reloads the entry.

### Key changes

1. **`const.py`** — add `CONF_SCAN_INTERVAL = "scan_interval"`. Use the
   constant everywhere rather than string-literalling the key.

2. **`config_flow.py`**
   - `ConfigFlow.async_get_options_flow` returns an `OptionsFlow` subclass.
   - The options flow has a single `init` step: integer `scan_interval`
     clamped to `vol.Range(min=1, max=60)`, pre-filled from
     `entry.options.get(CONF_SCAN_INTERVAL, 1)`.
   - On submit, `async_create_entry(title="", data={CONF_SCAN_INTERVAL: ...})`
     so the value lands in `entry.options`.

3. **`__init__.py`**
   - Read `entry.options.get(CONF_SCAN_INTERVAL, 1)` and pass
     `update_interval=timedelta(minutes=...)` to the bike coordinator.
   - Register an update listener that reloads the entry on options change:
     `entry.async_on_unload(entry.add_update_listener(_async_update_listener))`.

4. **Strings** — add translation keys for the options step in both
   `strings.json` and `translations/en.json`.

### Defaults & bounds

- Default stays **1 minute** so existing installs are byte-for-byte
  identical until the user opens the options dialog.
- Upper bound **60 minutes** — anything longer and the device looks offline
  in the UI; users who truly want that can build an automation to disable
  the entry.
- Lower bound **1 minute** — faster than that would hammer the API with no
  practical benefit (the bike doesn't update its server-side state that
  often).

## Non-goals

- No option for the release coordinator's interval. It's already hourly and
  the firmware update cadence doesn't warrant it.
- No other options (credentials, bike selection, etc.). Those live in a
  re-auth flow if/when needed.
- No minor-version bump or migration — new installs get the default, old
  installs have empty `options` which also yields the default.

## Implementation checklist

- [x] Write spec
- [x] Add `CONF_SCAN_INTERVAL` to `const.py`
- [x] Add `OptionsFlow` subclass and `async_get_options_flow` wiring in
      `config_flow.py`
- [x] Read `scan_interval` from `entry.options` in `async_setup_entry` and
      pass to `CowboyBikeUpdateCoordinator`
- [x] Register update listener that reloads the entry on options change
- [x] Translation keys in `strings.json` and `translations/en.json`
- [x] Test asserting `update_interval` reflects `entry.options["scan_interval"]`
