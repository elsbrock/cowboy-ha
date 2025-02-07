# Cowboy Home Assistant Integration

Welcome to the documentation for the Cowboy Home Assistant Integration. This integration allows you to connect your [Cowboy](https://cowboy.com/) electric bike with Home Assistant, enabling smart home automation and monitoring capabilities.

<p align="center">
  <img width="640" alt="image" src="https://github.com/user-attachments/assets/0d2358c7-2448-48e1-bf67-4cd07ec34474">
</p>

## Features

The integration provides several sensors and capabilities:

- **Mileage Sensor**: Keeps track of your bike's total mileage
- **Remaining Range**: Indicates the estimated remaining range
- **Battery Level Sensor**: Monitors the current battery status
- **Battery Health**: Gives an indication of the battery's health
- **Battery Docked**: Whether or not the battery is inside the bike
- **Usage Duration**: Tracks the total usage duration of the bike
- **Software Update Alerts**: Notifies you of available software updates
- **Location Tracking**: Tracks the current position of your bike

## Installation

### Via HACS (Recommended)

1. Ensure you have [HACS](https://hacs.xyz/) installed
2. Go to HACS > Integrations
3. Click the "+" button and search for "Cowboy"
4. Click Install
5. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/cowboy` directory to your Home Assistant's `custom_components` folder:

```bash
cd ~/.homeassistant
git clone https://github.com/elsbrock/cowboy-ha.git
cp -r cowboy-ha/custom_components/cowboy custom_components/
```

2. Restart Home Assistant

## Configuration

1. Go to Settings > Devices & Services
2. Click "Add Integration"
3. Search for "Cowboy"
4. Enter your credentials:
   - **Username**: Your Cowboy account email
   - **Password**: Your Cowboy account password

**Note:** The account password is stored securely to renew the session. It is not used for other purposes.

## Available Entities

### Sensors

| Entity | Description | Unit |
|--------|-------------|------|
| `sensor.cowboy_total_distance` | Total distance traveled | km |
| `sensor.cowboy_remaining_range` | Estimated remaining range | km |
| `sensor.cowboy_battery_level` | Current battery level | % |
| `sensor.cowboy_battery_health` | Battery health status | % |
| `binary_sensor.cowboy_battery_docked` | Battery docking status | - |
| `sensor.cowboy_total_duration` | Total usage time | seconds |
| `sensor.cowboy_total_co2_saved` | Total CO2 saved | grams |
| `sensor.cowboy_pcb_battery_state_of_charge` | PCB battery state of charge | % |
| `binary_sensor.cowboy_stolen` | Stolen status | - |
| `binary_sensor.cowboy_crashed` | Crashed status | - |
| `binary_sensor.cowboy_battery_inserted` | Battery inserted status | - |
| `binary_sensor.cowboy_update_available` | Update available status | - |

### Device Tracker

The integration creates a device tracker entity that shows your bike's last known location:

- `device_tracker.cowboy_bike`

## Automations

Here are some example automations you can create:

```yaml
# Get notified when battery is low
automation:
  - alias: "Notify on Low Battery"
    trigger:
      platform: numeric_state
      entity_id: sensor.cowboy_battery_level
      below: 20
    action:
      service: notify.mobile_app
      data:
        message: "Cowboy bike battery is low ({{ states('sensor.cowboy_battery_level') }}%)"

# Log when bike leaves home
  - alias: "Bike Left Home"
    trigger:
      platform: state
      entity_id: device_tracker.cowboy_bike
      from: "home"
    action:
      service: notify.mobile_app
      data:
        message: "Bike has left home"

# Notify when an update is available
  - alias: "Notify on Update Available"
    trigger:
      platform: state
      entity_id: binary_sensor.cowboy_update_available
      to: "on"
    action:
      service: notify.mobile_app
      data:
        message: "A software update is available for your Cowboy bike."
```

## Development

### Prerequisites

1. Install [Nix](https://nixos.org/download.html)
2. Enable [Flakes](https://nixos.wiki/wiki/Flakes#Enable_flakes)

### Setting Up Development Environment

1. Clone the repository:

```bash
git clone https://github.com/elsbrock/cowboy-ha.git
cd cowboy-ha
```

2. Enter the development environment:

```bash
nix develop
```

3. Start Home Assistant:

```bash
hass -c config
```

### Running Tests

Run the test suite using pytest:

```bash
pytest tests/ -v
```

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Verify your Cowboy account credentials
   - Ensure your account is active
   - Check internet connectivity

2. **No Data Updates**
   - The integration polls every minute
   - Check if your bike is powered on
   - Verify internet connectivity

### Debug Logging

To enable debug logs, go to Settings > Integrations > Cowboy > Options > Debug Logging.

You can alternatively add this to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.cowboy: debug
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/elsbrock/cowboy-ha/blob/main/LICENSE) file for details.

## Disclaimer

This integration is not officially affiliated with Cowboy. Use at your own risk.
