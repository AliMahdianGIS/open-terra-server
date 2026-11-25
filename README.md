# Open Terra Server

An open-source, self-hostable platform for uploading, converting, publishing and sharing city-scale 3D layers (OBJ, glTF, 3D Tiles, SLPK), served as 3D Tiles and I3S.

- What v1 covers: [project-scope.md](project-scope.md)
- How it gets built, phase by phase: [implementation-plan.md](implementation-plan.md)

> **Status:** early skeleton. There is a Django API with a health check and a map-config endpoint, and a React + CesiumJS app that shows a globe. Uploads, processing and tile serving are not built yet.

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

You can get a free Cesium Ion token at https://ion.cesium.com/. Without a token, the map uses OpenStreetMap imagery and no terrain.

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
