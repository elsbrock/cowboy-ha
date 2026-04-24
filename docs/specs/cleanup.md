# Cleanup: dead code and broken logout

Three small, unrelated fixes to the Cowboy client and integration entry
module. No behavioural change for users beyond logout actually working.

## Intent

While reviewing the client and integration entry point, three issues surfaced:

1. **`CowboyAPIClient.get_bike_status()`** hits `/bikes/{id}/status`, which
   the Cowboy API returns `404` for. Nothing in the repo calls it, so it's
   simply dead code that would mislead future contributors.

2. **`async_unload_entry`** tries to call `.logout` on the bike coordinator
   object, which has no such method. The bare `except: pass` swallows the
   `AttributeError`, so logout is silently skipped on every unload. The
   coordinator was never the right receiver — the API client is.

3. **`_renew_token`** passes `self.uid` back into `login()` as the email.
   `self.uid` happens to equal the login email because the server echoes it
   in the `Uid` response header, but that's an implementation detail of the
   API we shouldn't rely on. Storing the email explicitly is a one-line fix
   that removes the coincidence.

## Changes

- `custom_components/cowboy/_client.py`
  - Delete `get_bike_status()`.
  - Initialize `self.email = None` in `__init__`.
  - Store `self.email = email` at the top of `login()`.
  - Change `_renew_token` to call `self.login(self.email, self.password)`.

- `custom_components/cowboy/__init__.py`
  - In `async_unload_entry`, log out the API client
    (`hass.data[DOMAIN][entry.entry_id][CONF_API].logout`) instead of the
    bike coordinator.
  - Update the stale "logging out any of them suffices" comment — with the
    fix there's only one thing to log out.
  - Keep the `try` / `except` (the logout call may legitimately fail if the
    token is already expired) and the existing `# noqa` markers.

## Non-goals

- No refactor of the client's auth state handling. `self.uid` stays as the
  response-header value used for authenticated requests.
- No change to how the coordinator is wired up or torn down.

## Implementation checklist

- [x] Write spec
- [x] Delete `get_bike_status`
- [x] Fix `async_unload_entry` to log out the API client
- [x] Track `email` on the client and use it in `_renew_token`
- [x] `pytest` and `ruff check` pass
