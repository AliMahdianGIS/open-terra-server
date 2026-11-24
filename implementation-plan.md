# Open Terra Server — Implementation Plan

This plan implements the v1 scope in [project-scope.md](project-scope.md). It splits the work into phases. Each phase ends with something you can demo. Each task is small (roughly half a day to three days) and has a clear "done when" condition.

Task IDs (`P2.3` = phase 2, task 3) are for referencing tasks in issues and commits.

## Design principle: works for any city, not one sample

The system must work for city data from anywhere in the world. No code path, default or test is built around one dataset. In practice:

- **No dataset-specific assumptions.** Coordinate system, units, axis order, vertical datum, file layout and attribute structure always come from the data or from the user. They are never hard-coded.
- **A reference test corpus, not a reference dataset.** Development and acceptance use a set of varied open datasets (P0.1). The New York City OBJ is one entry in it, not the target.
- **Every corpus dataset must pass.** Milestones and the acceptance test pass only when every dataset in the corpus passes. A fix that helps one dataset and breaks another is a regression.
- **The corpus grows.** When a user reports data that fails, a sample of it (or a synthetic copy with the same properties) is added to the corpus with a regression test.

---

## Guiding decisions

The backend is **Django** (decided). The other choices shape the plan, and Phase 0 confirms or changes them.

| Topic | Choice | Reason |
|---|---|---|
| Backend | **Django** (Python) + **Django REST Framework**, OpenAPI schema from **drf-spectacular** | Decided. Django gives auth, sessions, permissions, migrations and an admin site out of the box, which covers much of Phase 6. |
| Geospatial | **GeoDjango** on PostGIS; **pyproj** for reprojection | Layer extents as geometry fields; pyproj gives in-process access to the full PROJ library. |
| Converters | Run as **CLI subprocesses** from the worker: loaders.gl `tile-converter`, `3d-tiles-tools`, obj2gltf (Node.js), Obj2Tiles (.NET) | The best converters are in Node and C#. A small Python wrapper per tool runs it, streams progress from its output, and maps errors. The worker image includes the Node and .NET runtimes. |
| glTF / 3D Tiles processing | **Node.js geometry toolkit** (`tools/geometry/`, TypeScript) built on **glTF-Transform**, loaders.gl and `3d-tiles-tools`, run by the worker as one CLI (`otgeo <command>`) | Python stays for the platform and coordinate systems; JavaScript has the best glTF tools. The toolkit does the glTF work Python is weak at (feature IDs, metadata, compression) and gives all JS-based steps one consistent interface. |
| Database | **PostgreSQL + PostGIS** | Users, layers, versions, jobs and permissions are relational. |
| Job queue | **Celery** with **Redis** as broker | The standard for background jobs in Django: retries, time limits, task routing (e.g. separate queues for heavy conversion and light jobs), and well known to contributors. Redis is also used as the cache. |
| Uploads | **tus** protocol: **tusd** (the reference tus server) as its own container, with HTTP hooks to Django; `tus-js-client` in the browser | Python tus servers are less mature. tusd handles uploads of tens of GB well. Django checks auth and quotas in the pre-create hook and registers the upload in the post-finish hook. |
| Tile serving | Django checks permissions, then **nginx serves the file** via `X-Accel-Redirect`. Public tiles can be served by nginx directly | Serving many small tile files through Python is slow. This keeps permission logic in Django and file delivery in nginx. |
| App server | **Gunicorn** (WSGI) behind nginx | Simple and proven. Job progress uses polling first; ASGI/SSE can be added later if needed. |
| Reprojection | **Native PROJ** (through pyproj) with its full EPSG database and transformation grids | Needed for worldwide data: every EPSG CRS, ESRI and OGC WKT, datum shifts that need grid files, and vertical datums / geoid models. |
| Frontend | **React + Vite + CesiumJS** | CesiumJS is required. React is common and contributor-friendly. TypeScript types for the API are generated from the OpenAPI schema (`openapi-typescript`). |
| Repo layout | `backend/` (Django project; the same code base runs as API and Celery worker), `tools/geometry/` (Node.js geometry toolkit), `web/` (React app), `docker/` (images and Compose files) | One Python code base for API and worker; no shared-types package needed thanks to OpenAPI generation. |
| License | AGPL-3.0 (pending the license check in P0.6) | See the scope. |

---

## Phase 0 — Discovery and technical spikes

**Goal:** Answer the open questions and test the riskiest assumptions before building the platform. The results go into `docs/adr/` (one Architecture Decision Record per decision).

- [ ] **P0.1 Build the reference test corpus.** Collect 6–10 openly licensed city datasets that together cover the variation the system must handle:
  - **Coordinate systems:** UTM, US State Plane, national grids (e.g. British National Grid, Gauss-Krüger, Lambert-93, RD New), a CRS that needs a grid-based datum shift, and a `.prj` in ESRI WKT as well as OGC WKT.
  - **Units:** meters, US survey feet, international feet.
  - **Location:** northern and southern hemispheres, high latitude, near the antimeridian, and a city that spans two UTM zones.
  - **Heights:** ellipsoidal heights, orthometric heights (geoid-based, e.g. NAVD88, EGM2008), and data with no reliable Z (for "relative to ground").
  - **Structure:** one large OBJ vs. many tiled OBJs, one object per building vs. one merged mesh, textured vs. untextured, missing `.prj`, non-ASCII file and object names.
  - **Size:** a small sample (fast CI), a district, and at least one full city with tens of GB.

  The New York City OBJ can be one entry. Record each dataset in `docs/test-corpus.md` with its source, license, CRS, units, vertical datum, structure and size. *Done when:* the corpus covers every item above (synthetic data is fine where no open dataset exists).
- [ ] **P0.2 Record ArcGIS Pro baselines.** Load each corpus dataset in ArcGIS Pro. Record 3–5 surveyed or clearly identifiable control points (coordinates of known corners or landmarks), the attribute table fields, and screenshots. These baselines are the reference for placement and attribute checks. *Done when:* baselines exist for every corpus dataset in a machine-readable format (e.g. `control-points.json` per dataset).
- [ ] **P0.3 Spike: OBJ → 3D Tiles with LOD.** Run Obj2Tiles (and an alternative such as obj2gltf + 3d-tiles-tools) on corpus datasets with different structures (single mesh, per-building objects, textured, untextured). Check LOD quality, texture handling, and **whether per-object feature IDs survive** decimation and splitting. *Done when:* an ADR picks the OBJ converter and states how feature identity is kept for every structure type. If the converter loses it, prototype the fix as a glTF-Transform script that writes `EXT_mesh_features` (this becomes part of the geometry toolkit).
- [ ] **P0.4 Spike: georeferencing.** Reproject samples from every CRS, unit and height type in the corpus to ECEF with an RTC origin. Measure the position error against the P0.2 control points. Decide whether to reproject vertices (exact) or use a local ENU transform per tile (fast, approximate), and check that the choice holds at high latitudes and across large extents. *Done when:* an ADR picks the approach and the error is below an agreed tolerance (e.g. < 5 cm horizontal and vertical) for every corpus dataset.
- [ ] **P0.5 Spike: 3D Tiles → I3S → ArcGIS Pro.** Convert the spike output with loaders.gl `tile-converter`, serve it with a minimal SceneServer mock, and add it to ArcGIS Pro by URL. Also open the SLPK. Check that attributes survive. *Done when:* an ADR covers the I3S path, the 3D Tiles 1.1 support gaps found, and the ArcGIS Pro version tested.
- [ ] **P0.6 Check dependency licenses.** List the licenses of CesiumJS, loaders.gl, Obj2Tiles, 3d-tiles-tools, PROJ and others, and confirm they are compatible with AGPL-3.0 (or Apache-2.0). *Done when:* the license ADR is accepted and a `LICENSE` file is added.
- [ ] **P0.7 Set performance targets.** Define targets that scale with the data, not with one city: processing throughput (e.g. triangles or GB per hour per worker), peak memory and disk use relative to input size, viewer FPS, tile load time (p95), and SceneServer response time. *Done when:* the targets are written in `docs/performance-targets.md`.
- [ ] **P0.8 Confirm the stack and contribution model.** Record the Django decision in an ADR, confirm or change the other guiding decisions above, and decide between solo work and open contribution (CONTRIBUTING.md, code of conduct, issue templates). *Done when:* an ADR is accepted.

**Milestone M0:** All open questions in the scope are answered, and the full chain (OBJ → 3D Tiles → I3S) has been shown to work by hand on one tile.

---

## Phase 1 — Project foundation

**Goal:** A running skeleton: API, worker, web app and database start with one `docker compose up`.

- [ ] **P1.1 Set up the repository.** `backend/` with a Django project and dependency management (uv or Poetry), Ruff + mypy (django-stubs); `web/` and `tools/geometry/` as pnpm workspaces with TypeScript, ESLint/Prettier; pre-commit hooks.
- [ ] **P1.2 Set up CI.** GitHub Actions for lint, type checks, pytest (pytest-django, against a PostGIS service container), web tests and Docker image builds on each PR.
- [ ] **P1.3 Create the Django project skeleton.** Settings split by environment and loaded from env vars (django-environ), apps `accounts`, `layers`, `uploads`, `processing`, `services` (3D Tiles + SceneServer); DRF with consistent error format; drf-spectacular schema and Swagger UI; structured logging; health check endpoint.
- [ ] **P1.4 Create the data model.** GeoDjango on PostGIS. Initial models: custom `User` (set up from day one, as Django recommends), `Organization`, `Layer`, `LayerVersion`, `Job`. Django migrations.
- [ ] **P1.5 Build the storage abstraction.** Use Django's `Storage` API (`FileSystemStorage` now, `django-storages` for S3/MinIO later) behind a small service module that adds what tiles need: streaming, range reads, prefix delete and a defined path layout (`layers/{id}/versions/{n}/source|3dtiles|i3s`).
- [ ] **P1.6 Create the worker skeleton.** Celery app with Redis broker, separate queues (`convert` for heavy jobs, `default` for light ones), a base task that reports progress to the `Job` model, time limits, and graceful shutdown. A helper for running converter CLIs as subprocesses with progress parsing and cancellation.
- [ ] **P1.6a Create the geometry toolkit skeleton.** `tools/geometry/` CLI (`otgeo`) in TypeScript, with a fixed contract the Python helper relies on: arguments in, JSON-lines progress and log events on stdout, a final JSON result, and documented exit codes and error codes. First commands: `inspect-gltf` (counts, extensions, bounds) and `validate-tileset` (wraps `3d-tiles-validator`). Unit tests with Vitest, plus a contract test from the Python side.
- [ ] **P1.7 Create the web app skeleton.** React + Vite, routing, an API client with types generated from the OpenAPI schema, and a page with a basic CesiumJS globe.
- [ ] **P1.8 Write Docker Compose.** Services: `db` (PostGIS), `redis`, `api` (Gunicorn), `worker` (Celery; image with Python, Node.js, .NET, the geometry toolkit and the converter CLIs chosen in Phase 0, all with pinned versions), `tusd`, and `proxy` (nginx serving the web build, Django static files and tile files). Named volumes for data.
- [ ] **P1.9 Add minimal authentication.** Django auth with session cookies (CSRF protection on), login/logout API for the React app, Argon2 password hasher, and a first admin user created from env vars on startup (management command). (Roles and sharing come in Phase 6.)

**Milestone M1:** `docker compose up` starts everything; an admin can log in and see an empty globe.

---

## Phase 2 — Upload and layer management

**Goal:** Users can create a layer and upload a large zip file reliably.

- [ ] **P2.1 Layer CRUD API.** Create, list, get, update and delete layers, with metadata: title, description, attribution, data license.
- [ ] **P2.2 Resumable upload endpoint.** tusd container writing to the shared data volume. Django hook endpoint: `pre-create` checks the session/API key, layer ownership, size limit and quota; `post-finish` links the upload to a layer version and queues the inspection job.
- [ ] **P2.3 Upload UI.** Form for layer metadata, file picker, progress bar, pause/resume, and resume after a page reload.
- [ ] **P2.4 Archive inspection job.** Unzip safely (protect against zip-slip and zip bombs), detect the input format (OBJ / glTF / GLB / SLPK / 3D Tiles), and store a file manifest.
- [ ] **P2.5 Input validation.** Per format: OBJ has its `.mtl` and textures; 3D Tiles has `tileset.json`; SLPK has a valid `3dSceneLayer.json`. Show clear, specific error messages for missing files.
- [ ] **P2.6 Layer list and detail pages.** Show layers, their status, metadata, and versions.
- [ ] **P2.7 Download the original upload.** Endpoint that streams the original zip (with range support).

**Milestone M2:** A publisher can upload the largest corpus dataset, resume an interrupted upload, and see the detected format and file list for every corpus dataset.

---

## Phase 3 — Georeferencing and OBJ → 3D Tiles pipeline

**Goal:** The core pipeline: OBJ data is converted to 3D Tiles and lands in the right place.

### 3a. Georeferencing

- [ ] **P3.1 CRS detection.** Read the CRS from a `.prj` in any common form (ESRI WKT, OGC WKT1, WKT2, PROJJSON) and from other sidecars found in the corpus (e.g. `.xml` metadata). Match it to an EPSG code where possible. If there is no EPSG match, keep the WKT and use it directly, so custom and local CRSs still work.
- [ ] **P3.2 Manual CRS selection.** If no CRS is found, the publish step asks for one: a searchable picker over the full EPSG database (search by code, name, country or area of use), or pasted WKT. Validate through PROJ, and warn when the data extent falls outside the CRS's area of use (a common sign of the wrong CRS).
- [ ] **P3.3 Transform module.** Python module (pyproj + NumPy for bulk vertex transforms): source CRS → WGS84 / ECEF through PROJ. Handles any linear unit the CRS defines (no hard-coded unit list), axis order, and datum transformations, including the ones that need grid files. Computes an RTC origin per tile.
- [ ] **P3.4 Transformation grids.** Ship the PROJ grids needed by common CRSs in the worker image. Optionally allow downloading more grids on demand (PROJ CDN) when the admin enables it. If a needed grid is missing, warn about reduced accuracy instead of failing silently.
- [ ] **P3.5 Vertical datums.** Convert heights to the ellipsoidal heights 3D Tiles needs. Read the vertical CRS from a compound CRS when present; otherwise let the user pick one (e.g. ellipsoidal, EGM96, EGM2008, or a national datum such as NAVD88 or DHHN2016). Apply geoid models through PROJ.
- [ ] **P3.6 Height modes.** *Absolute* (Z as-is, after the vertical datum conversion) and *relative to ground* (sample the terrain height and shift the model so its base sits on it), plus an optional vertical offset. Baked into the output.
- [ ] **P3.7 Terrain sampling for "relative to ground".** Sample Cesium World Terrain (when an Ion token is set) on the server side, at several points across the layer extent rather than one origin. With no token, show a warning and fall back to absolute height.
- [ ] **P3.8 Placement regression tests.** CI runs P3.1–P3.6 on a small sample from every corpus dataset and checks the output positions against the P0.2 control points. The build fails if any dataset goes outside the tolerance.

### 3b. Conversion

- [ ] **P3.9 Publish settings UI and API.** Collect CRS, vertical datum, height mode, offset and output options; show the detected values and let the user change them; save them on the layer version; start the job.
- [ ] **P3.10 Job pipeline framework.** A job is a list of steps (inspect → georeference → convert → post-process → validate → publish). Each step reports progress, and a failed job can be retried from the step that failed.
- [ ] **P3.11 OBJ → 3D Tiles step.** Wrap the converter chosen in P0.3, using the transforms from P3.3–P3.6. Handle both single-file and multi-tile datasets, whatever their file naming or folder layout.
- [ ] **P3.12 Feature identity and attributes.** Each OBJ group/object becomes a feature. Python reads the OBJ groups and sidecar attribute files (formats found in the corpus) and writes a feature table. A toolkit command (`otgeo add-features`, glTF-Transform) writes feature IDs (`EXT_mesh_features`) and a property table (`EXT_structural_metadata`) into each tile's glTF. Keep Unicode names and values intact.
- [ ] **P3.12a glTF optimization.** Toolkit command (`otgeo optimize`): deduplicate, weld, meshopt or Draco geometry compression, and KTX2/WebP texture compression, each configurable at publish time. Check that compressed output still converts to I3S (P5.1) before turning it on by default.
- [ ] **P3.13 Output validation.** Run `3d-tiles-validator` through `otgeo validate-tileset`; fail the job on errors and store warnings.
- [ ] **P3.14 Compute layer extent.** Store the bounding box in PostGIS for "zoom to layer" and later search. Handle extents that cross the antimeridian.
- [ ] **P3.15 Job status UI.** Progress per step, logs, error details, and a retry button. Live updates by polling the job API (SSE can come later).

**Milestone M3:** Every corpus dataset converts to a valid 3D Tiles 1.1 tileset with feature IDs and attributes, in the correct location (P3.8 placement tests pass for all of them).

---

## Phase 4 — 3D Tiles serving and web viewer

**Goal:** Published layers display in the built-in viewer and in any CesiumJS app.

- [ ] **P4.1 Tile serving endpoint.** `GET /layers/{id}/3dtiles/tileset.json` and tile content. Stable URL that always points to the current version. A Django view resolves the layer, checks access and returns an `X-Accel-Redirect` to an internal nginx location, so nginx sends the file. Correct `Content-Type`, gzip/brotli for JSON, CORS (django-cors-headers / nginx).
- [ ] **P4.2 Caching.** Version-scoped internal paths, `ETag`/`Cache-Control: immutable` for tiles, short cache for `tileset.json`. Cache layer lookups and permission results in Redis so each tile request costs as little Python work as possible. Optional nginx caching in front.
- [ ] **P4.3 Viewer page.** Load a layer by ID, zoom to its extent, show a loading indicator and error state.
- [ ] **P4.4 Basemap and terrain config.** Use Cesium Ion default terrain and imagery when a token is configured; fall back to OSM imagery with an ellipsoid (no terrain) when not.
- [ ] **P4.5 Identify.** Click a feature to highlight it and show its attributes in a side panel.
- [ ] **P4.6 Share links.** Copy a URL that opens the viewer at a layer and camera position. Also show the raw tileset URL for use in other CesiumJS apps, with a code snippet.
- [ ] **P4.7 Multiple layers.** Layer list in the viewer to turn layers on and off.

**Milestone M4 (acceptance steps 1–3):** Every corpus dataset is uploaded, placed correctly without manual positioning, and displays in the viewer with attributes on click.

---

## Phase 5 — I3S output: SLPK and SceneServer

**Goal:** Published layers open in ArcGIS Pro, both as a file and as a service.

- [ ] **P5.1 3D Tiles → I3S conversion step.** Add a pipeline step using loaders.gl `tile-converter`, run through the toolkit (`otgeo to-i3s`) so it reports progress and errors in the same format as the other steps (I3S 1.7/1.8, 3D Object profile), configured as decided in P0.5. Make I3S output an option at publish time.
- [ ] **P5.2 Attribute store.** Make sure feature attributes reach the I3S attribute store with the same field names and types as the source. Fix or work around converter gaps found in P0.5.
- [ ] **P5.3 SLPK packaging and download.** Build the SLPK (stored, not compressed, as Esri requires) and provide a download endpoint with range support.
- [ ] **P5.4 SceneServer REST API: service level.** Django views for `/rest/services/{layer}/SceneServer` and `/SceneServer/layers/0` JSON, matching Esri's format (`?f=json`, `?f=pjson`).
- [ ] **P5.5 SceneServer REST API: nodes and resources.** Node pages, geometries, textures, attributes and shared resources. Store the I3S output unpacked on disk so nginx can serve the binary resources via `X-Accel-Redirect`, like tiles; generate JSON documents in Django only where they must be rewritten (e.g. URLs).
- [ ] **P5.6 ArcGIS Pro compatibility tests.** A documented manual test (and automated JSON contract tests against recorded Pro requests): add the service by URL, check location, attributes and identify. Record the tested Pro version.
- [ ] **P5.7 Show service URLs in the UI.** On the layer page: 3D Tiles URL, SceneServer URL and SLPK download, with copy buttons and "how to add in ArcGIS Pro" help.

**Milestone M5 (acceptance step 4):** For every corpus dataset, the SceneServer service and the SLPK both load in ArcGIS Pro in the same location and with the same attributes as the P0.2 baseline.

---

## Phase 6 — Users, roles, sharing and access

**Goal:** Multi-user support with the permission model from the scope.

- [ ] **P6.1 Roles.** Admin, Publisher, Viewer, as Django groups/permissions. Object-level checks in one central module (one place that answers "can user X do Y on layer Z"), used by DRF permission classes and the tile/SceneServer views.
- [ ] **P6.2 User management (admin).** Invite or create users, change roles, deactivate users. Use the Django admin site first; add screens in the React app where admins need a friendlier UI.
- [ ] **P6.3 Organizations and teams.** Create organizations, add/remove members, organization admins.
- [ ] **P6.4 Layer visibility.** Private, Shared (with specific users or organizations), Public. Sharing dialog in the UI.
- [ ] **P6.5 Apply permissions everywhere.** Layer API, tile serving, SceneServer, downloads and viewer. Public layers need no login. Add tests for each access path.
- [ ] **P6.6 API keys.** Create, list and revoke keys per user; keys can be limited to specific layers; passed as a URL query parameter (works with CesiumJS); stored hashed; last-used time recorded.
- [ ] **P6.7 Quotas.** Storage and processing limits per user/organization, set by the admin. Enforced at upload start and job start; usage shown in the UI.
- [ ] **P6.8 Security pass.** Rate limiting on login (DRF throttling or django-axes), review of CSRF and session settings, secure headers (Django `SecurityMiddleware`, CSP), `manage.py check --deploy` in CI, and an audit log for admin actions.

**Milestone M6:** Private, shared and public layers behave correctly for all clients; private layers work in CesiumJS with an API key; ArcGIS Pro users can download the SLPK for private layers.

---

## Phase 7 — Other input formats

**Goal:** Support the remaining v1 inputs.

- [ ] **P7.1 glTF / GLB input.** Georeference (CRS + origin from the user if not in the file), then tile with LOD into 3D Tiles.
- [ ] **P7.2 3D Tiles import.** Validate an uploaded tileset and re-serve it as-is; optionally upgrade older versions to 1.1 with `3d-tiles-tools`; optionally convert to I3S.
- [ ] **P7.3 SLPK import.** Validate and serve the SLPK through the SceneServer API; optionally convert to 3D Tiles with `tile-converter`.
- [ ] **P7.4 Format-specific publish options.** The publish UI shows only the options that apply to the detected format (e.g. no CRS step for 3D Tiles).

**Milestone M7:** Each of the four input formats can be uploaded and published to both outputs (where conversion is supported).

---

## Phase 8 — Styling

**Goal:** Publishers can style layers in the built-in viewer.

- [ ] **P8.1 Style model and API.** Store styles per layer as JSON, based on the Cesium 3D Tiles Styling language (color, show/filter conditions).
- [ ] **P8.2 Color by attribute.** UI to pick a field and a scheme: unique values (categories) or class breaks (numbers), with a legend.
- [ ] **P8.3 Filter by attribute.** UI to build simple conditions (field, operator, value) that hide features.
- [ ] **P8.4 Save and load.** Styles are saved with the layer and applied when anyone opens it in the viewer; a default style can be set.
- [ ] **P8.5 Field statistics.** Compute distinct values and min/max per field during processing to drive the style UI.

**Milestone M8:** A publisher colors a corpus layer's buildings by an attribute, saves the style, and other users see it.

---

## Phase 9 — Layer lifecycle

**Goal:** Versioning, deletion and clean storage.

- [ ] **P9.1 Re-upload as new version.** Upload new data to an existing layer; process it in the background; switch the service URLs to the new version only when processing succeeds.
- [ ] **P9.2 Version history.** List versions with status and dates; roll back to an earlier version.
- [ ] **P9.3 Delete layer.** Remove the database records, source files and all generated outputs; cancel running jobs first.
- [ ] **P9.4 Storage cleanup.** Remove abandoned uploads, failed job output and old versions (with a configurable retention).
- [ ] **P9.5 Cache invalidation.** Make sure version switches and deletions are not hidden by cached responses (version-scoped paths from P4.2).

**Milestone M9:** A layer can be updated, rolled back and deleted without broken URLs or leftover files.

---

## Phase 10 — Performance, hardening and v1 release

**Goal:** Pass the full acceptance test and prepare the release.

- [ ] **P10.1 Full-scale processing runs.** Process the full-city datasets in the corpus; measure time, memory and disk; tune worker concurrency and converter settings against the P0.7 targets. Check that resource use grows in a predictable way with input size, so larger cities are not a surprise.
- [ ] **P10.2 Tile serving load test.** Load test the tile and SceneServer endpoints (e.g. k6) with realistic request patterns; tune nginx caching, keep-alive and HTTP/2.
- [ ] **P10.3 Viewer performance.** Tune `maximumScreenSpaceError`, tile cache size and request scheduling; measure FPS and load time against targets.
- [ ] **P10.4 Large-upload robustness.** Test uploads of tens of GB, network interruptions, and worker restarts during jobs.
- [ ] **P10.5 End-to-end tests.** Playwright tests for upload → publish → view → identify → share, run in CI with the small samples from the corpus.
- [ ] **P10.6 Acceptance test run.** Run acceptance steps 1–5 from the scope on every corpus dataset and record the results per dataset, the ArcGIS Pro version and screenshots.
- [ ] **P10.7 Documentation.** Install guide (Docker Compose, configuration, Ion token, reverse proxy, TLS), user guide, API reference, and architecture overview.
- [ ] **P10.8 Operations basics.** Backup and restore of the database and storage, upgrade/migration notes, and a metrics endpoint.
- [ ] **P10.9 Release.** Version tag, published Docker images, changelog and release notes.

**Milestone M10:** v1.0 released; acceptance test passed and documented.

---

## Phase order and parallel work

```
P0 ──► P1 ──► P2 ──► P3 ──► P4 ──► P5 ──────────► P10
                       │      │                   ▲
                       │      └──► P8 ───────────┤
                       └──► P7 (after P3/P5) ─────┤
              P6 (can start after P2) ────────────┤
              P9 (after P4) ──────────────────────┘
```

- **Critical path:** P0 → P1 → P2 → P3 → P4 → P5 → P10. This delivers the core value (any city's data correctly placed in Cesium and ArcGIS Pro) as early as possible.
- **Parallel work** (for contributors): P6 (permissions) after P2; P8 (styling) after P4; P7 (other formats) after P3/P5; P9 (lifecycle) after P4.
- Until Phase 6, every user is effectively an admin. Keep authorization checks behind one function from the start (P1.9) so Phase 6 does not need a rewrite.

## Main risks

| Risk | Impact | Mitigation |
|---|---|---|
| Feature IDs lost during OBJ tiling and decimation | Identify and styling don't work | Test in P0.3; write a custom glTF post-processing step if needed. |
| Position errors from approximate georeferencing at city scale | Data in the wrong place | Measure in P0.4; reproject vertices if the error is too large. |
| Data from regions or CRSs the corpus doesn't cover | Wrong placement for some users | Use PROJ for all CRS handling (no custom math per CRS); warn when the extent is outside the CRS's area of use; add failing user data to the corpus (see design principle). |
| Python request overhead on many small tile requests | Slow tile loading at city scale | nginx sends the files via `X-Accel-Redirect` (P4.1); public tiles served by nginx directly; permission results cached in Redis (P4.2); load test in P10.2. |
| Converters run as external processes (Node, .NET) | Hard-to-read errors, no fine-grained progress, larger worker image | JS-based tools run through the geometry toolkit's fixed JSON contract (P1.6a); Obj2Tiles gets a Python wrapper that parses its output; pin tool versions in the worker image; test each step against the corpus samples. |
| Two languages in the back end (Python + TypeScript) | More for contributors to learn; logic split across both | Clear split: Python owns the platform, coordinate systems and job orchestration; the toolkit only transforms glTF/tiles files and holds no platform logic. Contract tests keep the two sides in sync. |
| Wrong or missing vertical datum | Buildings float or sink by tens of meters | Explicit vertical datum step (P3.5), with the detected value shown to the user before processing. |
| `tile-converter` gaps for 3D Tiles 1.1 → I3S (e.g. metadata) | Missing attributes in ArcGIS Pro | Test in P0.5; contribute fixes upstream or add a conversion step. |
| ArcGIS Pro changes its SceneServer client | Service stops loading in Pro | Contract tests from recorded requests (P5.6); test each new Pro release. |
| Processing time and disk use at full city scale | Acceptance step 5 fails | Early full-scale run in P10.1 (or sooner, after P3); process tiles in parallel. |
