# Diagnostics with redaction

Related: [#99](https://github.com/elsbrock/cowboy-ha/issues/99)

## Intent

Home Assistant's built-in diagnostics feature lets users download a JSON dump
of a config entry's state, which is how we ask them to attach data to bug
reports. The Cowboy API responses contain plenty that users shouldn't be
pasting into public issues: credentials, MAC addresses, serial numbers,
GPS coordinates, phone numbers, home addresses, etc.

The integration currently has no `diagnostics.py`, so issue authors have no
easy way to share structured data — and when we add diagnostics, it has to
redact by default or we'll make the problem the issue describes worse.

## Approach

Ship `custom_components/cowboy/diagnostics.py` with
`async_get_config_entry_diagnostics` that returns a redacted dump of:

1. The config entry itself (data + options). HA will already strip
   `CONF_PASSWORD` in some scopes but we redact explicitly for belt-and-braces.
2. The latest bike coordinator payload (i.e. `GET /bikes/{id}` response).
3. The latest release coordinator payload.

Use `homeassistant.components.diagnostics.async_redact_data` for the actual
masking — it recursively replaces matching keys with the literal string
`**REDACTED**`.

## Redaction list

Anything that identifies a person, a specific physical device, current
location, or grants API access:

**Credentials / session**
- `username`, `password`, `email`, `uid`, `client`, `access_token`,
  `push_token`, `passkey`

**Personally identifying info**
- `first_name`, `last_name`, `nickname`, `phone_number`, `emergency_phone_number`,
  `avatar_url`, `avatars`, `cover_url`,
  `instagram_profile_url`, `facebook_username`, `intercom_token`

**Device identifiers**
- `id` (bike id), `bike_id`, `mac_address`, `serial_number`, `sku_code`, `uuid`

**Location**
- `latitude`, `longitude`, `address`, `country_code`

Notes:
- We redact `nickname` because users tend to name bikes after themselves or
  partners.
- `id`, `bike_id`, and `uuid` are flagged even though on their own they're
  not terribly sensitive — Cowboy support could use them to look up an
  account, which is the specific risk called out in the issue.
- Top-level keys like the config entry's own `entry_id` are HA-internal and
  don't need redaction.

## Non-goals

- No custom "raw mode" toggle. If a debugger needs unredacted data they can
  grab it from the Cowboy app, mitmproxy, or the integration's debug logs.
- No entity-level diagnostics (`async_get_device_diagnostics`) for now — the
  config-entry dump already covers the interesting data.

## Implementation checklist

- [x] Write spec
- [ ] Add `diagnostics.py`
- [ ] Add test with a realistic fixture, asserting each sensitive key is
      redacted and a representative non-sensitive key (e.g. `battery_state_of_charge`)
      survives.
