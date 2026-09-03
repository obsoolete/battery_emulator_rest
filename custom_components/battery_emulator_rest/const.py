"""Constants for the Battery Emulator REST integration."""

DOMAIN = "battery_emulator_rest"

CONF_HOST = "host"
CONF_RESOLVED_IP = "resolved_ip"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 30
DNS_TIMEOUT = 5
REQUEST_TIMEOUT = 10
READ_RETRY_DELAYS = (0.5, 1.5)
STALE_FAILURE_LIMIT = 3

MAX_CHARGE_SPEED = "max_charge_speed"
MAX_DISCHARGE_SPEED = "max_discharge_speed"
LAST_SUCCESSFUL_UPDATE = "last_successful_update"
