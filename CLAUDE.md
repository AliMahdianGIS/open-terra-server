# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

Open Terra Server is a self-hostable platform for publishing city-scale 3D layers (OBJ, glTF, 3D Tiles, SLPK) as 3D Tiles and I3S. Read these before planning work:

- [project-scope.md](project-scope.md): what v1 includes and excludes.
- [implementation-plan.md](implementation-plan.md): phases and tasks. Task IDs like `P1.7` are used in commits and issues.

Current state: early Phase 1 (convert formats to 3D Tiles). There is a Django API with `/api/health/` and `/api/map-config/`, a React + CesiumJS globe, and `apps.conversion` with a `convert` management command for OBJ → 3D Tiles (Obj2Tiles, path from `OBJ2TILES_PATH`). Nothing else is built yet.

## Scope discipline

- Build only what is asked. Don't add plan items that weren't requested, such as Docker, Celery, auth or PostGIS models.
- Follow the stack decisions in the plan's "Guiding decisions" table. Don't swap libraries without asking.

## Worldwide data, never one sample

The system must work for city data from anywhere. Never hard-code a CRS, units, axis order, vertical datum, file layout or attribute structure. Never design, default or test around one dataset (for example New York City). Tests that touch geodata must cover a varied set of datasets.

## Layout

| Path | Contents |
|---|---|
| `backend/` | Django + DRF API. `config/` holds settings and URLs; all apps live in `apps/` (e.g. `apps/core/`, `apps/conversion/`), registered as `apps.<name>` |
| `frontend/` | React + Vite + TypeScript app with CesiumJS |
| `docs/` | Project docs, such as the reference test corpus ([test-corpus.md](docs/test-corpus.md)) |

Planned folders that don't exist yet: `tools/geometry/` (Node.js glTF toolkit) and `docker/`.

## Commands

The backend uses **uv only**. Don't add `requirements.txt` files or use bare `pip`.

```sh
# backend (run in backend/)
uv sync                            # install, dev tools included
uv add <pkg> / uv add --dev <pkg>  # add a dependency; updates pyproject.toml and uv.lock
uv run python manage.py runserver  # serves http://127.0.0.1:8000
uv run pytest                      # tests
uv run ruff check .                # lint
uv run ruff format .               # format

# frontend (run in frontend/)
npm install
npm run dev                        # serves http://127.0.0.1:5173 and forwards /api to :8000
npm run build                      # type check + production build
```

Before reporting backend work as done, run `uv run pytest` and `uv run ruff check .`. Before reporting frontend work as done, run `npm run build`.

## Conventions

- **Backend settings** come from environment variables via django-environ (`backend/.env`; see `.env.example`). Never hard-code secrets or tokens.
- **Database:** SQLite is the default until PostGIS arrives in P2.1. Don't write SQLite-specific code.
- **API:** DRF views get `extend_schema` annotations so the OpenAPI schema at `/api/schema/` stays accurate. The frontend will generate its API types from that schema.
- **Python:** target 3.12+, type hints on functions, Ruff rules from `pyproject.toml` (line length 100).
- **Frontend:** strict TypeScript, function components and hooks. Cesium's static files are copied by `vite-plugin-static-copy` and found through `CESIUM_BASE_URL`; keep that setup when touching `vite.config.ts`.
- **Map without a token:** the map must keep working with no Cesium Ion token, using OpenStreetMap imagery and no terrain.

## Gotchas

- **Use `127.0.0.1`, not `localhost`, in dev server and proxy config.** On this Windows machine, Node resolves `localhost` to IPv6 (`::1`) only, and browsers then get `ERR_CONNECTION_REFUSED`.
- **Editing files from PowerShell 5.1:** `Get-Content` / `Set-Content` corrupt UTF-8 text (the docs contain em dashes), and `-Encoding utf8` adds a BOM. Use the Edit and Write tools instead, or .NET `File.ReadAllText` / `WriteAllText` with a BOM-less `UTF8Encoding`.
- The platform is Windows. Both PowerShell and Git Bash are available.

## Git

- Work on feature branches (for example `feat/<task-id>-<topic>`). `main` is the PR target.
- Commit only when asked.
- Never commit `.env` files, `backend/db.sqlite3`, `.venv/` or `node_modules/`.
- Commit `backend/uv.lock` and `frontend/package-lock.json`.
