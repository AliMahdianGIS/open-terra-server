from django.apps import AppConfig


class ConversionConfig(AppConfig):
    """Converts uploaded 3D layers between formats (OBJ, glTF, 3D Tiles, SLPK, I3S)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.conversion"
    label = "conversion"
    verbose_name = "Format conversion"
