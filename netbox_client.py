"""
netbox-grafana-bridge – NetBox API client
Wraps pynetbox with caching and helper methods used by the Grafana bridge.
"""
from __future__ import annotations

import time
import logging
from typing import Any
from functools import lru_cache

import requests

log = logging.getLogger(__name__)


class NetBoxClient:
    """Thin wrapper around the NetBox REST API."""

    def __init__(self, url: str, token: str, timeout: int = 10) -> None:
        self.base = url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Token {token}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        })
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict | None = None) -> Any:
        url = f"{self.base}/api/{path.lstrip('/')}"
        resp = self.session.get(url, params=params or {}, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _list(self, path: str, params: dict | None = None) -> list:
        """Return all results, following NetBox pagination."""
        results: list = []
        p = dict(params or {})
        p.setdefault("limit", 200)
        p.setdefault("offset", 0)
        while True:
            data = self._get(path, p)
            results.extend(data.get("results", []))
            if not data.get("next"):
                break
            p["offset"] += p["limit"]
        return results

    # ------------------------------------------------------------------
    # Devices
    # ------------------------------------------------------------------

    def get_devices(self, site: str | None = None,
                    role: str | None = None,
                    tag: str | None = None) -> list[dict]:
        params: dict = {}
        if site:
            params["site"] = site
        if role:
            params["role"] = role
        if tag:
            params["tag"] = tag
        return self._list("dcim/devices/", params)

    def get_device(self, name: str) -> dict | None:
        results = self._list("dcim/devices/", {"name": name})
        return results[0] if results else None

    def get_device_by_id(self, device_id: int) -> dict | None:
        try:
            return self._get(f"dcim/devices/{device_id}/")
        except requests.HTTPError:
            return None

    # ------------------------------------------------------------------
    # Interfaces
    # ------------------------------------------------------------------

    def get_interfaces(self, device: str | None = None,
                       device_id: int | None = None) -> list[dict]:
        params: dict = {}
        if device:
            params["device"] = device
        if device_id:
            params["device_id"] = device_id
        return self._list("dcim/interfaces/", params)

    # ------------------------------------------------------------------
    # Sites
    # ------------------------------------------------------------------

    def get_sites(self) -> list[dict]:
        return self._list("dcim/sites/")

    def get_site(self, slug: str) -> dict | None:
        results = self._list("dcim/sites/", {"slug": slug})
        return results[0] if results else None

    # ------------------------------------------------------------------
    # Prefixes / IP addresses
    # ------------------------------------------------------------------

    def get_prefixes(self, site: str | None = None,
                     vrf: str | None = None) -> list[dict]:
        params: dict = {}
        if site:
            params["site"] = site
        if vrf:
            params["vrf"] = vrf
        return self._list("ipam/prefixes/", params)

    def get_ip_addresses(self, device: str | None = None,
                         interface_id: int | None = None) -> list[dict]:
        params: dict = {}
        if device:
            params["device"] = device
        if interface_id:
            params["interface_id"] = interface_id
        return self._list("ipam/ip-addresses/", params)

    # ------------------------------------------------------------------
    # Circuits / Providers / ASNs
    # ------------------------------------------------------------------

    def get_circuits(self, provider: str | None = None,
                     site: str | None = None) -> list[dict]:
        params: dict = {}
        if provider:
            params["provider"] = provider
        if site:
            params["site"] = site
        return self._list("circuits/circuits/", params)

    def get_providers(self) -> list[dict]:
        return self._list("circuits/providers/")

    def get_asns(self) -> list[dict]:
        return self._list("ipam/asns/")

    # ------------------------------------------------------------------
    # Device-type / roles
    # ------------------------------------------------------------------

    def get_device_roles(self) -> list[dict]:
        return self._list("dcim/device-roles/")

    def get_tags(self) -> list[dict]:
        return self._list("extras/tags/")

    # ------------------------------------------------------------------
    # Change-log (for Grafana annotations)
    # ------------------------------------------------------------------

    def get_object_changes(self, since_epoch: int | None = None,
                           object_type: str | None = None,
                           limit: int = 100) -> list[dict]:
        params: dict = {"limit": limit}
        if since_epoch:
            # NetBox expects ISO 8601; convert epoch → datetime string
            import datetime
            dt = datetime.datetime.utcfromtimestamp(since_epoch)
            params["time_after"] = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        if object_type:
            params["changed_object_type"] = object_type
        return self._list("extras/object-changes/", params)

    # ------------------------------------------------------------------
    # Grafana dashboard deep-link helper
    # ------------------------------------------------------------------

    @staticmethod
    def grafana_link(grafana_url: str, uid: str,
                     var_name: str, var_value: str) -> str:
        """Return a Grafana dashboard URL with a template variable pre-set."""
        if not uid:
            return grafana_url
        base = grafana_url.rstrip("/")
        return f"{base}/d/{uid}?var-{var_name}={requests.utils.quote(str(var_value))}"
