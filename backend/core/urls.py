from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("map-config/", views.map_config, name="map-config"),
]
