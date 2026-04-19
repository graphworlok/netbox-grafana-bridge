import urllib.request
import urllib.error
import json

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from ..forms import GrafanaConfigForm
from ..models import GrafanaConfig


def _get_config() -> GrafanaConfig:
    obj, _ = GrafanaConfig.objects.get_or_create(pk=1)
    return obj


class GrafanaConfigView(View):
    template_name = "netbox_grafana_bridge/config.html"

    def get(self, request):
        cfg = _get_config()
        return render(request, self.template_name, {"object": cfg})


class GrafanaConfigEditView(View):
    template_name = "netbox_grafana_bridge/config_edit.html"

    def get(self, request):
        cfg  = _get_config()
        form = GrafanaConfigForm(instance=cfg)
        return render(request, self.template_name, {"form": form, "object": cfg})

    def post(self, request):
        cfg  = _get_config()
        form = GrafanaConfigForm(request.POST, instance=cfg)
        if form.is_valid():
            form.save()
            messages.success(request, "Grafana bridge configuration saved.")
            return redirect("plugins:netbox_grafana_bridge:config")
        return render(request, self.template_name, {"form": form, "object": cfg})


class GrafanaStatusView(View):
    template_name = "netbox_grafana_bridge/status.html"

    def get(self, request):
        cfg    = _get_config()
        status = {"reachable": False, "detail": "", "health": None}

        if cfg.bridge_url:
            health_url = cfg.bridge_url.rstrip("/") + "/health"
            try:
                with urllib.request.urlopen(health_url, timeout=5) as resp:
                    body = resp.read().decode()
                    status["reachable"] = True
                    status["health"]    = json.loads(body)
                    status["detail"]    = f"HTTP {resp.status}"
            except urllib.error.HTTPError as exc:
                status["detail"] = f"HTTP {exc.code}: {exc.reason}"
            except urllib.error.URLError as exc:
                status["detail"] = str(exc.reason)
            except Exception as exc:
                status["detail"] = str(exc)
        else:
            status["detail"] = "Bridge URL not configured."

        return render(request, self.template_name, {"object": cfg, "status": status})
