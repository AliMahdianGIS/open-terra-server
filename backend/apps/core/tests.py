from django.test import Client, override_settings


def test_health() -> None:
    response = Client().get("/api/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@override_settings(CESIUM_ION_TOKEN="")
def test_map_config_without_token() -> None:
    response = Client().get("/api/map-config/")
    assert response.status_code == 200
    assert response.json() == {"cesium_ion_token": ""}


@override_settings(CESIUM_ION_TOKEN="abc")
def test_map_config_with_token() -> None:
    assert Client().get("/api/map-config/").json() == {"cesium_ion_token": "abc"}
