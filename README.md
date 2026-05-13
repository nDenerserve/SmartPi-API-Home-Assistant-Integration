# SmartPi — Home Assistant Integration

A custom Home Assistant integration for the **SmartPi AC** energy meter by [enerserve GmbH](https://www.enerserve.eu). It connects to the device's local REST API and exposes live electrical measurements as Home Assistant entities.

---

## Requirements

| Requirement | Version |
|---|---|
| Home Assistant | 2024.1 or newer |
| SmartPi AC firmware | any version with REST API v1 |
| Network access | HA must be able to reach the SmartPi by IP |

No additional Python packages are required — the integration uses the aiohttp client that ships with Home Assistant.

---

## Installation

### Option A — Manual

1. Copy the `custom_components/smartpi` directory into your Home Assistant configuration folder:
   ```
   <config>/custom_components/smartpi/
   ```
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and search for **SmartPi**.

### Option B — HACS (recommended for updates)

1. Add this repository as a custom repository in HACS (type: **Integration**).
2. Install the **SmartPi** integration from HACS.
3. Restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration** and search for **SmartPi**.

---

## Configuration

During the setup wizard you will be asked for:

| Field | Required | Description |
|---|---|---|
| Host | Yes | IP address or hostname of the SmartPi device |
| Port | No | HTTP port (default: `80`) |
| Username | No | SmartPi login username (needed for config write access) |
| Password | No | SmartPi login password |

Credentials are optional for read-only sensor data but are required to use the configuration entities (number, switch, select) and the options-flow device settings.

The device serial number is used as the unique ID, so the same physical device cannot be added twice.

---

## Entities

### Sensors (read-only, updated every 30 seconds)

One sensor entity is created per phase per enabled measurement type.

| Measurement | Unit | Device Class |
|---|---|---|
| Current | A | `current` |
| Voltage | V | `voltage` |
| Active Power | W | `power` |
| Power Factor | — | `power_factor` |
| Frequency | Hz | `frequency` |
| Energy Consumed | Wh | `energy` |
| Energy Produced | Wh | `energy` |
| Energy Balance | Wh | `energy` |
| Total Power (all phases) | W | `power` |

The set of exposed sensors can be changed at any time in **Settings → Devices & Services → SmartPi → Configure → Sensors**.

### Configuration entities (require credentials, disabled by default)

These entities write directly to the SmartPi device configuration. Enable them individually under the device's entity list.

**Number entities** (per phase 1–4):

| Entity | Description |
|---|---|
| Current Calibration Factor | Correction multiplier for current measurements (0.1–10.0) |
| CT Primary Current | Nominal primary current of the installed CT (A) |
| GUI Maximum Current | Upper bound for the web UI current display (A) |

**Number entities** (per phase 1–3, not neutral):

| Entity | Description |
|---|---|
| Reference Voltage | Expected phase-to-neutral voltage used for power calculations (V) |
| Voltage Calibration Factor | Correction multiplier for voltage measurements (0.1–10.0) |

**Switch entities** (per phase 1–4):

| Entity | Description |
|---|---|
| Measure Current | Enable / disable current measurement for this phase |
| Invert Current Direction | Flip the sign of the current reading |

**Switch entities** (per phase 1–3):

| Entity | Description |
|---|---|
| Measure Voltage | Enable / disable voltage measurement for this phase |

**Select entities** (per phase 1–4):

| Entity | Options |
|---|---|
| Current Transformer Type | YHDC_SCT013, YHDC_SCT006, YHDC_SCT023R, YHDC_SCT0400, YHDC_SCT800, Rogowski |

---

## Options Flow

After setup, open **Settings → Devices & Services → SmartPi → Configure** to access three configuration sections:

### Sensors
Choose which measurement types are exposed as HA sensor entities. Changes trigger an integration reload.

### Device Settings
Edit the SmartPi device name, GPS coordinates (latitude / longitude), and log level. These values are written directly to the device.

### AC Measurement Settings
Change global AC parameters:

| Setting | Description |
|---|---|
| Power Frequency | Grid frequency (50 Hz or 60 Hz) |
| Sample Rate | Number of samples averaged per reading (1–10) |
| Integrator | Enable the integrator mode for energy calculations |

---

## Integration Architecture

```
custom_components/smartpi/
├── __init__.py          Entry setup / teardown, platform forwarding
├── coordinator.py       DataUpdateCoordinator — HTTP polling & config r/w
├── config_flow.py       UI setup wizard and options flow
├── sensor.py            Read-only live measurement sensors
├── number.py            Editable per-phase calibration values
├── switch.py            Per-phase measurement enable/disable toggles
├── select.py            Per-phase current transformer type selector
├── const.py             Domain constants, API paths, measurement keys
├── manifest.json        Integration metadata
├── strings.json         UI strings (source, English)
├── icons.json           Service icon declarations
├── brand/               Integration branding (served via HA brands proxy)
│   ├── icon.png
│   └── logo.png
└── translations/
    └── de.yaml          German UI translations
```

The coordinator polls the `/api/v1/smartpiac/livedata` endpoint every 30 seconds and caches the result. All sensor entities read from this cache rather than making individual HTTP requests. The device configuration (AC config and main config) is loaded once at startup and written back on demand when a configuration entity value changes.

Authentication uses a JWT token obtained from `/api/v1/login`. The token is cached in memory and refreshed automatically on a 401 response.

---

## Troubleshooting

**"Cannot connect" during setup**
Verify that the SmartPi is reachable from the HA host:
```bash
curl http://<smartpi-ip>/api/v1/smartpiac/livedata
```

**Configuration entities are not visible**
Configuration entities (number, switch, select) are disabled by default. Go to the device page in HA, click the entity count under "Disabled", and enable the entities you need. Credentials must be configured for these entities to work.

**"Invalid auth" during setup**
Check your username and password in the SmartPi web interface. If you have forgotten the password, it can be reset via the SmartPi system settings page.

---

## License

This project is provided as-is without warranty. See the repository for license details.
