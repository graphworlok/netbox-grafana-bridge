from django.urls import path

from . import views

app_name = "netbox_grafana_bridge"

urlpatterns = [
    path("config/",      views.GrafanaConfigView.as_view(),     name="config"),
    path("config/edit/", views.GrafanaConfigEditView.as_view(), name="config_edit"),
    path("status/",      views.GrafanaStatusView.as_view(),     name="status"),
]
