from netbox.plugins import PluginConfig


class GrafanaBridgeConfig(PluginConfig):
    name = "netbox_grafana_bridge"
    verbose_name = "Grafana Bridge"
    description = "Configure and monitor the NetBox ↔ Grafana bridge service"
    version = "0.1.0"
    author = "graphworlok"
    base_url = "grafana"
    min_version = "4.0.0"

    default_settings = {}


config = GrafanaBridgeConfig
