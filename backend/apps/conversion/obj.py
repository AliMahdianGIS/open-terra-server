"""Reading and rewriting OBJ files.

Files are streamed in chunks, so their size is limited by disk, not memory. Only vertex
positions (``v``), normals (``vn``) and material library paths (``mtllib``) are rewritten; every
other line (faces, texture coordinates, groups, objects, materials) is copied as it is.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TextIO

import numpy as np

from .runner import ConversionError

UpAxis = Literal["z", "y"]

CHUNK_LINES = 200_000


@dataclass(frozen=True)
class ObjPart:
    path: Path
    name: str  # unique and safe for use as a folder name / URI


def find_obj_parts(input_path: Path) -> list[ObjPart]:
    """One part per ``.obj`` file: the file itself, or every ``.obj`` below a folder."""
    if input_path.is_file():
        if input_path.suffix.lower() != ".obj":
            raise ConversionError(f"{input_path.name} is not an OBJ file.")
        files = [input_path]
        base = input_path.parent
    elif input_path.is_dir():
        files = sorted(
            (p for p in input_path.rglob("*") if p.is_file() and p.suffix.lower() == ".obj"),
            key=lambda p: p.relative_to(input_path).as_posix().lower(),
        )
        base = input_path
        if not files:
            raise ConversionError(f"No .obj files found in {input_path}.")
    else:
        raise ConversionError(f"{input_path} does not exist.")

    parts, used = [], set()
    for index, path in enumerate(files):
        stem = path.relative_to(base).with_suffix("").as_posix()
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or "part"
        name = safe if safe.lower() not in used else f"{safe}-{index}"
        used.add(name.lower())
        parts.append(ObjPart(path=path, name=name))
    return parts


def _vertex_lines(handle: TextIO) -> Iterator[list[str]]:
    batch: list[str] = []
    for line in handle:
        if line.startswith(("v ", "v\t")):
            batch.append(line)
            if len(batch) >= CHUNK_LINES:
                yield batch
                batch = []
    if batch:
        yield batch


def _parse_xyz(lines: list[str], source: Path) -> np.ndarray:
    try:
        return np.array([line.split()[1:4] for line in lines], dtype=np.float64)
    except ValueError as exc:
        raise ConversionError(f"{source.name} has a malformed vertex line: {exc}") from exc


def to_source_axes(xyz: np.ndarray, up_axis: UpAxis) -> np.ndarray:
    """OBJ ``x y z`` to source ``(a, b, height)``. For Y-up files, ``-z`` is the second
    horizontal axis (the usual way exporters turn Z-up data into Y-up)."""
    if up_axis == "z":
        return xyz
    return np.column_stack([xyz[:, 0], -xyz[:, 2], xyz[:, 1]])


def scan_bounds(path: Path, up_axis: UpAxis) -> tuple[np.ndarray, np.ndarray, int]:
    """Min and max of the vertex positions in source axes, and the vertex count."""
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    count = 0
    with path.open(encoding="utf-8", errors="surrogateescape", newline="") as handle:
        for batch in _vertex_lines(handle):
            pts = to_source_axes(_parse_xyz(batch, path), up_axis)
            lo = np.minimum(lo, pts.min(axis=0))
            hi = np.maximum(hi, pts.max(axis=0))
            count += len(pts)
    if count and not (np.all(np.isfinite(lo)) and np.all(np.isfinite(hi))):
        raise ConversionError(f"{path.name} has vertices that are not finite numbers.")
    return lo, hi, count


PointMap = Callable[[np.ndarray], np.ndarray]


def rewrite_obj(
    source: Path,
    target: Path,
    *,
    up_axis: UpAxis,
    positions_to_local: PointMap,
    normals_to_local: PointMap,
) -> list[str]:
    """Write ``source`` to ``target`` with positions and normals in the local ENU frame.

    The output is Z-up ``(east, north, up)``, because Obj2Tiles splits tiles along the OBJ's
    X and Y axes (and Z only with ``--zsplit``). Obj2Tiles copies these values into glTF
    unchanged, so the tileset root transform has to undo the glTF Y-up convention (see
    ``obj_to_3dtiles.root_transform``).
    ``mtllib`` paths become absolute so textures still resolve from the source folder.
    Returns warnings (for example, missing material libraries).
    """
    warnings: list[str] = []
    with (
        source.open(encoding="utf-8", errors="surrogateescape", newline="") as src,
        target.open("w", encoding="utf-8", errors="surrogateescape", newline="\n") as out,
    ):
        chunk: list[str] = []
        for line in src:
            chunk.append(line)
            if len(chunk) >= CHUNK_LINES:
                _write_chunk(chunk, out, source, up_axis, positions_to_local, normals_to_local,
                             warnings)  # fmt: skip
                chunk = []
        if chunk:
            _write_chunk(chunk, out, source, up_axis, positions_to_local, normals_to_local,
                         warnings)  # fmt: skip
    return warnings


def _write_chunk(
    lines: list[str],
    out: TextIO,
    source: Path,
    up_axis: UpAxis,
    positions_to_local: PointMap,
    normals_to_local: PointMap,
    warnings: list[str],
) -> None:
    v_idx = [i for i, line in enumerate(lines) if line.startswith(("v ", "v\t"))]
    vn_idx = [i for i, line in enumerate(lines) if line.startswith(("vn ", "vn\t"))]
    replaced: dict[int, str] = {}

    if v_idx:
        tokens = [lines[i].split() for i in v_idx]
        xyz = _parse_xyz([lines[i] for i in v_idx], source)
        local = positions_to_local(to_source_axes(xyz, up_axis))
        for i, toks, (e, n, u) in zip(v_idx, tokens, local, strict=True):
            extra = " " + " ".join(toks[4:]) if len(toks) > 4 else ""  # w or vertex colour
            replaced[i] = f"v {e:.4f} {n:.4f} {u:.4f}{extra}\n"
    if vn_idx:
        xyz = _parse_xyz([lines[i] for i in vn_idx], source)
        local = normals_to_local(to_source_axes(xyz, up_axis))
        for i, (e, n, u) in zip(vn_idx, local, strict=True):
            replaced[i] = f"vn {e:.6f} {n:.6f} {u:.6f}\n"

    for i, line in enumerate(lines):
        if i in replaced:
            out.write(replaced[i])
        elif line.startswith(("mtllib ", "mtllib\t")):
            out.write(_absolute_mtllib(line, source, warnings))
        else:
            out.write(line)


def _absolute_mtllib(line: str, source: Path, warnings: list[str]) -> str:
    rest = line[len("mtllib") :].strip()
    whole = source.parent / rest
    # The spec separates several libraries with spaces, but many exporters write one file
    # name that contains spaces. Prefer the whole name when such a file exists.
    names = [rest] if whole.is_file() else rest.split()
    result = []
    for name in names:
        path = (source.parent / name).resolve()
        if not path.is_file():
            warnings.append(f"{source.name}: material library {name!r} not found.")
        result.append(f"mtllib {path}\n")
    return "".join(result)
