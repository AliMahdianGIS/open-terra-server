import numpy as np
import pytest
from pyproj import CRS, Transformer

from apps.conversion.georef import (
    LocalFrame,
    SourceCRS,
    check_area_of_use,
    choose_axis_order,
    parse_crs,
    read_crs_file,
)
from apps.conversion.runner import ConversionError

from .helpers import SITES, Site, expected_ecef, write_prj


def _frame(site: Site, mode: str = "auto") -> tuple[LocalFrame, np.ndarray]:
    corners = site.box_corners()
    source = SourceCRS.from_crs(site.crs)
    swap, _ = choose_axis_order(source, mode, corners.min(0), corners.max(0))
    origin = (corners.min(0) + corners.max(0)) / 2
    return LocalFrame(source, tuple(origin), swap_xy=swap), corners


@pytest.mark.parametrize("site", SITES, ids=lambda s: s.id)
def test_vertices_land_where_proj_puts_them(site: Site) -> None:
    frame, corners = _frame(site)
    local = frame.to_local(corners)
    # Local ENU metres back to ECEF through the tileset matrix.
    m = np.array(frame.tileset_transform()).reshape(4, 4).T
    ecef = (np.column_stack([local, np.ones(len(local))]) @ m.T)[:, :3]
    expected = expected_ecef(site, corners, frame.source.height_factor)
    assert np.abs(ecef - expected).max() < 1e-3  # 1 mm


@pytest.mark.parametrize("site", SITES, ids=lambda s: s.id)
def test_origin_is_at_the_site(site: Site) -> None:
    frame, _ = _frame(site)
    lon, lat, _ = frame.origin_lon_lat_height
    assert lat == pytest.approx(site.lat, abs=1e-6)
    assert (lon - site.lon + 180) % 360 - 180 == pytest.approx(0, abs=1e-6)


@pytest.mark.parametrize("site", SITES, ids=lambda s: s.id)
def test_auto_axis_order_matches_the_file(site: Site) -> None:
    corners = site.box_corners()
    swap, warning = choose_axis_order(
        SourceCRS.from_crs(site.crs), "auto", corners.min(0), corners.max(0)
    )
    assert swap is site.stored_northing_first
    assert warning is None


@pytest.mark.parametrize("site", SITES, ids=lambda s: s.id)
def test_local_frame_is_east_north_up(site: Site) -> None:
    frame, corners = _frame(site)
    local = frame.to_local(corners)
    # The box is a few hundred metres at most and sits around the origin.
    assert np.abs(local).max() < 500
    # Points with a larger height are higher in the local frame.
    low, high = (
        local[corners[:, 2] == corners[:, 2].min()],
        local[corners[:, 2] > corners[:, 2].min()],
    )
    assert high[:, 2].mean() > low[:, 2].mean()
    # An up normal stays (almost) up; grid convergence only tilts it slightly.
    up = frame.normals_to_local(np.array([[0.0, 0.0, 1.0]]))[0]
    assert up[2] > 0.999


def test_control_point_utm_central_meridian_on_the_equator() -> None:
    # Independent of PROJ: (500000 E, 0 N) in UTM 33N is 15°E on the equator.
    source = SourceCRS.from_crs(CRS.from_epsg(32633))
    frame = LocalFrame(source, (500000.0, 0.0, 0.0), swap_xy=False)
    lon, lat, h = frame.origin_lon_lat_height
    assert (lon, lat, h) == pytest.approx((15.0, 0.0, 0.0), abs=1e-7)
    assert frame.origin_ecef == pytest.approx(
        [6378137.0 * np.cos(np.radians(15)), 6378137.0 * np.sin(np.radians(15)), 0.0], abs=1e-3
    )


def test_us_survey_feet_are_converted_to_metres() -> None:
    source = SourceCRS.from_crs(CRS.from_epsg(2263))  # NY Long Island, US survey feet
    assert source.height_factor == pytest.approx(1200 / 3937)
    x, y = Transformer.from_crs(4326, 2263, always_xy=True).transform(-73.99, 40.75)
    frame = LocalFrame(source, (x, y, 0.0), swap_xy=False)
    local = frame.to_local(np.array([[x, y, 0.0], [x, y, 1000.0], [x + 1000.0, y, 0.0]]))
    assert local[1, 2] - local[0, 2] == pytest.approx(304.8006, abs=1e-3)
    # Horizontal distance is scaled by the projection's scale factor (close to 1).
    assert np.linalg.norm(local[2] - local[0]) == pytest.approx(304.8006, rel=1e-4)


def test_height_offset_and_override() -> None:
    source = SourceCRS.from_crs(CRS.from_epsg(32633), height_unit_factor=0.01)  # centimetres
    frame = LocalFrame(source, (389000.0, 5819000.0, 0.0), swap_xy=False, height_offset=12.5)
    lon, lat, h = frame.origin_lon_lat_height
    local = frame.to_local(np.array([[389000.0, 5819000.0, 1000.0]]))
    assert h == pytest.approx(12.5, abs=1e-6)
    assert local[0, 2] == pytest.approx(10.0, abs=1e-6)


def test_compound_crs_uses_its_horizontal_part_and_vertical_unit() -> None:
    source = SourceCRS.from_crs(CRS.from_epsg(7415))  # RD New + NAP height
    assert source.horizontal.to_epsg() == 28992
    assert source.height_factor == 1.0
    # Heights are taken as ellipsoidal heights on the source datum (Bessel for RD New), so
    # PROJ's datum shift to WGS 84 changes them. No geoid is applied yet (plan P4.1).
    frame = LocalFrame(source, (121000.0, 487000.0, 7.0), swap_xy=False)
    expected = Transformer.from_crs(CRS.from_epsg(28992).to_3d(), 4979, always_xy=True).transform(
        121000.0, 487000.0, 7.0
    )
    assert frame.origin_lon_lat_height == pytest.approx(expected, abs=1e-6)


def test_explicit_axis_orders() -> None:
    source = SourceCRS.from_crs(CRS.from_epsg(3879))  # GK25FIN defines northing first
    lo, hi = np.zeros(3), np.ones(3)
    assert choose_axis_order(source, "xy", lo, hi) == (False, None)
    assert choose_axis_order(source, "crs", lo, hi) == (True, None)


def test_auto_axis_order_warns_when_it_cannot_tell() -> None:
    source = SourceCRS.from_crs(CRS.from_epsg(3879))
    far = np.array([0.0, 0.0, 0.0])  # neither order lands in Finland
    swap, warning = choose_axis_order(source, "auto", far, far)
    assert swap is False
    assert warning and "--axis-order" in warning


def test_warns_when_data_is_outside_the_crs_area() -> None:
    source = SourceCRS.from_crs(CRS.from_epsg(2056))  # Switzerland
    frame = LocalFrame(source, (2600000.0, -4000000.0, 0.0), swap_xy=False)  # far south
    assert "outside the area of use" in (check_area_of_use(source, frame) or "")


@pytest.mark.parametrize("flavour", ["WKT1_ESRI", "WKT1_GDAL", "WKT2_2019", "PROJJSON"])
@pytest.mark.parametrize("epsg", [32633, 2263, 7855, 3879, 6697])
def test_reads_prj_in_every_flavour(tmp_path, flavour: str, epsg: int) -> None:
    crs = CRS.from_epsg(epsg)
    path = tmp_path / "data.prj"
    write_prj(path, crs, flavour)
    parsed = read_crs_file(path)
    # WKT1 can't express every axis order, so compare positions, not definitions.
    lon, lat = (crs.area_of_use.west + crs.area_of_use.east) / 2, crs.area_of_use.north - 1
    want = Transformer.from_crs(4326, crs, always_xy=True).transform(lon, lat)
    got = Transformer.from_crs(4326, parsed, always_xy=True).transform(lon, lat)
    assert got == pytest.approx(want, abs=1e-6)


def test_parse_crs_from_user_input(tmp_path) -> None:
    assert parse_crs("EPSG:25833").to_epsg() == 25833
    assert parse_crs("2263").to_epsg() == 2263
    assert parse_crs(CRS.from_epsg(3879).to_wkt()).equals(CRS.from_epsg(3879))
    path = tmp_path / "crs.prj"
    write_prj(path, CRS.from_epsg(7855))
    assert parse_crs(str(path)).equals(CRS.from_epsg(7855), ignore_axis_order=True)
    with pytest.raises(ConversionError, match="Could not understand"):
        parse_crs("not a crs")


def test_rejects_crs_that_cannot_be_placed() -> None:
    with pytest.raises(ConversionError, match="not a projected or geographic"):
        SourceCRS.from_crs(CRS.from_epsg(5703))  # NAVD88 height only
