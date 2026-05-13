# Changelog

All notable changes to the SmartPi Home Assistant Integration are documented here.

---

## [1.0.0] — 2026-05-13

### Added

**Core integration**
- Initial release of the SmartPi custom integration for Home Assistant.
- Config flow for easy setup via the HA UI (Settings → Devices & Services).
- Support for optional username/password credentials (required for config write access).
- Duplicate device prevention using the SmartPi serial number as the unique ID.
- Re-authentication flow that allows credentials to be updated without removing the integration.

**Sensor platform**
- Per-phase sensor entities for: current, voltage, active power, power factor, frequency, energy consumed, energy produced, energy balance.
- Total active power sensor aggregated across all phases (from the `/livepower` endpoint).
- Configurable sensor selection — users can enable or disable individual measurement types.
- Sensors update every 30 seconds via the `DataUpdateCoordinator`.

**Configuration entities (requires credentials)**
- Number entities for per-phase calibration: current calibration factor, CT primary current, GUI maximum current, reference voltage, voltage calibration factor.
- Switch entities for per-phase measurement control: enable/disable current measurement, invert current direction, enable/disable voltage measurement.
- Select entity for per-phase current transformer type (supports YHDC_SCT013, YHDC_SCT006, YHDC_SCT023R, YHDC_SCT0400, YHDC_SCT800, Rogowski; unknown values from the device are added dynamically).
- All configuration entities are disabled by default to keep the default device view clean.

**Options flow**
- Sensor selection menu to choose which measurement types are exposed.
- Device settings menu to edit the SmartPi device name, GPS coordinates, and log level (written directly to the device).
- AC measurement settings menu to configure power frequency (50/60 Hz), sample rate (1–10), and integrator mode.

**Authentication**
- JWT-based authentication with automatic token refresh on 401 responses.
- Authentication is skipped gracefully when no credentials are provided (read-only mode).

**Integration icon**
- Brand images added to `brand/` directory using the HA 2026.3+ brands proxy API.
- `icon.png` and `logo.png` are served locally by Home Assistant without requiring a submission to the central brands repository.

**Documentation**
- English docstrings added to all source files.
- `README.md` with installation instructions, entity overview, and architecture description.
- This `CHANGELOG.md`.

### Technical details

- Platforms: `sensor`, `number`, `switch`, `select`
- Minimum Home Assistant version: 2024.1
- No external Python dependencies
- `iot_class`: `local_polling`
- Poll interval: 30 seconds
- HTTP timeout: 10 seconds per request
