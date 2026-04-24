# Trip sensors

Surface data from the Cowboy trip endpoints as first-class HA sensors: a
"last trip" snapshot plus a running "today" distance. The integration already
polls `/bikes/{id}` and `/releases`; trips get their own coordinator so the
cadence and failure mode stay independent.

## Intent

The bike coordinator only tracks lifetime totals and live telemetry. Riders
also want at-a-glance info about their most recent ride (distance, duration,
CO2, calories) and how far they've gone today — both come straight from the
Cowboy API with no extra modelling.

## API shape (observed)

- `GET /trips/recent` returns `{"trips": [...]}`, most-recent first. Each
  trip carries `distance` (km), `moving_time` / `duration` (seconds),
  `ended_at` (ISO 8601), `title`, `co2_saved` (g), `calories_burned` (kcal),
  and more. Only the head of the list is consumed.
- `GET /trips/highlights` returns a list of `{type, payload}` entries. The
  entry with `type == "today_highlight"` has `payload.distance` (km) for
  "today so far". May be absent on fresh days; value function tolerates
  that.
- `GET /trips/metrics/stats` is intentionally skipped — it only returns
  heart-rate data when the user has Apple Health sync enabled.

## Approach

A new `CowboyTripsUpdateCoordinator` fetches both endpoints in one pass and
normalises them into:

```python
{
    "last_trip": <first trips[] item or None>,
    "today_distance": <float or None>,
}
```

Default interval is 15 minutes — trips don't change between polls. Failure
is non-fatal: `async_setup_entry` wraps the first refresh in try/except so
a trips outage doesn't block the bike coordinator (the critical path).

Sensors live in `sensor.py` alongside the bike sensors but subclass
`CoordinatorEntity[CowboyTripsUpdateCoordinator]` directly. They share the
same device as the bike sensors via the bike coordinator's `device_info`.
Every value function tolerates `last_trip is None` by returning `None`, so
sensors show `unknown` on a fresh account rather than raising.

## Field mapping

| Key | API path | Device class | Unit | Notes |
|-----|----------|--------------|------|-------|
| `last_trip_distance` | `last_trip.distance` | distance | km | Precision 1. |
| `last_trip_ended_at` | `last_trip.ended_at` | timestamp | — | ISO 8601 → `datetime`. |
| `last_trip_duration` | `last_trip.moving_time` | duration | s | `SensorStateClass.MEASUREMENT`. |
| `last_trip_co2_saved` | `last_trip.co2_saved` | — | g | Icon `mdi:cloud-check`. |
| `last_trip_calories` | `last_trip.calories_burned` | energy | kcal | — |
| `last_trip_title` | `last_trip.title` | — | — | Text sensor, icon `mdi:bike`. |
| `today_distance` | `today_distance` | distance | km | `SensorStateClass.TOTAL_INCREASING` — resets daily in practice. |

## Implementation checklist

- [x] Write spec
- [ ] Add `CONF_TRIPS_COORDINATOR` to `const.py`
- [ ] Add `CowboyTripsUpdateCoordinator` to `coordinator.py`
- [ ] Wire it into `async_setup_entry` with non-fatal first refresh
- [ ] Add `TRIPS_SENSOR_TYPES` and `CowboyTripsSensor` in `sensor.py`
- [ ] Add translation keys to `strings.json` and `translations/en.json`
- [ ] Unit-test value functions against fixture dicts with and without data
