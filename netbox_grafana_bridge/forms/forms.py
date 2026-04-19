from django import forms

from ..models import GrafanaConfig


class GrafanaConfigForm(forms.ModelForm):
    class Meta:
        model  = GrafanaConfig
        fields = [
            "grafana_url", "bridge_url", "cache_ttl",
            "dashboard_uid_device", "dashboard_uid_interface",
            "dashboard_uid_site", "dashboard_uid_prefix", "dashboard_uid_circuit",
        ]
        help_texts = {
            "grafana_url":  "e.g. https://grafana.example.com",
            "bridge_url":   "e.g. http://localhost:8765",
            "cache_ttl":    "Seconds to cache NetBox API responses in the bridge.",
        }
