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

During setup, provide the host URL of your Battery Emulator device (e.g. `http://192.168.1.2`).

The polling interval can be adjusted after setup via the integration's **Configure** button (default: 30 seconds).
