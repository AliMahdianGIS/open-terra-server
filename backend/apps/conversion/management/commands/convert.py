"""``manage.py convert <input> <output>``: convert a 3D dataset to a 3D Tiles 1.1 tileset."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.conversion.obj_to_3dtiles import ObjOptions, convert_obj
from apps.conversion.runner import ConversionError


class Command(BaseCommand):
    help = (
        "Convert a 3D dataset to a 3D Tiles 1.1 tileset with levels of detail. "
        "Supported input so far: an OBJ file, or a folder whose .obj files (in any "
        "subfolder) are parts of one dataset."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("input", type=Path, help="OBJ file or folder of OBJ files.")
        parser.add_argument("output", type=Path, help="Output folder (must be empty or new).")
        parser.add_argument(
            "--crs",
            help="Source CRS: EPSG code (e.g. EPSG:25833), WKT, PROJJSON or a .prj path. "
            "Default: read the .prj file(s) next to the data.",
        )
        parser.add_argument(
            "--axis-order",
            choices=["auto", "xy", "crs"],
            default="auto",
            help="xy: the file stores easting/longitude first. crs: the order the CRS "
            "defines. auto (default): xy unless the CRS defines northing first, in which case "
            "the order that puts the data inside the CRS's area of use.",
        )
        parser.add_argument(
            "--up-axis",
            choices=["z", "y"],
            default="z",
            help="Which OBJ axis holds heights (default z).",
        )
        parser.add_argument(
            "--height-offset", type=float, default=0.0, help="Metres added to every height."
        )
        parser.add_argument(
            "--height-unit-factor",
            type=float,
            help="Metres per height unit. Default: the CRS's vertical unit, or its horizontal "
            "linear unit for a 2D CRS.",
        )
        parser.add_argument("--lods", type=int, default=3, help="Levels of detail (default 3).")
        parser.add_argument(
            "--divisions",
            type=int,
            default=2,
            help="Spatial split depth of the coarsest LOD (default 2).",
        )
        parser.add_argument(
            "--obj2tiles-arg",
            action="append",
            default=[],
            dest="obj2tiles_args",
            metavar="ARG",
            help="Extra argument for Obj2Tiles, repeatable (e.g. --obj2tiles-arg=--unlit).",
        )

    def handle(self, *args: Any, **opts: Any) -> None:
        verbosity = opts["verbosity"]
        options = ObjOptions(
            crs=opts["crs"],
            axis_order=opts["axis_order"],
            up_axis=opts["up_axis"],
            height_offset=opts["height_offset"],
            height_unit_factor=opts["height_unit_factor"],
            lods=opts["lods"],
            divisions=opts["divisions"],
            obj2tiles_args=opts["obj2tiles_args"],
        )
        try:
            result = convert_obj(
                opts["input"],
                opts["output"],
                options,
                on_step=lambda msg: self.stdout.write(f"=> {msg}") if verbosity else None,
                on_output=(lambda line: self.stdout.write(f"   {line}")) if verbosity > 1 else None,
            )
        except ConversionError as exc:
            raise CommandError(str(exc)) from exc

        for warning in result.warnings:
            self.stderr.write(self.style.WARNING(f"Warning: {warning}"))
        lon, lat, height = result.origin_lon_lat_height
        order = "northing first" if result.swap_xy else "easting first"
        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {result.tileset}\n"
                f"  {result.parts} OBJ file(s), {result.vertices:,} vertices\n"
                f"  CRS: {result.crs_name} ({order})\n"
                f"  Centre: lat {lat:.6f}, lon {lon:.6f}, "
                f"height {height:.2f} m (used as ellipsoidal)"
            )
        )
