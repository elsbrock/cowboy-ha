# Extra sensors from existing bike payload

Expose more of what `GET /bikes/{id}` already returns as first-class HA
sensors. No new API calls, no new polling.

## New sensors

| Key | API path | Device class | Unit | Notes |
|-----|----------|--------------|------|-------|
| `seen_at` | `bike.seen_at` | timestamp | — | Last time the bike phoned home. Useful for "is the bike online" automations. |
| `last_ride_mode` | `bike.last_ride_mode` | enum | — | Options list from observed `bike.autonomies[].ride_mode`. |
| `last_crash_started_at` | `bike.last_crash_started_at` | timestamp | — | Nullable — returns `None` if no crash on record. Diagnostic category. |
| `warranty_ends_at` | `bike.warranty_ends_at` | timestamp | — | Nullable. Diagnostic category. |
| `auto_lock` | `bike.pending_settings.auto_lock` | duration | min | The auto-lock interval configured in the Cowboy app. |
| `displayed_speed` | `bike.sku.features.displayed_speeds.default` | speed | km/h | The speed cap displayed to the rider (25 km/h in the EU). Diagnostic category. |

## Implementation notes

- Timestamps arrive as ISO 8601 strings (`"2026-04-24T09:25:32.491+02:00"`).
  `datetime.fromisoformat` handles the offset correctly on Python 3.11+.
- Where the underlying field may be missing or null, the value function
  returns `None` so the sensor reports `unknown` rather than raising.
- `last_crash_started_at`, `warranty_ends_at`, and `displayed_speed` are
  tagged `EntityCategory.DIAGNOSTIC` because they're reference data rather
  than routinely changing telemetry.

## Implementation checklist

- [x] Write spec
- [ ] Add sensor descriptions to `sensor.py`
- [ ] Add translation keys to `strings.json`
- [ ] Test nested-dict and nullable timestamp value functions
