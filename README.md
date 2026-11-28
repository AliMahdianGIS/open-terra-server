# Open Terra Server

An open-source, self-hostable platform for uploading, converting, publishing and sharing city-scale 3D layers (OBJ, glTF, 3D Tiles, SLPK), served as 3D Tiles and I3S.

- What v1 covers: [project-scope.md](project-scope.md)
- How it gets built, phase by phase: [implementation-plan.md](implementation-plan.md)

> **Status:** early. There is a Django API with a health check and a map-config endpoint, a React + CesiumJS app that shows a globe, and a `convert` command that turns OBJ data into 3D Tiles. Uploads, background processing and tile serving are not built yet.

## Repository layout

| Folder | Contents |
|---|---|
| `backend/` | Django + Django REST Framework API |
| `frontend/` | React + Vite + TypeScript app with a CesiumJS map |

## Prerequisites

- [uv](https://docs.astral.sh/uv/), the Python package manager. Install it with `winget install astral-sh.uv` on Windows, or see the uv docs for other systems. uv installs Python 3.12 or newer itself if it is missing.
- Node.js 18 or newer, with npm

## Backend setup

```sh
cd backend
uv sync                              # creates .venv and installs all packages, dev tools included
uv run python manage.py migrate
uv run python manage.py runserver
```

`uv run` runs a command inside the project's `.venv`, so you don't need to activate it.

### Managing packages

Packages are listed in `backend/pyproject.toml`, and the exact versions are in `backend/uv.lock`. Commit both files.

| Task | Command |
|---|---|
| Add a production package | `uv add <package>` |
| Add a development-only package (tests, linting) | `uv add --dev <package>` |
| Remove a package | `uv remove <package>` (add `--dev` for dev packages) |
| Install for development | `uv sync` |
| Install for production | `uv sync --no-dev --locked` |

`--locked` stops with an error if `uv.lock` doesn't match `pyproject.toml`, so production gets the versions you tested with.

The API runs at http://localhost:8000:

- `GET /api/health/` is the health check.
- `GET /api/map-config/` returns the settings the map needs at startup.
- `/api/docs/` is the Swagger UI, and `/api/schema/` is the OpenAPI schema.

### Configuration

Settings are read from environment variables, or from a `backend/.env` file. To create one, copy `backend/.env.example` to `backend/.env`.

| Variable | Default | Purpose |
|---|---|---|
| `DEBUG` | `false` | Django debug mode |
| `SECRET_KEY` | insecure dev key | Set a real value outside development |
| `DATABASE_URL` | SQLite file in `backend/` | e.g. `postgis://user:pass@localhost:5432/openterra` |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated |
| `CESIUM_ION_TOKEN` | empty | Optional. Enables Cesium world terrain and imagery |
| `OBJ2TILES_PATH` | empty | Path to the Obj2Tiles executable. Empty: look for `Obj2Tiles` on `PATH` |

You can get a free Cesium Ion token at https://ion.cesium.com/. Without a token, the map uses OpenStreetMap imagery and no terrain.

## Converting OBJ to 3D Tiles

The `convert` command turns an OBJ dataset into a 3D Tiles 1.1 tileset with levels of detail, placed on the globe. It uses [Obj2Tiles](https://github.com/OpenDroneMap/Obj2Tiles) (AGPL-3.0) for decimation, spatial splitting and tiling.

### Install Obj2Tiles

Download the release zip for your system from the [Obj2Tiles releases](https://github.com/OpenDroneMap/Obj2Tiles/releases) (tested with v1.10.4). The build is self-contained, so .NET doesn't need to be installed.

```sh
# Ubuntu (x64; use Obj2Tiles-LinuxArm64.zip on ARM)
curl -LO https://github.com/OpenDroneMap/Obj2Tiles/releases/download/v1.10.4/Obj2Tiles-Linux64.zip
unzip Obj2Tiles-Linux64.zip -d ~/.local/share/obj2tiles
chmod +x ~/.local/share/obj2tiles/Obj2Tiles
echo "OBJ2TILES_PATH=$HOME/.local/share/obj2tiles/Obj2Tiles" >> backend/.env
```

On Windows, unzip `Obj2Tiles-Win64.zip` and set `OBJ2TILES_PATH` to the full path of `Obj2Tiles.exe`. Instead of setting `OBJ2TILES_PATH`, you can put the folder on `PATH`.

### Run a conversion

```sh
cd backend
uv run python manage.py convert path/to/model.obj path/to/output
uv run python manage.py convert path/to/dataset-folder path/to/output --crs EPSG:25833
```

- **Input** is one `.obj` file, or a folder. Every `.obj` file anywhere in the folder is treated as part of one dataset, and the output gets a root `tileset.json` that references each part. `.mtl` files and textures are read from where the OBJ files point to them. If a folder holds alternative versions of the same area (for example one OBJ per level of detail), convert each file on its own.
- **CRS:** by default it is read from the `.prj` file(s) next to the data (ESRI WKT, OGC WKT, WKT2 or PROJJSON). Pass `--crs` with an EPSG code, WKT or a `.prj` path to set it yourself. Units (metres, US survey feet, degrees and so on) come from the CRS.
- **Axis order:** `--axis-order auto` (the default) assumes easting/longitude first. For a CRS that defines northing first, it picks the order that puts the data inside the CRS's area of use. Use `xy` or `crs` to force an order. Use `--up-axis y` for files exported Y-up.
- **Heights** are used as given, as ellipsoidal heights on the CRS's datum. `--height-offset` adds metres to them. Geoid and vertical datum conversion is not done yet.
- **Levels of detail:** `--lods` (default 3) and `--divisions` (default 2). Tiles split east-west and north-south, not vertically. The coarsest LOD has up to 4^divisions tiles, and each finer LOD has four times as many. Other Obj2Tiles options can be passed with `--obj2tiles-arg`, for example `--obj2tiles-arg=--unlit`.
- **Output:** the output folder must be empty or new. Use `-v 2` to see Obj2Tiles' own output.

Every vertex is reprojected with PROJ into a local east-north-up frame around the centre of the dataset, and the tileset root holds the exact transform from that frame to Earth-centred coordinates. This keeps vertex precision at a fraction of a millimetre, and placement doesn't depend on a flat-earth approximation.

## Frontend setup

```sh
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

While the dev server is running, it forwards `/api` requests to the backend at `localhost:8000`. The map also works when the backend is not running: it uses OpenStreetMap imagery and logs a warning in the browser console.

Other commands:

- `npm run build` creates a type-checked production build in `frontend/dist/`.
- `npm run preview` serves that build locally.

## Running the tests

```sh
cd backend
uv run pytest
uv run ruff check .
```

The conversion tests run against a stand-in for Obj2Tiles, so they need no external tools. When Obj2Tiles is installed (`OBJ2TILES_PATH` or `PATH`), extra end-to-end tests run the real converter. Without it, they are skipped.
