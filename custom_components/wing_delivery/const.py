"""Constants for the Wing Delivery integration."""
from homeassistant.const import Platform

DOMAIN = "wing_delivery"

# Config keys (host/port/username/password reuse homeassistant.const in config_flow)
CONF_FOLDER = "folder"
CONF_SENDER = "sender"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_PORT = 993
DEFAULT_FOLDER = "INBOX"
# Substring matched against the From header. Editable in the UI; refine once a
# real Wing order email is available.
DEFAULT_SENDER = "wing.com"
DEFAULT_SCAN_INTERVAL = 120  # seconds

STATUS_NONE = "none"
STATUS_ORDERED = "ordered"
STATUS_PREPARING = "preparing"
STATUS_EN_ROUTE = "en_route"
STATUS_ARRIVING = "arriving"
STATUS_DELIVERED = "delivered"

ACTIVE_STATUSES = frozenset(
    {STATUS_ORDERED, STATUS_PREPARING, STATUS_EN_ROUTE, STATUS_ARRIVING}
)

EVENT_STATUS_CHANGED = "wing_delivery_status_changed"

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER]
