"""End to end with the real Obj2Tiles. Skipped unless it is on PATH or OBJ2TILES_PATH is set."""

import json
import struct
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from django.conf import settings
from pyproj import Transformer

from apps.conversion.georef import SourceCRS
from apps.conversion.obj_to_3dtiles import ObjOptions, convert_obj, obj2tiles_command
from apps.conversion.runner import ToolNotFoundError

from .helpers import SITES, apply_transform, write_box_obj, write_prj

try:
    obj2tiles_command()
    HAVE_OBJ2TILES = True
except ToolNotFoundError:
    HAVE_OBJ2TILES = False

pytestmark = pytest.mark.skipif(
    not HAVE_OBJ2TILES, reason=f"Obj2Tiles not found (OBJ2TILES_PATH={settings.OBJ2TILES_PATH!r})"
)

# Southern + western hemisphere, US feet, northing-first file, antimeridian, compound CRS.
REAL_SITES = [s for s in SITES if s.epsg in (31983, 2263, 3879, 3460, 7415)]


def _glb_positions(path: Path) -> Iterator[np.ndarray]:
    data = path.read_bytes()
    json_len = struct.unpack("<I", data[12:16])[0]
    gltf = json.loads(data[20 : 20 + json_len])
    assert not gltf.get("extensionsRequired"), "compressed glTF is not decoded by this test"
    bin_start = 20 + json_len + 8
    for mesh in gltf["meshes"]:
        for prim in mesh["primitives"]:
            acc = gltf["accessors"][prim["attributes"]["POSITION"]]
            view = gltf["bufferViews"][acc["bufferView"]]
            offset = bin_start + view.get("byteOffset", 0) + acc.get("byteOffset", 0)
            yield np.frombuffer(data, "<f4", acc["count"] * 3, offset).reshape(-1, 3)


def _walk(tile: dict, parent_error: float) -> Iterator[dict]:
    assert None not in tile.values()
    assert tile["geometricError"] <= parent_error + 1e-9
    yield tile
    for child in tile.get("children", []):
        yield from _walk(child, tile["geometricError"])


@pytest.mark.parametrize("site", REAL_SITES, ids=lambda s: s.id)
def test_real_obj2tiles_output_is_in_place(tmp_path: Path, site) -> None:
    src = tmp_path / "in"
    src.mkdir()
    corners = site.box_corners()
    write_box_obj(src / "model.obj", corners, mtl_name=None)
    write_prj(src / "model.prj", site.crs, "WKT2_2019")
    options = ObjOptions(axis_order="crs" if site.stored_northing_first else "xy", lods=2,
                         divisions=1)  # fmt: skip
    result = convert_obj(src / "model.obj", tmp_path / "out", options)

    tileset = json.loads(result.tileset.read_text(encoding="utf-8"))
    assert tileset["asset"]["version"] == "1.1"
    tiles = list(_walk(tileset["root"], tileset["geometricError"]))
    assert any(t.get("content", {}).get("uri", "").endswith(".glb") for t in tiles)

    # Every finest-LOD vertex, taken back through glTF Y-up -> tile frame -> root transform
    # -> source CRS, lies on the original box.
    glb = np.vstack([p for f in (tmp_path / "out" / "LOD-0").glob("*.glb")
                     for p in _glb_positions(f)]).astype(np.float64)  # fmt: skip
    tile_frame = np.column_stack([glb[:, 0], -glb[:, 2], glb[:, 1]])
    ecef = apply_transform(tileset["root"]["transform"], tile_frame)
    source = SourceCRS.from_crs(site.crs)
    back = Transformer.from_crs(4978, source.horizontal.to_3d(), always_xy=True)
    east, north, h = back.transform(*ecef.T)
    a, b = (north, east) if site.stored_northing_first else (east, north)
    pts = np.column_stack([a, b, np.asarray(h) / source.height_factor])

    lo, hi = corners.min(0), corners.max(0)
    unit = 1e-7 if site.crs.is_geographic else 1e-3  # ~1 cm in degrees, 1 mm otherwise
    # Obj2Tiles adds vertices on straight edges between the (exact) corners. A straight edge
    # of length L sags up to L^2 / 8R below a surface of constant height, so allow for that.
    longest = np.linalg.norm(np.ptp(tile_frame, axis=0))
    sag = longest**2 / (8 * 6.371e6)
    tol = np.array([unit, unit, (1e-3 + sag) / source.height_factor])
    outside = (np.maximum(lo - pts, 0) + np.maximum(pts - hi, 0)) / tol
    assert outside.max() <= 1.0, f"{outside.max(0)} x tolerance outside the box"
    on_face = np.min(np.minimum(np.abs(pts - lo), np.abs(pts - hi)) / tol, axis=1)
    assert on_face.max() <= 1.0, f"{on_face.max():.1f} x tolerance off the faces"
    # The original corners come through exactly (to 1 mm).
    strict = np.array([unit, unit, 1e-3 / source.height_factor])
    for corner in corners:
        assert np.min(np.max(np.abs(pts - corner) / strict, axis=1)) <= 1.0
