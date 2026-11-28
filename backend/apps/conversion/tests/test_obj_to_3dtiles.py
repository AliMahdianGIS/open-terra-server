"""OBJ -> 3D Tiles pipeline, with a fake Obj2Tiles so it runs anywhere (no .NET needed)."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from django.core.management import CommandError, call_command
from pyproj import CRS

from apps.conversion.obj_to_3dtiles import ObjOptions, convert_obj
from apps.conversion.runner import ConversionError, ToolFailedError, ToolNotFoundError

from .helpers import (
    SITES,
    Site,
    apply_transform,
    expected_ecef,
    obj_to_tile_frame,
    read_obj_vertices,
    write_box_obj,
    write_prj,
)

FAKE = [sys.executable, str(Path(__file__).with_name("fake_obj2tiles.py"))]


def _dataset(root: Path, site: Site, *, up_axis: str = "z", prj: bool = True) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    obj = root / "model.obj"
    write_box_obj(obj, site.box_corners(), up_axis=up_axis)
    if prj:
        write_prj(root / "model.prj", site.crs, "WKT2_2019")
    return obj


def _axis_order(site: Site) -> str:
    return "crs" if site.stored_northing_first else "xy"


def _height_factor(site: Site) -> float:
    from apps.conversion.georef import SourceCRS

    return SourceCRS.from_crs(site.crs).height_factor


@pytest.mark.parametrize("site", SITES, ids=lambda s: s.id)
def test_single_obj_is_placed_where_proj_puts_it(tmp_path: Path, site: Site) -> None:
    obj = _dataset(tmp_path / "in", site)
    out = tmp_path / "out"
    result = convert_obj(obj, out, ObjOptions(axis_order=_axis_order(site)), obj2tiles=FAKE)

    tileset = json.loads(result.tileset.read_text(encoding="utf-8"))
    received = read_obj_vertices(out / "received.obj")
    ecef = apply_transform(tileset["root"]["transform"], obj_to_tile_frame(received))
    expected = expected_ecef(site, site.box_corners(), _height_factor(site))
    assert np.abs(ecef - expected).max() < 1e-3  # 1 mm, limited by the 4 decimals written
    assert result.vertices == 8
    lon, lat, _ = result.origin_lon_lat_height
    assert lat == pytest.approx(site.lat, abs=1e-6)
    assert not (out / ".work").exists()


@pytest.mark.parametrize("site", SITES[:4], ids=lambda s: s.id)
def test_y_up_obj_gives_the_same_result(tmp_path: Path, site: Site) -> None:
    results = []
    for up in ("z", "y"):
        obj = _dataset(tmp_path / up / "in", site, up_axis=up)
        out = tmp_path / up / "out"
        options = ObjOptions(axis_order=_axis_order(site), up_axis=up)
        convert_obj(obj, out, options, obj2tiles=FAKE)
        results.append(read_obj_vertices(out / "received.obj"))
    assert np.abs(results[0] - results[1]).max() < 1e-3


def test_rewrite_keeps_other_lines_and_fixes_material_paths(tmp_path: Path) -> None:
    site = SITES[1]
    obj = _dataset(tmp_path / "in folder", site)
    convert_obj(obj, tmp_path / "out", obj2tiles=FAKE)
    original = obj.read_text(encoding="utf-8").splitlines()
    received = (tmp_path / "out" / "received.obj").read_text(encoding="utf-8").splitlines()

    assert len(original) == len(received)
    kept = [a for a, b in zip(original, received, strict=True) if a == b]
    assert [line for line in original if line.startswith(("f ", "vt ", "o ", "g ", "usemtl"))] == [
        line for line in kept if line.startswith(("f ", "vt ", "o ", "g ", "usemtl"))
    ]
    mtllib = next(line for line in received if line.startswith("mtllib"))
    mtl_path = Path(mtllib[len("mtllib ") :])
    assert mtl_path.is_absolute()
    assert mtl_path.resolve() == (tmp_path / "in folder" / "box.mtl").resolve()
    # An up normal stays up in the (east, north, up) output.
    vn = next(line for line in received if line.startswith("vn")).split()[1:]
    assert float(vn[2]) == pytest.approx(1.0, abs=1e-3)


def test_obj2tiles_gets_local_mode_and_options(tmp_path: Path) -> None:
    obj = _dataset(tmp_path / "in", SITES[0])
    options = ObjOptions(lods=4, divisions=3, obj2tiles_args=["--unlit"])
    convert_obj(obj, tmp_path / "out", options, obj2tiles=FAKE)
    args = json.loads((tmp_path / "out" / "args.json").read_text(encoding="utf-8"))
    assert "--local" in args and "--no-zsplit" in args and "--unlit" in args
    assert args[args.index("--lods") + 1] == "4"
    assert args[args.index("--divisions") + 1] == "3"


def test_folder_of_objs_becomes_one_tileset(tmp_path: Path) -> None:
    site = SITES[5]  # a compound CRS, with the .prj at the top of the folder
    root = tmp_path / "in"
    corners = site.box_corners()
    for i, sub in enumerate(["tile_a/x", "tile_b", "tile b"]):  # unusual names on purpose
        folder = root / sub
        folder.mkdir(parents=True)
        write_box_obj(folder / "mesh.obj", corners + [i * 300.0, 0, 0])
    write_prj(root / "dataset.prj", site.crs)

    result = convert_obj(root, tmp_path / "out", obj2tiles=FAKE)
    assert result.parts == 3
    tileset = json.loads(result.tileset.read_text(encoding="utf-8"))
    children = tileset["root"]["children"]
    # "tile_b" and "tile b" sanitise to the same name; the parts must still be distinct.
    uris = sorted(c["content"]["uri"] for c in children)
    assert uris == [
        "parts/tile_a_x_mesh/tileset.json",
        "parts/tile_b_mesh-2/tileset.json",
        "parts/tile_b_mesh/tileset.json",
    ]
    for child in children:
        part = json.loads((tmp_path / "out" / child["content"]["uri"]).read_text("utf-8"))
        assert "transform" not in part["root"]  # inherits the root transform
    # The root box contains every part's box.
    box = np.array(tileset["root"]["boundingVolume"]["box"])
    for child in children:
        c = np.array(child["boundingVolume"]["box"])
        assert np.all(np.abs(c[:3] - box[:3]) + np.abs(c[[3, 7, 11]]) <= box[[3, 7, 11]] + 1e-9)
    # All parts share one frame, so they keep their 300 m spacing.
    centres = [read_obj_vertices(tmp_path / "out" / Path(u).parent / "received.obj").mean(0)
               for u in uris]  # fmt: skip
    gaps = sorted(np.linalg.norm(p - q) for i, p in enumerate(centres) for q in centres[i + 1 :])
    assert gaps == pytest.approx([300.0, 300.0, 600.0], rel=1e-3)


def test_user_crs_is_used_without_prj(tmp_path: Path) -> None:
    site = SITES[2]
    obj = _dataset(tmp_path / "in", site, prj=False)
    result = convert_obj(obj, tmp_path / "out", ObjOptions(crs="EPSG:2263"), obj2tiles=FAKE)
    assert "Long Island" in result.crs_name


def test_missing_crs_is_a_clear_error(tmp_path: Path) -> None:
    obj = _dataset(tmp_path / "in", SITES[0], prj=False)
    with pytest.raises(ConversionError, match="--crs"):
        convert_obj(obj, tmp_path / "out", obj2tiles=FAKE)


def test_conflicting_prj_files_are_an_error(tmp_path: Path) -> None:
    root = tmp_path / "in"
    for name, epsg in (("a", 32633), ("b", 25833)):
        (root / name).mkdir(parents=True)
        write_box_obj(root / name / "m.obj", SITES[0].box_corners())
        write_prj(root / name / "m.prj", CRS.from_epsg(epsg))
    with pytest.raises(ConversionError, match="disagree"):
        convert_obj(root, tmp_path / "out", obj2tiles=FAKE)


def test_non_empty_output_is_refused(tmp_path: Path) -> None:
    obj = _dataset(tmp_path / "in", SITES[0])
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "old.txt").write_text("x")
    with pytest.raises(ConversionError, match="not empty"):
        convert_obj(obj, tmp_path / "out", obj2tiles=FAKE)


def test_obj_without_vertices_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "empty.obj").write_text("# nothing\n")
    with pytest.raises(ConversionError, match="no vertices"):
        convert_obj(tmp_path / "in", tmp_path / "out", ObjOptions(crs="EPSG:32633"),
                    obj2tiles=FAKE)  # fmt: skip


def test_tool_failure_reports_its_output(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_OBJ2TILES_FAIL", "1")
    obj = _dataset(tmp_path / "in", SITES[0])
    with pytest.raises(ToolFailedError, match="could not read the mesh") as info:
        convert_obj(obj, tmp_path / "out", obj2tiles=FAKE)
    assert info.value.returncode == 3
    assert not (tmp_path / "out" / ".work").exists()


def test_missing_tool_is_a_clear_error(tmp_path: Path, settings) -> None:
    settings.OBJ2TILES_PATH = str(tmp_path / "no-such-obj2tiles")
    obj = _dataset(tmp_path / "in", SITES[0])
    with pytest.raises(ToolNotFoundError, match="OBJ2TILES_PATH"):
        convert_obj(obj, tmp_path / "out")


def test_convert_command(tmp_path: Path, monkeypatch, capsys) -> None:
    site = SITES[3]  # stored northing first: the command's auto axis order must find it
    obj = _dataset(tmp_path / "in", site, prj=False)
    monkeypatch.setattr("apps.conversion.obj_to_3dtiles.obj2tiles_command", lambda: FAKE)
    call_command("convert", str(obj), str(tmp_path / "out"), "--crs", "EPSG:3879", "--lods", "2")
    out = capsys.readouterr().out
    assert "GK25FIN (northing first)" in out
    assert (tmp_path / "out" / "tileset.json").is_file()


def test_convert_command_reports_errors(tmp_path: Path) -> None:
    with pytest.raises(CommandError, match="does not exist"):
        call_command("convert", str(tmp_path / "missing.obj"), str(tmp_path / "out"))
