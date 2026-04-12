"""
netbox-grafana-bridge
=====================
A FastAPI service that acts as a bridge between Grafana and NetBox.

Two integration directions are served from a single process:

1. Grafana → NetBox  (this service is configured as a Grafana JSON API datasource)
   - POST /search         variable/metric autocomplete
   - POST /query          table / timeseries data
   - POST /annotations    NetBox change-log as Grafana annotations
   - POST /tag-keys       tag filter support
   - POST /tag-values     tag filter support

2. NetBox → Grafana  (call these endpoints from NetBox custom-links)
   - GET  /dashboard-link  returns a redirect to the right Grafana dashboard

Run with:
    uvicorn app:app --host 0.0.0.0 --port 8765
"""

from __future__ import annotations

import time
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

try:
    import config_local as cfg  # type: ignore
except ImportError:
    import config as cfg        # fall back to config.py

from netbox_client import NetBoxClient

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
log = logging.getLogger("netbox-grafana-bridge")

# ---------------------------------------------------------------------------
# App & NetBox client
# ---------------------------------------------------------------------------
app = FastAPI(title="NetBox-Grafana Bridge",
              description="Bridges Grafana JSON API datasource ↔ NetBox")

_nb: NetBoxClient | None = None

def get_nb() -> NetBoxClient:
    global _nb
    if _nb is None:
        _nb = NetBoxClient(cfg.NETBOX_URL, cfg.NETBOX_TOKEN, cfg.NETBOX_TIMEOUT)
    return _nb

# ---------------------------------------------------------------------------
# Simple in-memory cache
# ---------------------------------------------------------------------------
_cache: dict[str, tuple[float, Any]] = {}

def _cached(key: str, fn, ttl: int = cfg.CACHE_TTL):
    now = time.monotonic()
    if key in _cache:
        ts, val = _cache[key]
        if now - ts < ttl:
            return val
    val = fn()
    _cache[key] = (now, val)
    return val

# ---------------------------------------------------------------------------
# Pydantic models for Grafana JSON API protocol
# ---------------------------------------------------------------------------

class TimeRange(BaseModel):
    from_: str | None = None
    to: str | None = None

    class Config:
        populate_by_name = True
        fields = {"from_": "from"}


class Target(BaseModel):
    target: str = ""
    type: str = "table"
    data: dict | None = None
    payload: dict | None = None


class QueryRequest(BaseModel):
    range: TimeRange | None = None
    targets: list[Target] = []
    maxDataPoints: int = 1000
    interval: str = "1m"


class SearchRequest(BaseModel):
    target: str = ""


class AnnotationRequest(BaseModel):
    range: TimeRange | None = None
    annotation: dict | None = None


class TagValuesRequest(BaseModel):
    key: str = ""

# ---------------------------------------------------------------------------
# Helper: convert epoch ms → seconds
# ---------------------------------------------------------------------------

def _epoch_ms_to_s(ms_str: str | None) -> int | None:
    if not ms_str:
        return None
    try:
        return int(ms_str) // 1000
    except (TypeError, ValueError):
        return None

# ---------------------------------------------------------------------------
# Route: health / connection test
# ---------------------------------------------------------------------------

@app.get("/")
async def health():
    """Grafana tests the datasource by hitting GET /.  Must return 200."""
    return {"status": "ok", "service": "netbox-grafana-bridge"}


@app.get("/health")
async def health_detail():
    nb = get_nb()
    try:
        sites = nb.get_sites()
        return {"status": "ok", "netbox_sites": len(sites)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

# ---------------------------------------------------------------------------
# Route: /search  – autocomplete for template variables
#
# Grafana sends:  {"target": "<metric/variable query>"}
# We respond with a list of strings or {text, value} objects.
#
# Supported target prefixes:
#   devices                  – list all device names
#   devices:<site-slug>      – devices at a site
#   devices:<site>:<role>    – devices at site with role
#   interfaces:<device-name> – interfaces for a device
#   sites                    – list all sites
#   roles                    – list all device roles
#   providers                – list all circuit providers
#   circuits:<provider-slug> – circuits for a provider
#   tags                     – list all tags
#   asns                     – list all ASNs
# ---------------------------------------------------------------------------

@app.post("/search")
async def search(req: SearchRequest):
    nb = get_nb()
    t = req.target.strip()
    parts = [p.strip() for p in t.split(":")]
    kind = parts[0].lower() if parts else ""

    try:
        if kind in ("device", "devices"):
            site = parts[1] if len(parts) > 1 else None
            role = parts[2] if len(parts) > 2 else None
            devices = _cached(f"devices:{site}:{role}",
                              lambda: nb.get_devices(site=site, role=role))
            return [d["name"] for d in devices if d.get("name")]

        if kind in ("interface", "interfaces"):
            device_name = parts[1] if len(parts) > 1 else None
            if not device_name:
                return []
            ifaces = _cached(f"ifaces:{device_name}",
                             lambda: nb.get_interfaces(device=device_name))
            return [i["name"] for i in ifaces if i.get("name")]

        if kind in ("site", "sites"):
            sites = _cached("sites", nb.get_sites)
            return [{"text": s["name"], "value": s["slug"]} for s in sites]

        if kind in ("role", "roles"):
            roles = _cached("roles", nb.get_device_roles)
            return [{"text": r["name"], "value": r["slug"]} for r in roles]

        if kind in ("provider", "providers"):
            providers = _cached("providers", nb.get_providers)
            return [{"text": p["name"], "value": p["slug"]} for p in providers]

        if kind in ("circuit", "circuits"):
            provider = parts[1] if len(parts) > 1 else None
            circuits = _cached(f"circuits:{provider}",
                               lambda: nb.get_circuits(provider=provider))
            return [{"text": c["cid"], "value": c["cid"]} for c in circuits]

        if kind in ("tag", "tags"):
            tags = _cached("tags", nb.get_tags)
            return [{"text": tg["name"], "value": tg["slug"]} for tg in tags]

        if kind in ("asn", "asns"):
            asns = _cached("asns", nb.get_asns)
            return [{"text": f"AS{a['asn']}", "value": str(a["asn"])} for a in asns]

        if kind in ("prefix", "prefixes"):
            site = parts[1] if len(parts) > 1 else None
            prefixes = _cached(f"prefixes:{site}",
                               lambda: nb.get_prefixes(site=site))
            return [p["prefix"] for p in prefixes if p.get("prefix")]

        # Fallback: try device search
        devices = _cached("devices:None:None",
                          lambda: nb.get_devices())
        return [d["name"] for d in devices if d.get("name") and
                (not t or t.lower() in d["name"].lower())]

    except Exception as exc:
        log.exception("search error")
        raise HTTPException(status_code=502, detail=str(exc))

# ---------------------------------------------------------------------------
# Route: /query  – return data for Grafana panels
#
# Target formats (panel "metrics"):
#   device_table                       – table of all devices
#   device_table:<site>                – devices at a site
#   interface_table:<device>           – interfaces of a device
#   ip_table:<device>                  – IP addresses on a device
#   circuit_table                      – all circuits
#   circuit_table:<provider>           – circuits by provider
#   provider_table                     – provider + ASN table
# ---------------------------------------------------------------------------

def _table_response(columns: list[str], rows: list[list]) -> dict:
    return {
        "type": "table",
        "columns": [{"text": c, "type": "string"} for c in columns],
        "rows": rows,
    }


@app.post("/query")
async def query(req: QueryRequest):
    nb = get_nb()
    results = []

    for tgt in req.targets:
        t = tgt.target.strip()
        parts = [p.strip() for p in t.split(":")]
        kind = parts[0].lower() if parts else ""

        try:
            if kind == "device_table":
                site = parts[1] if len(parts) > 1 else None
                role = parts[2] if len(parts) > 2 else None
                devices = _cached(f"devices:{site}:{role}",
                                  lambda: nb.get_devices(site=site, role=role))
                rows = [
                    [
                        d.get("name", ""),
                        d.get("status", {}).get("label", "") if isinstance(d.get("status"), dict) else str(d.get("status", "")),
                        d.get("role", {}).get("name", "") if isinstance(d.get("role"), dict) else str(d.get("role", "")),
                        d.get("site", {}).get("name", "") if isinstance(d.get("site"), dict) else str(d.get("site", "")),
                        d.get("primary_ip", {}).get("address", "") if isinstance(d.get("primary_ip"), dict) else "",
                        d.get("platform", {}).get("name", "") if isinstance(d.get("platform"), dict) else "",
                        d.get("device_type", {}).get("model", "") if isinstance(d.get("device_type"), dict) else "",
                    ]
                    for d in devices
                ]
                results.append(_table_response(
                    ["Name", "Status", "Role", "Site", "Primary IP", "Platform", "Model"],
                    rows,
                ))

            elif kind == "interface_table":
                device_name = parts[1] if len(parts) > 1 else ""
                if not device_name:
                    results.append(_table_response(["Error"], [["No device specified"]]))
                    continue
                ifaces = _cached(f"ifaces:{device_name}",
                                 lambda: nb.get_interfaces(device=device_name))
                rows = [
                    [
                        i.get("name", ""),
                        i.get("type", {}).get("label", "") if isinstance(i.get("type"), dict) else str(i.get("type", "")),
                        i.get("enabled", False),
                        str(i.get("mac_address", "") or ""),
                        i.get("description", ""),
                        i.get("mtu", "") or "",
                        i.get("mode", {}).get("label", "") if isinstance(i.get("mode"), dict) else "",
                    ]
                    for i in ifaces
                ]
                results.append(_table_response(
                    ["Name", "Type", "Enabled", "MAC", "Description", "MTU", "Mode"],
                    rows,
                ))

            elif kind == "ip_table":
                device_name = parts[1] if len(parts) > 1 else ""
                if not device_name:
                    results.append(_table_response(["Error"], [["No device specified"]]))
                    continue
                ips = _cached(f"ips:{device_name}",
                              lambda: nb.get_ip_addresses(device=device_name))
                rows = [
                    [
                        ip.get("address", ""),
                        ip.get("family", {}).get("label", "") if isinstance(ip.get("family"), dict) else str(ip.get("family", "")),
                        ip.get("status", {}).get("label", "") if isinstance(ip.get("status"), dict) else str(ip.get("status", "")),
                        ip.get("assigned_object", {}).get("name", "") if isinstance(ip.get("assigned_object"), dict) else "",
                        ip.get("description", ""),
                    ]
                    for ip in ips
                ]
                results.append(_table_response(
                    ["Address", "Family", "Status", "Interface", "Description"],
                    rows,
                ))

            elif kind == "circuit_table":
                provider = parts[1] if len(parts) > 1 else None
                circuits = _cached(f"circuits:{provider}",
                                   lambda: nb.get_circuits(provider=provider))
                rows = [
                    [
                        c.get("cid", ""),
                        c.get("provider", {}).get("name", "") if isinstance(c.get("provider"), dict) else "",
                        c.get("type", {}).get("name", "") if isinstance(c.get("type"), dict) else "",
                        c.get("status", {}).get("label", "") if isinstance(c.get("status"), dict) else "",
                        c.get("description", ""),
                        c.get("commit_rate", "") or "",
                    ]
                    for c in circuits
                ]
                results.append(_table_response(
                    ["CID", "Provider", "Type", "Status", "Description", "Commit Rate (kbps)"],
                    rows,
                ))

            elif kind == "provider_table":
                providers = _cached("providers", nb.get_providers)
                asns = _cached("asns", nb.get_asns)
                asn_by_provider: dict[int, list[str]] = {}
                for a in asns:
                    for p in (a.get("providers") or []):
                        pid = p.get("id") if isinstance(p, dict) else p
                        asn_by_provider.setdefault(pid, []).append(str(a["asn"]))
                rows = [
                    [
                        p.get("name", ""),
                        p.get("slug", ""),
                        ", ".join(asn_by_provider.get(p.get("id", 0), [])),
                        p.get("account", "") or "",
                        p.get("comments", "") or "",
                    ]
                    for p in providers
                ]
                results.append(_table_response(
                    ["Name", "Slug", "ASNs", "Account", "Comments"],
                    rows,
                ))

            else:
                results.append(_table_response(["Error"], [[f"Unknown target: {t}"]]))

        except Exception as exc:
            log.exception("query error for target %r", t)
            results.append(_table_response(["Error"], [[str(exc)]]))

    return results

# ---------------------------------------------------------------------------
# Route: /annotations  – NetBox change-log as Grafana annotations
# ---------------------------------------------------------------------------

@app.post("/annotations")
async def annotations(req: AnnotationRequest):
    nb = get_nb()
    from_s = _epoch_ms_to_s(req.range.from_ if req.range else None)
    object_type = None
    if req.annotation and "query" in req.annotation:
        object_type = req.annotation["query"] or None

    try:
        changes = nb.get_object_changes(since_epoch=from_s,
                                        object_type=object_type,
                                        limit=200)
    except Exception as exc:
        log.exception("annotations error")
        return []

    result = []
    for ch in changes:
        import datetime
        try:
            ts = int(
                datetime.datetime.fromisoformat(
                    ch["time"].replace("Z", "+00:00")
                ).timestamp() * 1000
            )
        except (KeyError, ValueError):
            continue

        action = ch.get("action", {})
        action_label = action.get("label", "") if isinstance(action, dict) else str(action)
        changed_object_type = ch.get("changed_object_type", "")
        object_repr = ch.get("object_repr", "")
        user = ch.get("user_name", ch.get("user", "unknown"))

        result.append({
            "time": ts,
            "title": f"[NetBox] {action_label}: {object_repr}",
            "text": f"Type: {changed_object_type}<br>User: {user}",
            "tags": ["netbox", action_label.lower(), changed_object_type.split(".")[-1]],
        })

    return result

# ---------------------------------------------------------------------------
# Route: /tag-keys, /tag-values  – for ad-hoc filters
# ---------------------------------------------------------------------------

@app.post("/tag-keys")
async def tag_keys():
    return [
        {"type": "string", "text": "site"},
        {"type": "string", "text": "role"},
        {"type": "string", "text": "device"},
        {"type": "string", "text": "provider"},
        {"type": "string", "text": "tag"},
    ]


@app.post("/tag-values")
async def tag_values(req: TagValuesRequest):
    nb = get_nb()
    key = req.key.lower()
    try:
        if key == "site":
            sites = _cached("sites", nb.get_sites)
            return [{"text": s["slug"]} for s in sites]
        if key == "role":
            roles = _cached("roles", nb.get_device_roles)
            return [{"text": r["slug"]} for r in roles]
        if key == "device":
            devices = _cached("devices:None:None", lambda: nb.get_devices())
            return [{"text": d["name"]} for d in devices if d.get("name")]
        if key == "provider":
            providers = _cached("providers", nb.get_providers)
            return [{"text": p["slug"]} for p in providers]
        if key == "tag":
            tags = _cached("tags", nb.get_tags)
            return [{"text": tg["slug"]} for tg in tags]
    except Exception as exc:
        log.exception("tag-values error")
    return []

# ---------------------------------------------------------------------------
# Route: /dashboard-link
# Used as a NetBox custom-link target URL.
#
# Examples:
#   /dashboard-link?object_type=device&name=switch-01
#   /dashboard-link?object_type=site&name=london-dc1
#
# Returns a redirect to the configured Grafana dashboard with the right
# template variable pre-set.  If no dashboard UID is configured for the
# object type, redirects to Grafana's home page.
# ---------------------------------------------------------------------------

@app.get("/dashboard-link")
async def dashboard_link(
    object_type: str = Query(..., description="NetBox object type: device, site, interface, circuit, prefix"),
    name: str = Query(..., description="Name or identifier of the object"),
):
    uid = cfg.DASHBOARD_UIDS.get(object_type, "")
    var_name = cfg.DASHBOARD_VAR_PARAMS.get(object_type, object_type)
    url = NetBoxClient.grafana_link(cfg.GRAFANA_URL, uid, var_name, name)
    return RedirectResponse(url=url, status_code=302)


# ---------------------------------------------------------------------------
# Route: /netbox-link-config
# Returns JSON that a NetBox admin can use to configure custom links.
# ---------------------------------------------------------------------------

@app.get("/netbox-link-config")
async def netbox_link_config(request: Request):
    """
    Returns the recommended NetBox custom-link configuration so administrators
    can easily add 'Open in Grafana' buttons to device/site/circuit pages.
    """
    bridge_base = str(request.base_url).rstrip("/")
    configs = []
    for obj_type, uid in cfg.DASHBOARD_UIDS.items():
        if not uid:
            continue
        # NetBox uses Jinja2 template syntax for custom-link URLs.
        # The exact field varies per object type.
        field_map = {
            "device":    "{{ object.name }}",
            "site":      "{{ object.slug }}",
            "interface": "{{ object.name }}",
            "circuit":   "{{ object.cid }}",
            "prefix":    "{{ object.prefix }}",
        }
        field = field_map.get(obj_type, "{{ object.name }}")
        configs.append({
            "object_type": f"dcim.{obj_type}" if obj_type in ("device", "interface") else
                           f"ipam.{obj_type}" if obj_type in ("prefix",) else
                           f"circuits.{obj_type}" if obj_type in ("circuit",) else
                           f"dcim.{obj_type}",
            "name": f"Open in Grafana",
            "url": f"{bridge_base}/dashboard-link?object_type={obj_type}&name={field}",
            "new_window": True,
            "button_class": "default",
        })
    return {
        "note": "Add these as NetBox custom-links (Customization → Custom Links) to "
                "get an 'Open in Grafana' button on each object's detail page.",
        "custom_links": configs,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host=cfg.BRIDGE_HOST, port=cfg.BRIDGE_PORT, reload=False)
