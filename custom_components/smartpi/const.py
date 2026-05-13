"""Constants for the SmartPi integration."""

DOMAIN = "smartpi"

# Default connection parameters
DEFAULT_PORT = 80
DEFAULT_SCAN_INTERVAL = 30  # seconds between live-data polls

# REST API endpoints exposed by the SmartPi device
API_LOGIN = "/api/v1/login"
API_LIVEDATA = "/api/v1/smartpiac/livedata"
API_LIVEPOWER = "/api/v1/smartpiac/livepower"
API_MAIN_CONFIG_READ = "/api/v1/config/readsmartpiconfiguration"
API_MAIN_CONFIG_WRITE = "/api/v1/config/writesmartpiconfiguration"
API_AC_CONFIG_READ = "/api/v1/config/readsmartpiacconfiguration"
API_AC_CONFIG_WRITE = "/api/v1/config/writesmartpiacconfiguration"

# Options-flow keys stored in HA (not written to the device)
CONF_ENABLED_MEASUREMENTS = "enabled_measurements"
CONF_SCAN_INTERVAL = "scan_interval"

# Per-phase measurement types returned by the livedata endpoint
MEASUREMENT_TYPES = [
    "current",
    "voltage",
    "power",
    "cosphi",
    "frequency",
    "energyconsumed",
    "energyproduced",
    "energybalanced",
]

# Total active power across all phases (from the separate livepower endpoint)
TOTAL_POWER_KEY = "totalpower"

# All measurement keys that can be enabled/disabled by the user
ALL_MEASUREMENT_KEYS = MEASUREMENT_TYPES + [TOTAL_POWER_KEY]

# Current transformer models supported by the SmartPi AC hardware
CT_TYPES = [
    "YHDC_SCT013",
    "YHDC_SCT006",
    "YHDC_SCT023R",
    "YHDC_SCT0400",
    "YHDC_SCT800",
    "Rogowski",
]

LOG_LEVELS = ["debug", "info", "warning", "error"]
POWER_FREQUENCIES = [50, 60]
