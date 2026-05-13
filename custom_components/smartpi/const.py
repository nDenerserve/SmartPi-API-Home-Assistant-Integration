DOMAIN = "smartpi"
DEFAULT_PORT = 80
DEFAULT_SCAN_INTERVAL = 30

API_LOGIN = "/api/v1/login"
API_LIVEDATA = "/api/v1/smartpiac/livedata"
API_LIVEPOWER = "/api/v1/smartpiac/livepower"
API_MAIN_CONFIG_READ = "/api/v1/config/readsmartpiconfiguration"
API_MAIN_CONFIG_WRITE = "/api/v1/config/writesmartpiconfiguration"
API_AC_CONFIG_READ = "/api/v1/config/readsmartpiacconfiguration"
API_AC_CONFIG_WRITE = "/api/v1/config/writesmartpiacconfiguration"

CONF_ENABLED_MEASUREMENTS = "enabled_measurements"

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
TOTAL_POWER_KEY = "totalpower"
ALL_MEASUREMENT_KEYS = MEASUREMENT_TYPES + [TOTAL_POWER_KEY]

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
