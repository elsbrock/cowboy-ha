# Multi-bike support

Tracks the work to let one Home Assistant installation track multiple Cowboy
bikes owned by the same household.

Related: [#120](https://github.com/elsbrock/cowboy-ha/issues/120)

## Intent

Today the integration assumes one entry per installation. Adding a second
entry sets `unique_id` to the bike's nickname with no collision guard, so the
setup either silently replaces the first entry or produces duplicate entities
that all point at whichever bike was last authenticated against.

Cowboy explicitly requires [one account per bike][cowboy-faq]: households with
multiple bikes use separate email addresses. So the fix is not "make one API
client juggle multiple bikes" — it's "let the user register N config entries,
one per account, each pinned to its own bike".

[cowboy-faq]: https://help.cowboy.com/en/articles/7967265-my-account

## API shape (observed)

Captured with `scripts/probe_api.py`:

- `POST /auth/sign_in` returns `data.bike` — a full object with numeric `id`,
  `model`, `serial_number`, `nickname`, etc. for the single bike on the
  account.
- `GET /users/me` mirrors the sign-in payload.
- `GET /bikes/{numeric_id}` returns the full per-bike document. This is the
  endpoint the coordinator polls.
- `data.available_bikes[]` lists bikes the account has access to, including
  those shared by other users; each entry has a `type` ("owner" / etc.).
  Not relevant here — we only track the account's own bike.

## Approach

Each Cowboy account becomes its own HA config entry with its own
`CowboyAPIClient`, coordinator, and device. The entry stores the numeric
`bike_id` captured from the login response so the client can address that
bike explicitly rather than relying on whatever happens to be active at
login.

### Key changes

1. **`CowboyAPIClient`** takes an optional `bike_id` at construction. When
   set, it's used for all per-bike endpoints. When unset (initial config
   flow) login backfills it from `data.bike.id`. The client no longer caches
   `model` / `serial_number` — those are bike facts, not client facts, and
   are derived at setup time via `get_bike()`.

2. **Config flow** uses `str(bike_id)` as the entry `unique_id` and calls
   `_abort_if_unique_id_configured` to block the same bike being added
   twice (e.g. logging in with the same credentials again). `VERSION` bumps
   to `2`.

3. **Migration** (`async_migrate_entry`): v1 entries don't have `bike_id`
   in their data. On first load after upgrade, re-authenticate with the
   stored credentials, read `data.bike.id`, write it back to entry data
   and set `unique_id` accordingly.

4. **Device identifier** moves from `(DOMAIN, entry.entry_id)` to
   `(DOMAIN, str(bike_id))` so the device registry entry matches the
   bike's identity and survives config-entry recreation.

5. **Device tracker unique_id** collision fix: it previously derived from
   `config_entry.title`, which could collide across entries. Switched to
   the same entry-id-suffix pattern as sensor/binary_sensor. Pre-existing
   bug, surfaced once multiple entries are possible.

### What this intentionally does not do

- No UI for picking among multiple bikes. Each account only has one.
- No attempt to juggle multiple bikes from a single login. Cowboy's model
  doesn't support it and neither did our probe of the API.
- Sensor/binary_sensor entity unique IDs stay entry-scoped
  (`{entry_id}_{key}`); they're already unique per entry.

## Implementation checklist

- [x] Write spec
- [x] Add `bike_id` parameter to `CowboyAPIClient`; stop caching bike
      metadata on the client.
- [x] Update `config_flow.py` to use `bike_id` as `unique_id` and abort on
      duplicates; bump `VERSION = 2`.
- [x] Update `__init__.py` to pass `bike_id` into the client, derive device
      info from `get_bike()`, key the device identifier on `bike_id`.
- [x] Add `async_migrate_entry` for v1 → v2.
- [x] Fix device tracker unique_id collision.
- [x] Update tests: migration path, duplicate-abort, and a second entry
      from a distinct account/bike.

## What happens on upgrade

Existing v1 entries auto-migrate on first load. No user action required.
To add a second bike afterwards, the user goes to Settings → Devices &
Services → Add Integration → Cowboy and enters the credentials for the
second account.
