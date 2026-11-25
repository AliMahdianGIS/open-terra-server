from django.conf import settings
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response


@extend_schema(
    responses=inline_serializer("Health", {"status": serializers.CharField()}),
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request: Request) -> Response:
    return Response({"status": "ok"})


@extend_schema(
    responses=inline_serializer(
        "MapConfig",
        {"cesium_ion_token": serializers.CharField(allow_blank=True)},
    ),
)
@api_view(["GET"])
@permission_classes([AllowAny])
def map_config(request: Request) -> Response:
    """Settings the web map needs at startup. An empty token means: use the OSM fallback."""
    return Response({"cesium_ion_token": settings.CESIUM_ION_TOKEN})
