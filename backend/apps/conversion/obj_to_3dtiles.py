"""OBJ -> 3D Tiles 1.1 with levels of detail, through Obj2Tiles.

Steps:

1. Find the OBJ files (one file, or every ``.obj`` below a folder) and their CRS (given by the
   user, or from ``.prj`` files).
2. Compute one local east-north-up frame for the whole dataset, centred on its bounding box.
3. Rewrite each OBJ with every vertex reprojected into that frame (metres).
4. Run Obj2Tiles in local mode on each OBJ: it decimates into LODs, splits into spatial tiles
   and writes a tileset with geometric errors.
5. Put the frame's exact ENU -> ECEF matrix (after the glTF Y-up fix) on the root. With
   several OBJ files, a root tileset references each part's tileset.
"""

from __future__ import annotations

import json
import shutil
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from django.conf import settings
from pyproj import CRS

from .georef import (
    AxisOrder,
    LocalFrame,
    SourceCRS,
    check_area_of_use,
    choose_axis_order,
    parse_crs,
    read_crs_file,
)
from .obj import ObjPart, UpAxis, find_obj_parts, rewrite_obj, scan_bounds
from .runner import ConversionError, OutputCallback, resolve_tool, run_tool

IDENTITY = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]

# The rewritten OBJ is (east, north, up) and Obj2Tiles copies it into glTF as is. 3D Tiles
# reads glTF as Y-up and turns it Z-up: glTF (x, y, z) becomes tile (x, -z, y), so a tile
# point t is (east, -up, north). This maps it back to east-north-up.
TILE_TO_ENU = np.array(
    [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, -1.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
)


@dataclass
class ObjOptions:
    crs: str | None = None  # EPSG code, WKT, PROJJSON or a file; default: read .prj files
    axis_order: AxisOrder = "auto"
    up_axis: UpAxis = "z"
    height_offset: float = 0.0  # metres, added to every height
    height_unit_factor: float | None = None  # metres per height unit; default from the CRS
    lods: int = 3
    divisions: int = 2
    obj2tiles_args: list[str] = field(default_factory=list)  # passed through to Obj2Tiles


@dataclass
class ConversionResult:
    tileset: Path
    parts: int
    vertices: int
    crs_name: str
    origin_lon_lat_height: tuple[float, float, float]
    swap_xy: bool
    warnings: list[str]


def convert_obj(
    input_path: Path,
    output_dir: Path,
    options: ObjOptions | None = None,
    *,
    obj2tiles: Sequence[str] | None = None,
    on_output: OutputCallback | None = None,
    on_step: Callable[[str], None] | None = None,
    cancel: threading.Event | None = None,
) -> ConversionResult:
    """Convert an OBJ file or a folder of OBJ files to a 3D Tiles tileset in ``output_dir``.

    ``obj2tiles`` is the command to run (default: ``OBJ2TILES_PATH`` or ``Obj2Tiles`` on PATH).
    """
    options = options or ObjOptions()
    step = on_step or (lambda _msg: None)
    if options.lods < 1 or options.divisions < 0:
        raise ConversionError("--lods must be at least 1 and --divisions at least 0.")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ConversionError(f"The output folder {output_dir} is not empty.")
    input_path = input_path.resolve()
    parts = find_obj_parts(input_path)
    command = list(obj2tiles) if obj2tiles else obj2tiles_command()
    warnings: list[str] = []

    step(f"Reading {len(parts)} OBJ file(s)")
    bounds = [scan_bounds(part.path, options.up_axis) for part in parts]
    empty = [part.path.name for part, (_, _, n) in zip(parts, bounds, strict=True) if n == 0]
    if empty:
        warnings.append(f"Skipped OBJ files without vertices: {', '.join(empty)}")
    used = [(p, b) for p, b in zip(parts, bounds, strict=True) if b[2] > 0]
    if not used:
        raise ConversionError("The OBJ input has no vertices.")
    lo = np.min([b[0] for _, b in used], axis=0)
    hi = np.max([b[1] for _, b in used], axis=0)
    vertices = sum(b[2] for _, b in used)

    source = SourceCRS.from_crs(
        _resolve_crs(options.crs, input_path, [p for p, _ in used]),
        options.height_unit_factor,
    )
    swap_xy, warning = choose_axis_order(source, options.axis_order, lo, hi)
    if warning:
        warnings.append(warning)
    origin = (lo + hi) / 2
    frame = LocalFrame(
        source,
        (float(origin[0]), float(origin[1]), float(origin[2])),
        swap_xy=swap_xy,
        height_offset=options.height_offset,
    )
    warning = check_area_of_use(source, frame)
    if warning:
        warnings.append(warning)

    output_dir.mkdir(parents=True, exist_ok=True)
    work = output_dir / ".work"
    work.mkdir()
    try:
        single = len(used) == 1
        tilesets: list[tuple[str, Path]] = []
        for index, (part, _) in enumerate(used, start=1):
            step(f"Converting {part.path.name} ({index}/{len(used)})")
            local_obj = work / f"{part.name}.obj"
            warnings += rewrite_obj(
                part.path,
                local_obj,
                up_axis=options.up_axis,
                positions_to_local=frame.to_local,
                normals_to_local=frame.normals_to_local,
            )
            part_out = output_dir if single else output_dir / "parts" / part.name
            _run_obj2tiles(command, local_obj, part_out, options, on_output, cancel)
            local_obj.unlink()
            tilesets.append((part.name, part_out / "tileset.json"))
    finally:
        shutil.rmtree(work, ignore_errors=True)

    step("Placing the tileset")
    tileset_path = output_dir / "tileset.json"
    if single:
        _place_single(tileset_path, frame)
    else:
        _write_root(tileset_path, frame, [(name, path) for name, path in tilesets])

    return ConversionResult(
        tileset=tileset_path,
        parts=len(used),
        vertices=vertices,
        crs_name=source.crs.name,
        origin_lon_lat_height=frame.origin_lon_lat_height,
        swap_xy=swap_xy,
        warnings=warnings,
    )


def root_transform(frame: LocalFrame) -> list[float]:
    """Column-major tileset root transform: tile frame -> ENU -> ECEF."""
    enu_to_ecef = np.array(frame.tileset_transform()).reshape(4, 4).T
    return [float(v) for v in (enu_to_ecef @ TILE_TO_ENU).T.flatten()]


def obj2tiles_command() -> list[str]:
    """The Obj2Tiles executable from ``OBJ2TILES_PATH``, or ``Obj2Tiles`` on PATH."""
    return [resolve_tool(settings.OBJ2TILES_PATH, ["Obj2Tiles", "obj2tiles"], "OBJ2TILES_PATH")]


def _resolve_crs(user_crs: str | None, input_path: Path, parts: list[ObjPart]) -> CRS:
    if user_crs:
        return parse_crs(user_crs)
    if input_path.is_dir():
        prj_files = sorted(p for p in input_path.rglob("*") if p.suffix.lower() == ".prj")
    else:
        same_stem = input_path.with_suffix(".prj")
        siblings = [p for p in input_path.parent.iterdir() if p.suffix.lower() == ".prj"]
        prj_files = [same_stem] if same_stem.is_file() else siblings
    if not prj_files:
        raise ConversionError(
            "No .prj file found next to the OBJ data, so its CRS is unknown. "
            "Pass the CRS with --crs (an EPSG code or WKT)."
        )
    crss = [(p, read_crs_file(p)) for p in prj_files]
    first_path, first = crss[0]
    for path, crs in crss[1:]:
        if not crs.equals(first, ignore_axis_order=False):
            raise ConversionError(
                f"The .prj files disagree ({first_path.name}: {first.name}, "
                f"{path.name}: {crs.name}). Pass the CRS with --crs."
            )
    return first


def _run_obj2tiles(
    command: list[str],
    obj_path: Path,
    out_dir: Path,
    options: ObjOptions,
    on_output: OutputCallback | None,
    cancel: threading.Event | None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    args = [
        *command,
        "--preset", "standard",
        # Tiles split east-west and north-south only. City data is wide, not tall, so
        # vertical splits only multiply the tile count (8 instead of 4 children per level).
        "--no-zsplit",
        "--local",  # the vertices are already in the local frame; we set the root transform
        "--lods", str(options.lods),
        "--divisions", str(options.divisions),
        *options.obj2tiles_args,
        str(obj_path),
        str(out_dir),
    ]  # fmt: skip
    run_tool(args, tool_name="Obj2Tiles", on_output=on_output, cancel=cancel)
    if not (out_dir / "tileset.json").is_file():
        raise ConversionError(f"Obj2Tiles finished but wrote no tileset.json in {out_dir}.")


def _load(path: Path) -> dict:
    # Obj2Tiles writes null for absent properties ("children": null), which the 3D Tiles
    # schema doesn't allow. Drop them; every tileset we load is written back.
    tileset = _drop_nulls(json.loads(path.read_text(encoding="utf-8")))
    transform = tileset["root"].get("transform", IDENTITY)
    if not np.allclose(transform, IDENTITY):
        raise ConversionError(
            f"{path} already has a root transform. This Obj2Tiles version doesn't behave as "
            "expected in --local mode."
        )
    if "box" not in tileset["root"]["boundingVolume"]:
        raise ConversionError(f"{path} has no box bounding volume at its root.")
    return tileset


def _place_single(path: Path, frame: LocalFrame) -> None:
    tileset = _load(path)
    tileset["root"]["transform"] = root_transform(frame)
    _dump(path, tileset)


def _write_root(path: Path, frame: LocalFrame, parts: list[tuple[str, Path]]) -> None:
    children, corners, errors = [], [], []
    for _name, part_path in parts:
        part = _load(part_path)
        part["root"].pop("transform", None)  # inherits the root's transform
        _dump(part_path, part)
        box = part["root"]["boundingVolume"]["box"]
        error = float(part.get("geometricError", part["root"]["geometricError"]))
        corners.append(_box_corners(box))
        errors.append(error)
        children.append(
            {
                "boundingVolume": {"box": box},
                "geometricError": error,
                "content": {"uri": part_path.relative_to(path.parent).as_posix()},
            }
        )
    all_corners = np.vstack(corners)
    lo, hi = all_corners.min(axis=0), all_corners.max(axis=0)
    centre, half = (lo + hi) / 2, (hi - lo) / 2
    error = max(errors)
    tileset = {
        "asset": {"version": "1.1"},
        "geometricError": error,
        "root": {
            "transform": root_transform(frame),
            "boundingVolume": {
                "box": [
                    *map(float, centre),
                    float(half[0]),
                    0.0,
                    0.0,
                    0.0,
                    float(half[1]),
                    0.0,
                    0.0,
                    0.0,
                    float(half[2]),
                ]  # fmt: skip
            },
            "geometricError": error,
            "refine": "ADD",
            "children": children,
        },
    }
    _dump(path, tileset)


def _box_corners(box: list[float]) -> np.ndarray:
    centre = np.array(box[:3])
    axes = np.array(box[3:12]).reshape(3, 3)
    signs = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)])
    return centre + signs @ axes


def _drop_nulls(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _drop_nulls(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_drop_nulls(v) for v in value]
    return value


def _dump(path: Path, tileset: dict) -> None:
    path.write_text(json.dumps(tileset, separators=(",", ":")), encoding="utf-8")
