"""Synthetic test data: boxes placed in many CRSs around the world.

No dataset is the target. Each entry exercises a different property: hemisphere, units,
axis order, compound CRS, geographic coordinates, antimeridian, high latitude, south-oriented
axes.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from pyproj import CRS, Transformer


@dataclass(frozen=True)
class Site:
    id: str
    epsg: int
    lon: float
    lat: float
    height: float  # in the CRS's height unit
    span: float  # box size in the CRS's horizontal unit
    stored_northing_first: bool = False  # the file stores (northing, easting)

    @property
    def crs(self) -> CRS:
        return CRS.from_epsg(self.epsg)

    def centre(self) -> tuple[float, float]:
        """The site centre in file order (a, b)."""
        crs = self.crs
        horizontal = crs.sub_crs_list[0] if crs.is_compound else crs
        east, north = Transformer.from_crs(4326, horizontal, always_xy=True).transform(
            self.lon, self.lat
        )
        return (north, east) if self.stored_northing_first else (east, north)

    def box_corners(self) -> np.ndarray:
        a, b = self.centre()
        s = self.span / 2
        h = self.height
        tall = 30.0 if self.crs.is_geographic else self.span / 4
        corners = itertools.product((a - s, a + s), (b - s, b + s), (h, h + tall))
        return np.array(list(corners), dtype=np.float64)


SITES = [
    Site("berlin-utm33n", 32633, 13.40, 52.52, 40.0, 200.0),
    Site("melbourne-mga55-gda2020", 7855, 144.96, -37.81, 10.0, 200.0),
    Site("long-island-stateplane-ftus", 2263, -73.99, 40.75, 30.0, 600.0),
    Site("helsinki-gk25-northing-first", 3879, 24.94, 60.17, 20.0, 200.0, True),
    Site("helsinki-gk25-easting-first", 3879, 24.94, 60.17, 20.0, 200.0, False),
    Site("amsterdam-rd-nap-compound", 7415, 4.90, 52.37, 2.0, 200.0),
    Site("tokyo-jgd2011-geographic", 6697, 139.77, 35.68, 40.0, 0.002, True),
    Site("sao-paulo-utm23s", 31983, -46.63, -23.55, 760.0, 200.0),
    Site("cape-town-lo19-west-south", 2048, 18.42, -33.92, 15.0, 200.0),
    Site("fiji-map-grid-antimeridian", 3460, 178.44, -18.14, 5.0, 200.0),
    Site("zurich-lv95", 2056, 8.54, 47.37, 410.0, 200.0),
]

FACES = [(1, 2, 4, 3), (5, 7, 8, 6), (1, 5, 6, 2), (3, 4, 8, 7), (1, 3, 7, 5), (2, 6, 8, 4)]


def write_box_obj(
    path: Path,
    corners: np.ndarray,
    *,
    up_axis: str = "z",
    mtl_name: str | None = "box.mtl",
    with_normals: bool = True,
) -> None:
    """A textured box with one normal per face, ``corners`` in source axes (a, b, height)."""
    pts = (
        corners
        if up_axis == "z"
        else np.column_stack([corners[:, 0], corners[:, 2], -corners[:, 1]])
    )
    lines = []
    if mtl_name:
        lines.append(f"mtllib {mtl_name}")
    lines += ["o building_ü", "g walls"]
    lines += [f"v {x:.6f} {y:.6f} {z:.6f}" for x, y, z in pts]
    lines += ["vt 0 0", "vt 1 0", "vt 1 1", "vt 0 1"]
    if with_normals:
        up = (0.0, 0.0, 1.0) if up_axis == "z" else (0.0, 1.0, 0.0)
        lines.append("vn {:.1f} {:.1f} {:.1f}".format(*up))
    if mtl_name:
        lines.append("usemtl brick")
    for q in FACES:
        n = "/1" if with_normals else ""
        lines.append(f"f {q[0]}/1{n} {q[1]}/2{n} {q[2]}/3{n}")
        lines.append(f"f {q[0]}/1{n} {q[2]}/3{n} {q[3]}/4{n}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if mtl_name:
        (path.parent / mtl_name).write_text(
            "newmtl brick\nKd 0.8 0.4 0.3\nmap_Kd textures/brick.png\n", encoding="utf-8"
        )
        (path.parent / "textures").mkdir(exist_ok=True)
        (path.parent / "textures" / "brick.png").write_bytes(b"\x89PNG\r\n\x1a\n")


def write_prj(path: Path, crs: CRS, flavour: str = "WKT1_ESRI") -> None:
    text = crs.to_json() if flavour == "PROJJSON" else crs.to_wkt(flavour)
    path.write_text(text, encoding="utf-8")


def read_obj_vertices(path: Path) -> np.ndarray:
    rows = [
        line.split()[1:4]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("v ")
    ]
    return np.array(rows, dtype=np.float64)


def obj_to_tile_frame(xyz: np.ndarray) -> np.ndarray:
    """Obj2Tiles copies OBJ xyz into glTF (Y-up); 3D Tiles turns that into (x, -z, y)."""
    return np.column_stack([xyz[:, 0], -xyz[:, 2], xyz[:, 1]])


def apply_transform(matrix: list[float], pts: np.ndarray) -> np.ndarray:
    m = np.array(matrix, dtype=np.float64).reshape(4, 4).T
    return (np.column_stack([pts, np.ones(len(pts))]) @ m.T)[:, :3]


def expected_ecef(site: Site, corners: np.ndarray, height_factor: float) -> np.ndarray:
    """ECEF of the source points by a direct PROJ transformation (heights as ellipsoidal)."""
    crs = site.crs
    horizontal = crs.sub_crs_list[0] if crs.is_compound else (crs.to_2d() if len(
        crs.axis_info) == 3 else crs)  # fmt: skip
    a, b, h = corners.T
    east, north = (b, a) if site.stored_northing_first else (a, b)
    tr = Transformer.from_crs(horizontal.to_3d(), 4978, always_xy=True)
    return np.column_stack(tr.transform(east, north, h * height_factor))
