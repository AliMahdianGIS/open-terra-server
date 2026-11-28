# Open Terra Server — Implementation Plan

This plan implements the v1 scope in [project-scope.md](project-scope.md). It splits the work into phases. Each phase ends with something you can demo. Each task is small (roughly half a day to three days) and has a clear "done when" condition.

Task IDs (`P2.3` = phase 2, task 3) are for referencing tasks in issues and commits.

**Phase 1 comes first because it is the core value:** turn city data in different formats into 3D Tiles that render fast. Platform features (database models, job queue, uploads, auth, Docker) come after the conversion works.

## Design principle: works for any city, not one sample

The system must work for city data from anywhere in the world. No code path, default or test is built around one dataset. In practice:

- **No dataset-specific assumptions.** Coordinate system, units, axis order, vertical datum, file layout and attribute structure always come from the data or from the user. They are never hard-coded.
- **A reference test corpus, not a reference dataset.** Development and acceptance use a set of varied open datasets (P1.1). The New York City OBJ is one entry in it, not the target.
- **Every corpus dataset must pass.** Milestones pass only when every dataset in the corpus passes. A fix that helps one dataset and breaks another is a regression.
- **The corpus grows.** When a user reports data that fails, a sample of it (or a synthetic copy with the same properties) is added to the corpus with a regression test.

---

## Guiding decisions

| Topic | Choice | Reason |
|---|---|---|
| Backend | **Django** + **Django REST Framework**, OpenAPI schema from **drf-spectacular** | Decided. Gives auth, permissions, migrations and an admin site out of the box. |
| Converters | Run as **CLI subprocesses**: Obj2Tiles (.NET), obj2gltf, `3d-tiles-tools` and loaders.gl `tile-converter` (Node.js) | The best converters are in Node and C#. A small Python wrapper per tool runs it, reads its progress and maps its errors. |
| glTF / 3D Tiles processing | **Node.js geometry toolkit** (`tools/geometry/`, TypeScript, glTF-Transform), run as one CLI (`otgeo <command>`) | JavaScript has the best glTF tools. Python stays for orchestration and coordinate systems. |
| Reprojection | **pyproj** (native PROJ with its full EPSG database) | Needed for worldwide data: every EPSG CRS, ESRI and OGC WKT, and datum shifts. |
| Frontend | **React + Vite + CesiumJS** | CesiumJS is required. |
| Database | SQLite in Phase 1; **PostgreSQL + PostGIS** (GeoDjango) from Phase 2 | Phase 1 needs no data model. |
| Job queue | Synchronous runs in Phase 1; **Celery** with **Redis** from Phase 2 | Phase 1 conversions run from a management command. |
| Uploads | **tusd** with HTTP hooks to Django; `tus-js-client` in the browser (Phase 3) | Handles uploads of tens of GB. |
| Tile serving | Django dev view in Phase 1; Django checks permissions and **nginx serves the file** via `X-Accel-Redirect` from Phase 5 | Serving many small tile files through Python is slow. |
| Repo layout | `backend/`, `frontend/`, `tools/geometry/`, `docker/` (Phase 2) | One Python code base for API and worker. |
| License | AGPL-3.0 (pending the license check in P1.2) | See the scope. |

---

## Phase 1 — Convert formats to 3D Tiles for fast rendering

**Goal:** One command turns OBJ, glTF/GLB, SLPK or 3D Tiles input into an optimized 3D Tiles 1.1 tileset with levels of detail, placed in the right location, that renders smoothly in the CesiumJS viewer.

Already done: Django API skeleton (`/api/health/`, `/api/map-config/`) and a React + CesiumJS globe that works without an Ion token.

- [ ] **P1.1 Build the test corpus.** Small samples from varied, openly licensed city datasets (candidates in [docs/test-corpus.md](docs/test-corpus.md)) covering each input format, several CRSs and units, both hemispheres, textured and untextured data, one merged mesh and per-building objects, and single-file and tiled layouts. Synthetic data is fine where no open dataset exists. *Done when:* the samples are downloaded, recorded in `docs/test-corpus.md`, and a small subset is picked for CI.
- [ ] **P1.2 Pick the converters.** Try Obj2Tiles and obj2gltf + `3d-tiles-tools` on the OBJ samples; pick tools for glTF/GLB tiling and SLPK → 3D Tiles (`tile-converter`). Compare LOD quality, texture handling, speed and whether object identity survives. Check the tools' licenses. *Done when:* an ADR in `docs/adr/` names one tool per input format.
- [ ] **P1.3 Converter runner and command.** A Python helper in `apps/conversion` that runs a converter CLI as a subprocess, reads its progress, maps its errors and can be cancelled. Tool paths come from environment variables. A management command `convert <input> <output> [options]` runs a full conversion. *Done when:* the command runs a converter end to end and reports clear errors when a tool is missing or fails.
- [ ] **P1.4 Input detection and checks.** Detect the format of a file, folder or zip (OBJ / glTF / GLB / SLPK / 3D Tiles) and check that its parts are present: OBJ has its `.mtl` and textures, 3D Tiles has `tileset.json`, SLPK has `3dSceneLayer.json`. *Done when:* every corpus sample is detected correctly and broken samples give specific error messages.
- [ ] **P1.5 Georeferencing.** Read the CRS from a `.prj` (ESRI WKT, OGC WKT, WKT2, PROJJSON) or take it from the user (EPSG code or WKT). Transform to ECEF through pyproj with an RTC origin, using the units and axis order the CRS defines. Heights are used as given, plus an optional offset (vertical datum conversion comes in Phase 4). *Done when:* samples from every CRS in the corpus land within an agreed tolerance of known control points.
- [ ] **P1.6 OBJ → 3D Tiles with LOD.** Wrap the OBJ converter from P1.2 with the transform from P1.5. Generate several LOD levels by decimation and split large meshes into spatial tiles, with geometric errors that let CesiumJS load coarse tiles first. Handle single-file and multi-file datasets whatever their naming or folder layout. *Done when:* every OBJ sample converts.
- [ ] **P1.7 glTF / GLB → 3D Tiles with LOD.** Same as P1.6 for glTF and GLB input. *Done when:* every glTF/GLB sample converts.
- [ ] **P1.8 SLPK → 3D Tiles.** Convert I3S SLPK input with `tile-converter`, keeping its existing LOD tree. *Done when:* every SLPK sample converts.
- [ ] **P1.9 3D Tiles input.** Validate an existing tileset and upgrade older versions to 1.1 with `3d-tiles-tools`. *Done when:* every 3D Tiles sample passes through.
- [ ] **P1.10 Optimize for rendering.** Start the geometry toolkit (`tools/geometry/`, `otgeo optimize`): deduplicate, weld, meshopt or Draco geometry compression and KTX2/WebP textures, each configurable. *Done when:* optimized output is measurably smaller and faster to load than unoptimized output on the corpus, with no visible loss at the default settings.
- [ ] **P1.11 Output validation.** Run `3d-tiles-validator` on every output; fail the conversion on errors and report warnings. *Done when:* the command fails on an invalid tileset and passes on valid ones.
- [ ] **P1.12 View converted tilesets.** A development endpoint that serves converted tilesets from the output folder, and a viewer page that lists them, loads one, and zooms to it. Tune `maximumScreenSpaceError` and the tile cache for smooth rendering. *Done when:* every converted corpus sample opens in the viewer and stays responsive while moving the camera.
- [ ] **P1.13 Conversion tests.** pytest runs the conversion on the CI subset of the corpus, for every input format, and checks that the output is valid and in the right place. *Done when:* the tests pass for every sample in the subset.

**Milestone M1:** Every corpus sample, in every supported input format, converts with one command to a valid 3D Tiles 1.1 tileset with LODs, lands in the right place, and renders smoothly in the viewer.

---

## Phase 2 — Platform foundation

**Goal:** The conversion runs as a background job on a platform that starts with one `docker compose up`.

- [ ] **P2.1 Data model.** GeoDjango on PostGIS: custom `User`, `Organization`, `Layer`, `LayerVersion`, `Job`. Store layer extents (handle the antimeridian).
- [ ] **P2.2 Storage abstraction.** Django `Storage` API (file system now, S3/MinIO later) with a fixed path layout (`layers/{id}/versions/{n}/source|3dtiles|i3s`).
- [ ] **P2.3 Worker.** Celery with Redis; separate `convert` and `default` queues; the Phase 1 conversion runs as a job made of steps (inspect → georeference → convert → optimize → validate → publish) that report progress and can be retried from the failed step.
- [ ] **P2.4 Docker Compose.** `db`, `redis`, `api` (Gunicorn), `worker` (with Node.js, .NET and pinned converter versions), `tusd` and `proxy` (nginx).
- [ ] **P2.5 Minimal authentication.** Session login for the React app and a first admin user from env vars. Keep authorization behind one function so Phase 7 doesn't need a rewrite.
- [ ] **P2.6 CI.** GitHub Actions for lint, type checks, tests (against PostGIS) and image builds.

**Milestone M2:** `docker compose up` starts everything; an admin logs in and a conversion runs as a background job.

---

## Phase 3 — Upload and layer management

- [ ] **P3.1 Layer CRUD API** with title, description, attribution and data license.
- [ ] **P3.2 Resumable uploads** through tusd, with auth, size and quota checks in its hooks.
- [ ] **P3.3 Upload UI** with progress, pause/resume and resume after reload.
- [ ] **P3.4 Safe archive extraction** (zip-slip and zip-bomb protection) feeding the P1.4 detection.
- [ ] **P3.5 Publish settings UI.** Show the detected CRS and options; a searchable EPSG picker or pasted WKT when no CRS is found, with a warning when the data is outside the CRS's area of use.
- [ ] **P3.6 Layer pages and job status UI** (progress per step, logs, errors, retry).
- [ ] **P3.7 Download the original upload** with range support.

**Milestone M3:** A publisher uploads any corpus dataset in the browser and publishes it to 3D Tiles.

---

## Phase 4 — Accurate placement and attributes

- [ ] **P4.1 Vertical datums.** Convert heights to ellipsoidal heights, from a compound CRS or a user choice (e.g. EGM2008, NAVD88, DHHN2016), through PROJ geoid models.
- [ ] **P4.2 Transformation grids.** Ship the PROJ grids common CRSs need; warn when a needed grid is missing.
- [ ] **P4.3 Height modes.** Absolute or relative to ground (terrain sampled at several points when an Ion token is set; otherwise warn and use absolute).
- [ ] **P4.4 Feature identity and attributes.** Each OBJ group/object becomes a feature: `otgeo add-features` writes `EXT_mesh_features` and `EXT_structural_metadata`, keeping Unicode names and values.
- [ ] **P4.5 Placement regression tests** against control points for every corpus dataset.

**Milestone M4:** Every corpus dataset is placed within tolerance, including heights, and keeps its attributes.

---

## Phase 5 — 3D Tiles serving and viewer

- [ ] **P5.1 Tile serving.** Stable URL per layer; Django checks access and nginx sends the file (`X-Accel-Redirect`); correct content types, compression and CORS.
- [ ] **P5.2 Caching.** Version-scoped paths, immutable tiles, short cache for `tileset.json`, cached permission lookups.
- [ ] **P5.3 Viewer.** Layer list, zoom to layer, loading and error states, Ion or OSM basemap.
- [ ] **P5.4 Identify.** Click a feature to highlight it and show its attributes.
- [ ] **P5.5 Share links** to the viewer and the raw tileset URL with a CesiumJS snippet.

**Milestone M5:** Published layers display in the built-in viewer and in any CesiumJS app, with attributes on click.

---

## Phase 6 — I3S output: SLPK and SceneServer

- [ ] **P6.1 3D Tiles → I3S** with `tile-converter` (`otgeo to-i3s`), as a publish option.
- [ ] **P6.2 Attribute store** with the source field names and types.
- [ ] **P6.3 SLPK packaging and download.**
- [ ] **P6.4 SceneServer REST API** (service, layer, nodes and resources), with binary resources served by nginx.
- [ ] **P6.5 ArcGIS Pro compatibility tests** and service URLs shown in the UI.

**Milestone M6:** For every corpus dataset, the SceneServer service and the SLPK load in ArcGIS Pro in the right place with attributes.

---

## Phase 7 — Users, roles, sharing and access

- [ ] **P7.1 Roles** (Admin, Publisher, Viewer) with object-level checks in one module.
- [ ] **P7.2 User management and organizations.**
- [ ] **P7.3 Layer visibility:** private, shared, public; applied to the API, tiles, SceneServer and downloads.
- [ ] **P7.4 API keys** (hashed, revocable, optionally per layer, usable from CesiumJS).
- [ ] **P7.5 Quotas** for storage and processing.
- [ ] **P7.6 Security pass:** login rate limits, secure headers, `check --deploy` in CI, audit log.

**Milestone M7:** Private, shared and public layers behave correctly for every client.

---

## Phase 8 — Styling

- [ ] **P8.1 Style model** based on the Cesium 3D Tiles Styling language.
- [ ] **P8.2 Color and filter by attribute**, driven by field statistics computed during processing.
- [ ] **P8.3 Saved and default styles** that every viewer sees.

**Milestone M8:** A publisher colors a layer by an attribute, saves the style, and other users see it.

---

## Phase 9 — Layer lifecycle

- [ ] **P9.1 New versions** that go live only when processing succeeds; version history and rollback.
- [ ] **P9.2 Delete layers** with all files and running jobs.
- [ ] **P9.3 Storage cleanup** of abandoned uploads, failed output and old versions.

**Milestone M9:** A layer can be updated, rolled back and deleted without broken URLs or leftover files.

---

## Phase 10 — Performance, hardening and v1 release

- [ ] **P10.1 Full-scale runs** on the full-city corpus datasets; tune against written performance targets.
- [ ] **P10.2 Load tests** for tile and SceneServer endpoints.
- [ ] **P10.3 End-to-end tests** (Playwright) for upload → publish → view → identify → share.
- [ ] **P10.4 Acceptance test run** on every corpus dataset.
- [ ] **P10.5 Documentation, backups and release.**

**Milestone M10:** v1.0 released; acceptance test passed and documented.

---

## Phase order

```
P1 ──► P2 ──► P3 ──► P4 ──► P5 ──► P6 ──────► P10
                      │      ├──► P8 ────────┤
       P7 (after P2) ─┼──────┼───────────────┤
                      └──────┴──► P9 ────────┘
```

**Critical path:** P1 → P2 → P3 → P4 → P5 → P6 → P10. Phase 1 proves the hardest part (fast, correctly placed 3D Tiles from any format) before the platform is built around it.

## Main risks

| Risk | Impact | Mitigation |
|---|---|---|
| A converter loses object identity during decimation and tiling | Identify and styling don't work | Check in P1.2; add a glTF post-processing step (P4.4) if needed. |
| Position errors from approximate georeferencing at city scale | Data in the wrong place | Measure in P1.5 on every corpus CRS; reproject vertices if the error is too large. |
| Data from regions or CRSs the corpus doesn't cover | Wrong placement for some users | All CRS handling through PROJ; warn when the extent is outside the CRS's area of use; add failing data to the corpus. |
| Converters run as external processes (Node, .NET) | Hard-to-read errors, coarse progress | One runner with error mapping (P1.3); pinned tool versions; tests on corpus samples. |
| Slow rendering of large cities | Poor viewer experience | LODs and geometric errors (P1.6), compression (P1.10), viewer tuning (P1.12), full-scale runs (P10.1). |
| Processing time and disk use at full city scale | Large datasets fail | Full-scale runs in P10.1, or sooner after Phase 2. |
