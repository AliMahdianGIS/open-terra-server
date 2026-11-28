"""Stand-in for Obj2Tiles in tests. Called as ``python fake_obj2tiles.py [options] input output``.

It behaves like ``Obj2Tiles --local``: copies the input OBJ (so tests can inspect what the
converter received), records its arguments, and writes a tileset with an identity transform
and a box around the vertices in the tile frame. ``FAKE_OBJ2TILES_FAIL=1`` makes it fail.
"""

import json
import os
import shutil
import sys
from pathlib import Path


def main() -> int:
    args = sys.argv[1:]
    obj, out = Path(args[-2]), Path(args[-1])
    print(" => Decimation stage")
    if os.environ.get("FAKE_OBJ2TILES_FAIL"):
        print(" !> Error: could not read the mesh", flush=True)
        return 3
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy(obj, out / "received.obj")
    (out / "args.json").write_text(json.dumps(args), encoding="utf-8")

    pts = [
        [float(v) for v in line.split()[1:4]]
        for line in obj.read_text(encoding="utf-8").splitlines()
        if line.startswith("v ")
    ]
    tile = [(x, -z, y) for x, y, z in pts]
    lo = [min(p[i] for p in tile) for i in range(3)]
    hi = [max(p[i] for p in tile) for i in range(3)]
    c = [(lo[i] + hi[i]) / 2 for i in range(3)]
    h = [(hi[i] - lo[i]) / 2 for i in range(3)]
    tileset = {
        "asset": {"version": "1.1"},
        "geometricError": 50.0,
        "root": {
            "transform": [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0],
            "boundingVolume": {"box": [*c, h[0], 0, 0, 0, h[1], 0, 0, 0, h[2]]},
            "geometricError": 50.0,
            "refine": "REPLACE",
            "content": {"uri": "root.glb"},
        },
    }
    (out / "tileset.json").write_text(json.dumps(tileset), encoding="utf-8")
    (out / "root.glb").write_bytes(b"glTF")
    print(" => Pipeline completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
