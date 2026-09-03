# battery_emulator_rest

A Home Assistant custom integration for controlling a Battery Emulator device via its REST API.

## Features

- **Max Charge Speed** — view and set the maximum charge speed (amps)
- **Max Discharge Speed** — view and set the maximum discharge speed (amps)
- **Calibrate SOC** — trigger a state-of-charge calibration
- Configurable polling interval via integration options

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS
2. Search for "Battery Emulator REST" and install
3. Restart Home Assistant
4. Add the integration via **Settings → Devices & Services → Add Integration**

### Manual

1. Copy the `custom_components/battery_emulator_rest` folder into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Add the integration via **Settings → Devices & Services → Add Integration**

## Configuration

During setup, provide the HTTP(S) DNS hostname, IPv4 address, or IPv6 address of your Battery Emulator device (e.g. `battery-emulator.home`, `http://192.168.1.2`, or `http://[2001:db8::2]`).

When configured with a DNS hostname, the integration stores the last successfully resolved IP address. It refreshes that address while DNS is available and uses the cached address during a DNS outage. A literal IP address bypasses DNS entirely.

An existing hostname-based entry must resolve successfully once after upgrading to seed its fallback address. Initial configuration also requires working DNS because no address has been cached yet.

The polling interval can be adjusted after setup via the integration's **Configure** button (default: 30 seconds).

To change the device address later, open **Settings → Devices & Services**, select the Battery Emulator integration, and choose **Reconfigure** from its menu. The new connection is validated before the existing entry is updated and reloaded.

## Connection reliability

The integration retries incomplete, disconnected, or timed-out reads up to three times. After data has been received successfully, the previous values remain available through two consecutive failed polling cycles. A third failed cycle marks the entities unavailable so a sustained outage is still visible.

The **Last Successful Update** diagnostic sensor is not advanced while cached values are retained and can be used to determine their freshness. State-changing commands are not retried automatically, which avoids applying a command twice when the device drops its response.
