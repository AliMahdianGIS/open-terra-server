"""Coordinate systems and the local frame that converted tilesets are placed in.

Source vertices are reprojected with PROJ (through pyproj) to ECEF and then expressed in an
east-north-up (ENU) frame centred on the dataset. The tileset root gets the exact ENU-to-ECEF
matrix, so placement doesn't rely on a flat-earth approximation: every vertex is reprojected
individually, including Earth curvature, grid convergence and scale factor.

Nothing here assumes a particular CRS, unit or axis order: units come from the CRS, axis order
comes from the CRS or the user. Heights are used as given (plus an optional offset): they are
treated as ellipsoidal heights on the source CRS's datum, so PROJ's datum shift applies but no
geoid model. Vertical datum conversion comes later (implementation plan P4.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError

from .runner import ConversionError

AxisOrder = Literal["auto", "xy", "crs"]

ECEF = CRS.from_epsg(4978)
WGS84_3D = CRS.from_epsg(4979)
WGS84_LONLAT = CRS.from_epsg(4326)


def parse_crs(value: str) -> CRS:
    """Parse a CRS given by the user: ``EPSG:xxxx``, a bare EPSG code, WKT (OGC, ESRI or WKT2),
    PROJJSON, or a path to a file holding one of those (such as a ``.prj``)."""
    text = value.strip()
    if text.isdigit():
        text = f"EPSG:{text}"
    path = Path(text)
    if len(text) < 1024 and "\n" not in text and path.is_file():
        return read_crs_file(path)
    try:
        return CRS.from_user_input(text)
    except CRSError as exc:
        raise ConversionError(f"Could not understand the CRS {value!r}: {exc}") from exc


def read_crs_file(path: Path) -> CRS:
    """Read a ``.prj`` (or similar) file holding ESRI WKT, OGC WKT, WKT2 or PROJJSON."""
    try:
        text = path.read_text(encoding="utf-8-sig").strip()
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1").strip()
    if not text:
        raise ConversionError(f"{path.name} is empty.")
    try:
        return CRS.from_user_input(text)
    except CRSError as exc:
        raise ConversionError(f"{path.name} does not hold a CRS PROJ understands: {exc}") from exc


@dataclass(frozen=True)
class SourceCRS:
    """The CRS of the source vertices, split into what the transformation needs."""

    crs: CRS
    horizontal: CRS
    height_factor: float  # metres per source height unit

    @classmethod
    def from_crs(cls, crs: CRS, height_unit_factor: float | None = None) -> SourceCRS:
        if crs.is_compound:
            horizontal, vertical = crs.sub_crs_list[0], crs.sub_crs_list[1]
            factor = vertical.axis_info[0].unit_conversion_factor
        elif len(crs.axis_info) == 3:
            horizontal = crs.to_2d()
            factor = crs.axis_info[2].unit_conversion_factor
        else:
            horizontal = crs
            first = crs.axis_info[0] if crs.axis_info else None
            # A 2D CRS says nothing about heights. Assume they share the horizontal linear unit
            # (metres, US survey feet, ...); for geographic CRSs assume metres.
            linear = first is not None and first.unit_name not in ("degree", "radian", "grad")
            factor = first.unit_conversion_factor if linear and first else 1.0
        if not (horizontal.is_projected or horizontal.is_geographic):
            raise ConversionError(
                f"{crs.name} is not a projected or geographic CRS, so it can't be placed on "
                "the globe."
            )
        if height_unit_factor is not None:
            factor = height_unit_factor
        return cls(crs=crs, horizontal=horizontal, height_factor=factor)

    @property
    def first_axis_is_northing(self) -> bool:
        axis = self.horizontal.axis_info[0] if self.horizontal.axis_info else None
        return axis is not None and axis.direction.lower() in ("north", "south")


class LocalFrame:
    """Maps source coordinates to a local east-north-up frame in metres around ``origin``.

    Source points are ``(a, b, h)``: the first two horizontal coordinates as stored in the file
    and the height. ``swap_xy`` says the file stores northing (or latitude) first.
    """

    def __init__(
        self,
        source: SourceCRS,
        origin: tuple[float, float, float],
        *,
        swap_xy: bool,
        height_offset: float = 0.0,
    ) -> None:
        self.source = source
        self.swap_xy = swap_xy
        self.height_offset = height_offset
        self._to_ecef = Transformer.from_crs(source.horizontal.to_3d(), ECEF, always_xy=True)
        origin_ecef = self._source_to_ecef(np.array([origin], dtype=np.float64))[0]
        if not np.all(np.isfinite(origin_ecef)):
            raise ConversionError(
                f"The data centre {origin} can't be transformed from {source.crs.name}. "
                "Check the CRS and the axis order."
            )
        lon, lat, height = Transformer.from_crs(ECEF, WGS84_3D, always_xy=True).transform(
            *origin_ecef
        )
        self.origin_ecef = origin_ecef
        self.origin_lon_lat_height = (float(lon), float(lat), float(height))
        self.rotation = enu_rotation(lon, lat)  # rows: east, north, up (in ECEF)
        self._normal_matrix = self._compute_normal_matrix(np.array(origin, dtype=np.float64))

    def _source_to_ecef(self, points: np.ndarray) -> np.ndarray:
        a, b, h = points[:, 0], points[:, 1], points[:, 2]
        east, north = (b, a) if self.swap_xy else (a, b)
        heights = h * self.source.height_factor + self.height_offset
        x, y, z = self._to_ecef.transform(east, north, heights)
        return np.column_stack([np.asarray(x), np.asarray(y), np.asarray(z)])

    def to_local(self, points: np.ndarray) -> np.ndarray:
        """Source ``(a, b, h)`` points (N x 3) to local ENU metres (N x 3)."""
        ecef = self._source_to_ecef(points)
        local = (ecef - self.origin_ecef) @ self.rotation.T
        if not np.all(np.isfinite(local)):
            raise ConversionError(
                f"Some vertices can't be transformed from {self.source.crs.name}. "
                "Check the CRS and the axis order."
            )
        return local

    def normals_to_local(self, normals: np.ndarray) -> np.ndarray:
        """Source normals (N x 3) to unit normals in the local frame."""
        out = normals @ self._normal_matrix.T
        length = np.linalg.norm(out, axis=1, keepdims=True)
        return np.divide(out, length, out=np.zeros_like(out), where=length > 0)

    def _compute_normal_matrix(self, origin: np.ndarray) -> np.ndarray:
        # Jacobian of source -> local at the origin, by central differences. It carries the
        # units, the axis order and the grid convergence; normals use its inverse transpose.
        step = np.array([1e-6, 1e-6, 1.0]) if self.source.horizontal.is_geographic else 1.0
        offsets = np.diag(np.broadcast_to(step, (3,)).astype(np.float64))
        plus = self.to_local(origin + offsets)
        minus = self.to_local(origin - offsets)
        jacobian = ((plus - minus) / (2 * np.diag(offsets))[:, None]).T
        return np.linalg.inv(jacobian).T

    def tileset_transform(self) -> list[float]:
        """Column-major 4x4 matrix from the local frame to ECEF, for ``tileset.json``."""
        east, north, up = self.rotation
        o = self.origin_ecef
        return [
            *map(float, east), 0.0,
            *map(float, north), 0.0,
            *map(float, up), 0.0,
            float(o[0]), float(o[1]), float(o[2]), 1.0,
        ]  # fmt: skip


def enu_rotation(lon_deg: float, lat_deg: float) -> np.ndarray:
    """Rows are the east, north and up unit vectors in ECEF at a geodetic position."""
    lon, lat = np.radians(lon_deg), np.radians(lat_deg)
    sl, cl, sp, cp = np.sin(lon), np.cos(lon), np.sin(lat), np.cos(lat)
    return np.array(
        [
            [-sl, cl, 0.0],
            [-sp * cl, -sp * sl, cp],
            [cp * cl, cp * sl, sp],
        ]
    )


def choose_axis_order(
    source: SourceCRS, mode: AxisOrder, bbox_min: np.ndarray, bbox_max: np.ndarray
) -> tuple[bool, str | None]:
    """Decide whether the file stores northing/latitude first. Returns ``(swap_xy, warning)``.

    ``xy``: easting/longitude first (the usual order in mesh files). ``crs``: the axis order the
    CRS defines. ``auto``: when the CRS defines northing first, try both orders and keep the
    one that puts the data inside the CRS's area of use.
    """
    if mode == "xy":
        return False, None
    if mode == "crs" or not source.first_axis_is_northing:
        return source.first_axis_is_northing, None

    area = source.crs.area_of_use or source.horizontal.area_of_use
    if area is None:
        return False, (
            f"{source.crs.name} defines northing first but has no area of use to check "
            "against; assuming the file stores easting first. Use --axis-order crs if not."
        )
    centre = (bbox_min + bbox_max) / 2
    to_lonlat = Transformer.from_crs(source.horizontal, WGS84_LONLAT, always_xy=True)
    hits = []
    for swap in (False, True):
        east, north = (centre[1], centre[0]) if swap else (centre[0], centre[1])
        lon, lat = to_lonlat.transform(east, north)
        if _inside(area, lon, lat):
            hits.append(swap)
    if len(hits) == 1:
        return hits[0], None
    return False, (
        f"Could not tell the axis order from the data's position in {source.crs.name}; "
        "assuming easting first. Use --axis-order crs if the file stores northing first."
    )


def check_area_of_use(source: SourceCRS, frame: LocalFrame) -> str | None:
    """Warn when the data centre is outside the CRS's area of use (often a wrong CRS)."""
    area = source.crs.area_of_use or source.horizontal.area_of_use
    lon, lat, _ = frame.origin_lon_lat_height
    if area is None or _inside(area, lon, lat, margin=1.0):
        return None
    return (
        f"The data centre ({lat:.5f}, {lon:.5f}) is outside the area of use of "
        f"{source.crs.name} ({area.name}). Check that the CRS is right."
    )


def _inside(area: object, lon: float, lat: float, margin: float = 0.0) -> bool:
    if not (np.isfinite(lon) and np.isfinite(lat)):
        return False
    west, south, east, north = (
        area.west - margin,  # type: ignore[attr-defined]
        area.south - margin,  # type: ignore[attr-defined]
        area.east + margin,  # type: ignore[attr-defined]
        area.north + margin,  # type: ignore[attr-defined]
    )
    if not south <= lat <= north:
        return False
    if west <= east:
        return west <= lon <= east
    return lon >= west or lon <= east  # area crosses the antimeridian
