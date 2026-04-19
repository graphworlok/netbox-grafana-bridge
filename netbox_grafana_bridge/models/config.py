from django.db import models
from django.urls import reverse


class GrafanaConfig(models.Model):
    """
    Singleton model storing Grafana bridge connection configuration.
    Only one row should ever exist; the view enforces this by using get_or_create.
    """
    grafana_url = models.URLField(
        verbose_name="Grafana URL",
        help_text="Base URL of your Grafana instance (e.g. https://grafana.example.com).",
        blank=True,
    )
    bridge_url = models.URLField(
        verbose_name="Bridge Service URL",
        help_text="URL where the netbox-grafana-bridge FastAPI service is running (e.g. http://localhost:8765).",
        blank=True,
    )
    cache_ttl = models.PositiveIntegerField(
        verbose_name="Cache TTL (seconds)",
        default=60,
        help_text="How long the bridge caches NetBox responses for Grafana variable queries.",
    )

    # Dashboard UIDs per object type
    dashboard_uid_device    = models.CharField(max_length=100, blank=True, verbose_name="Device dashboard UID")
    dashboard_uid_interface = models.CharField(max_length=100, blank=True, verbose_name="Interface dashboard UID")
    dashboard_uid_site      = models.CharField(max_length=100, blank=True, verbose_name="Site dashboard UID")
    dashboard_uid_prefix    = models.CharField(max_length=100, blank=True, verbose_name="Prefix dashboard UID")
    dashboard_uid_circuit   = models.CharField(max_length=100, blank=True, verbose_name="Circuit dashboard UID")

    class Meta:
        verbose_name = "Grafana Configuration"
        verbose_name_plural = "Grafana Configuration"

    def __str__(self) -> str:
        return "Grafana Bridge Configuration"

    def get_absolute_url(self) -> str:
        return reverse("plugins:netbox_grafana_bridge:config")

    def dashboard_uids(self) -> dict:
        return {
            "device":    self.dashboard_uid_device,
            "interface": self.dashboard_uid_interface,
            "site":      self.dashboard_uid_site,
            "prefix":    self.dashboard_uid_prefix,
            "circuit":   self.dashboard_uid_circuit,
        }
