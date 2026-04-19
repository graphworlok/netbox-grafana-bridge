from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="GrafanaConfig",
            fields=[
                ("id",                   models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("grafana_url",          models.URLField(blank=True, verbose_name="Grafana URL")),
                ("bridge_url",           models.URLField(blank=True, verbose_name="Bridge Service URL")),
                ("cache_ttl",            models.PositiveIntegerField(default=60, verbose_name="Cache TTL (seconds)")),
                ("dashboard_uid_device",    models.CharField(blank=True, max_length=100, verbose_name="Device dashboard UID")),
                ("dashboard_uid_interface", models.CharField(blank=True, max_length=100, verbose_name="Interface dashboard UID")),
                ("dashboard_uid_site",      models.CharField(blank=True, max_length=100, verbose_name="Site dashboard UID")),
                ("dashboard_uid_prefix",    models.CharField(blank=True, max_length=100, verbose_name="Prefix dashboard UID")),
                ("dashboard_uid_circuit",   models.CharField(blank=True, max_length=100, verbose_name="Circuit dashboard UID")),
            ],
            options={"verbose_name": "Grafana Configuration", "verbose_name_plural": "Grafana Configuration"},
        ),
    ]
