# Cowboy Home Assistant Integration

This custom Home Assistant integration connects Home Assistant with your [Cowboy](https://cowboy.com/) electric bike, providing insights and monitoring capabilities directly within your Home Automation setup.

<p align="center">
  <img width="640" alt="image" src="https://github.com/user-attachments/assets/0d2358c7-2448-48e1-bf67-4cd07ec34474">
</p>

Feedback and contributions welcome.

## Features

Among others, the following sensors are available:

- **Mileage Sensor**: Keeps track of your bike's total mileage.
- **Remaining Range**: Indicates the estimated remaining range.
- **Battery Level Sensor**: Monitors the current battery status.
- **Battery Health**: Gives an indication of the battery's health.
- **Battery Docked**: Weither or not the battery is inside the bike
- **Usage Duration**: Tracks the total usage duration of the bike.
- **Software Update Alerts**: Notifies you of available software updates for your bike.
- **Location Tracking**: Tracks the current position of your Cowboy bike.

## Installation via HACS

This integration is available in the default HACS catalog and can be installed directly.

## Configuration

Enter your Cowboy account credentials in the integration setup:

- **Username**: The email address associated with your Cowboy account.
- **Password**: Your Cowboy account password.

The account password is stored by the integration in order to be able to renew the session. It is not used for other purposes. Uninstalling the integration will logout the session.

> [!NOTE]
> The integration polls the Cowboy bike for data updates every minute and checks for software release availability every hour.

## Development

This project uses [Nix](https://nixos.org/) to manage development environments. This ensures consistent development environments across different machines.

### Prerequisites

1. Install Nix following the [official instructions](https://nixos.org/download.html)
2. Enable [Flakes](https://nixos.wiki/wiki/Flakes#Enable_flakes) if you haven't already

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

   This will:
   - Create a Python virtual environment
   - Install all development dependencies
   - Set up a basic Home Assistant configuration

3. Start a development instance of Home Assistant:
   ```bash
   hass -c config
   ```
   Then visit http://localhost:8123 in your browser.

### Running Tests

The test suite can be run using pytest: `pytest tests/ -v`

## Disclaimer

This integration is an independent project and not officially affiliated with Cowboy. "Cowboy" is a trademark and belongs to its respective owners. This project does not claim any official endorsement by Cowboy. Use at your own risk.

## License

MIT. See the [LICENSE](LICENSE) file for more details.

## Credits

Parts of the repository were copied over from [ludeeus/integration_blueprint](https://github.com/ludeeus/integration_blueprint/) (MIT).

## Documentation

For more information, please visit [our GitHub Pages site](https://elsbrock.github.io/cowboy-ha/).

---

*This integration is created and maintained by enthusiasts and is not a Cowboy official product.*
