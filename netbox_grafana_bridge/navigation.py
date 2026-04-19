from netbox.plugins.navigation import PluginMenu, PluginMenuButton, PluginMenuItem

menu = PluginMenu(
    label="Grafana Bridge",
    groups=(
        (
            "Grafana",
            (
                PluginMenuItem(
                    link="plugins:netbox_grafana_bridge:config",
                    link_text="Configuration",
                    buttons=(
                        PluginMenuButton(
                            link="plugins:netbox_grafana_bridge:config_edit",
                            title="Edit configuration",
                            icon_class="mdi mdi-pencil",
                        ),
                    ),
                ),
                PluginMenuItem(
                    link="plugins:netbox_grafana_bridge:status",
                    link_text="Bridge Status",
                    buttons=(
                        PluginMenuButton(
                            link="plugins:netbox_grafana_bridge:status",
                            title="Check bridge connectivity",
                            icon_class="mdi mdi-heart-pulse",
                        ),
                    ),
                ),
            ),
        ),
    ),
    icon_class="mdi mdi-chart-line",
)
