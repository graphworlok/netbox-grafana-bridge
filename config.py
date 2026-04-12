"""
netbox-grafana-bridge – Configuration
Copy this file to config_local.py and fill in your values, or set environment variables.
"""
import os

# --- NetBox ---
NETBOX_URL   = os.getenv("NETBOX_URL",   "https://netbox.example.com")
NETBOX_TOKEN = os.getenv("NETBOX_TOKEN", "YOUR_NETBOX_API_TOKEN")

# --- Grafana ---
# Base URL of your Grafana instance.  Used to generate deep-links from NetBox.
GRAFANA_URL  = os.getenv("GRAFANA_URL",  "https://grafana.example.com")

# Dashboard UIDs to link from NetBox objects.
# Keys are NetBox object types; values are Grafana dashboard UIDs.
# The bridge builds a URL like: <GRAFANA_URL>/d/<uid>?var-device=<name>
DASHBOARD_UIDS: dict[str, str] = {
    "device":    os.getenv("GRAFANA_DASHBOARD_DEVICE",    ""),
    "interface": os.getenv("GRAFANA_DASHBOARD_INTERFACE", ""),
    "site":      os.getenv("GRAFANA_DASHBOARD_SITE",      ""),
    "prefix":    os.getenv("GRAFANA_DASHBOARD_PREFIX",    ""),
    "circuit":   os.getenv("GRAFANA_DASHBOARD_CIRCUIT",   ""),
}

# Default Grafana variable names per object type.
# The bridge appends ?var-<param>=<value> to the dashboard URL.
DASHBOARD_VAR_PARAMS: dict[str, str] = {
    "device":    "device",
    "interface": "interface",
    "site":      "site",
    "prefix":    "prefix",
    "circuit":   "circuit",
}

# --- Bridge service ---
BRIDGE_HOST = os.getenv("BRIDGE_HOST", "0.0.0.0")
BRIDGE_PORT = int(os.getenv("BRIDGE_PORT", "8765"))

# NetBox request timeout (seconds)
NETBOX_TIMEOUT = int(os.getenv("NETBOX_TIMEOUT", "10"))

# How long (seconds) to cache NetBox responses for Grafana variable queries
CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))
