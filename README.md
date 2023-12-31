# Cowboy Home Assistant Integration

This custom Home Assistant integration connects Home Assistant with your [Cowboy](https://cowboy.com/) electric bike, providing insights and monitoring capabilities directly within your Home Automation setup.

Feedback and contributions welcome.

> [!WARNING]
> The integration is working but considered unstable until a release has been made. It might have bugs or unexpected behaviors, or incompatible changes may require you to reinstall.

## Features

Among others, the following sensors are available:

- **Mileage Sensor**: Keeps track of your bike's total mileage.
- **Remaining Range**: Indicates the estimated remaining range.
- **Battery Level Sensor**: Gives an indication of the battery's health.
- **Battery Health**: Monitors the current battery status.
- **Usage Duration**: Tracks the total usage duration of the bike.
- **Software Update Alerts**: Notifies you of available software updates for your bike.
- **Location Tracking**: Tracks the current position of your Cowboy bike.

## Installation via HACS

1. Open Home Assistant Community Store (HACS) in your Home Assistant.
2. Go to "Integrations" and select "+ Explore & Download Repositories."
3. Find and select "Cowboy".
4. Click "Download this Repository with HACS".
5. Restart Home Assistant.
6. Navigate to the Integrations page, add the Cowboy integration, and provide your Cowboy account credentials.

## Configuration

Enter your Cowboy account credentials in the integration setup:

- **Username**: The email address associated with your Cowboy account.
- **Password**: Your Cowboy account password.

The account password is stored by the integration in order to be able to renew the session. It is not used for other purposes. Uninstalling the integration will logout the session.

> [!NOTE]
> The integration polls the Cowboy bike for data updates every minute and checks for software release availability every hour.

## Disclaimer

This integration is an independent project and not officially affiliated with Cowboy. "Cowboy" is a trademark and belongs to its respective owners. This project does not claim any official endorsement by Cowboy. Use at your own risk.

## License

MIT. See the [LICENSE](LICENSE) file for more details.

## Credits

Parts of the repository were copied over from [ludeeus/integration_blueprint](https://github.com/ludeeus/integration_blueprint/) (MIT).

---

*This integration is created and maintained by enthusiasts and is not a Cowboy official product.*
