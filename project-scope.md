# Open Terra Server — Project Scope

## Problem

I have many 3D layers (such as OBJ files) that I want to publish on a map and share with others. However, there isn't a powerful, free platform available for this purpose. Options like Cesium Ion and ArcGIS Online exist, but they are neither free nor open-source, so users cannot download their projects or deploy them on their own servers.

## Solution

An open-source, self-hostable system that lets users upload, convert, publish and share spatial layers. Version 1 focuses on **city-scale 3D layers**. 2D layers come later. Over time, the project will add useful services found in Cesium Ion and ArcGIS Online.

The project is a **platform around existing open-source conversion tools** (upload, processing, storage, serving, permissions, viewer). It does not reimplement converters where a good open-source one exists.

## Target users

- People and organizations who have city-scale 3D data (photogrammetry meshes, building models) and want to publish it without a commercial platform.
- Consumers of the published layers in ArcGIS Pro, CesiumJS-based apps, and the built-in web viewer.

## Version 1 scope

### 1. Upload

- Upload as a zip archive (OBJ + `.mtl` + textures + `.prj`, or a multi-tile dataset).
- Resumable/chunked uploads for large files (city-scale datasets can be tens of GB).
- Supported input formats in v1:
  - OBJ (with `.mtl`, textures, and `.prj` sidecar)
  - glTF / GLB
  - SLPK (import and re-serve existing I3S packages)
  - 3D Tiles (import and re-serve existing tilesets)
- Layer metadata: title, description, attribution, data license.

### 2. Georeferencing

Goal: uploaded data lands in the correct place automatically, the same way it does in ArcGIS Pro.

- Read the coordinate system from a `.prj` sidecar file when present.
- Otherwise, the user chooses an EPSG code at upload (e.g. UTM zones, State Plane).
- Reproject from the source coordinate system to the output (WGS84 / ECEF for 3D Tiles; as required for I3S).
- Take linear units (meters, US feet, feet) from the coordinate system.
- Re-center tiles on a local origin (RTC) to avoid floating-point jitter with large projected coordinates.
- Height options at publish time:
  - **Absolute height** (use the Z values as-is)
  - **Relative to ground** (place the model on the terrain surface)
  - Optional vertical offset
- Height mode and offset are baked into the generated output, because CesiumJS has no client-side equivalent for 3D Tiles.

### 3. Processing pipeline

- Processing runs as background jobs (queue + workers), separate from the web API.
- Job status and progress are visible to the user. Failed jobs show the error and can be retried.
- Generates level-of-detail (LOD) hierarchies suitable for city-scale data.
- Keeps feature identity: each OBJ group/object becomes a feature with its attributes, so attributes are available for identify and styling (feature IDs + metadata in 3D Tiles, the attribute store in I3S).
- Uses existing open-source tools where possible, for example:
  - Obj2Tiles (OBJ → 3D Tiles with LOD)
  - loaders.gl `tile-converter` (3D Tiles ↔ I3S)
  - Cesium `3d-tiles-tools`, obj2gltf
- Final tool choice is part of the technical design.

### 4. Output services

- **3D Tiles 1.1**, served over HTTP for CesiumJS and other 3D Tiles clients.
- **I3S 1.7/1.8 (3D Object profile)**:
  - Downloadable **SLPK** file.
  - Online **SceneServer**-compatible REST service (mimicking Esri's SceneServer API) that can be added to ArcGIS Pro by URL.
- Compatibility with ArcGIS Pro must be tested against the current Pro release. API mimicking can break when Esri changes the client.

### 5. Styling

- Users can define and change styles for a layer in the built-in viewer (e.g. color by attribute, filter by attribute).
- Styles are stored per layer.
- Styles apply only to the built-in viewer. ArcGIS Pro and third-party Cesium apps use their own styling, and this is accepted.

### 6. Web viewer

- Built on CesiumJS.
- Displays published layers, supports identify (click a feature to see its attributes) and styling.
- Share links for layers.
- Basemap and terrain: start with Cesium Ion's default terrain and imagery (requires a free Ion token in the configuration). Fallback when no token is set: OpenStreetMap imagery with no terrain. Self-hosted terrain/imagery is a later improvement.

### 7. Users, roles and sharing

- Accounts with authentication.
- Roles:
  - **Admin** — manage users, organizations and all layers.
  - **Publisher** — upload, process, publish and manage their own layers.
  - **Viewer** — view layers shared with them.
- Organizations/teams group users and share layers.
- Layer visibility:
  - **Private** — owner only
  - **Shared** — specific users or organizations
  - **Public** — anyone with the link
- Quotas on storage and processing per user/organization (configurable by admin).
- External client access:
  - Public layers: no authentication required.
  - Private layers: revocable API keys passed in the URL (works with CesiumJS).
  - ArcGIS Pro in v1: supports public layers. For private layers, users download the SLPK. (ArcGIS Pro expects Esri's own login flow for secured services. Supporting that is out of scope for v1.)

### 8. Layer lifecycle

- Re-uploading data to an existing layer creates a new version. The service URL stays the same.
- Deleting a layer removes the source files and all generated outputs.
- Users can download both the original upload and the generated SLPK.

### 9. Deployment

- Self-hosted with **Docker Compose**.
- Storage on **local disk**. The storage layer should be abstracted so S3/MinIO can be added later.
- Tile serving must handle many small requests efficiently (caching headers, optional reverse proxy/CDN in front).

## Acceptance test for v1

The system must work for city data from anywhere in the world, so the acceptance test does not depend on one dataset. It uses a **reference test corpus**: a set of openly licensed city datasets that covers different coordinate systems (UTM, State Plane, national grids), linear units (meters, US and international feet), vertical datums, hemispheres and latitudes, file structures and sizes. The New York City OBJ dataset can be one entry. The corpus is defined in the implementation plan and grows when new data fails.

For **every** dataset in the corpus:

1. Upload the dataset.
2. It is placed correctly on the map without manual positioning (coordinate system from `.prj`/EPSG, units and vertical datum handled).
3. It publishes as 3D Tiles and displays correctly in the built-in CesiumJS viewer, with attributes on click.
4. It publishes as an I3S SceneServer service and an SLPK, and both load in ArcGIS Pro in the same location, with the same attributes, as the original data.
5. Performance is acceptable at full city scale (target numbers to be defined, relative to input size).

## Out of scope for v1

- Additional input formats: FBX, IFC/BIM, CityGML, LAS/LAZ point clouds.
- Other I3S profiles (Integrated Mesh, Point Cloud, Building) and older 3D Tiles/I3S versions.
- 2D layers (approach to be decided: build in-house or integrate GeoServer).
- Self-hosted terrain and basemap services.
- S3/MinIO and CDN integration.
- Esri-compatible token authentication for secured services in ArcGIS Pro.
- Analysis and other features from Cesium Ion / ArcGIS Online (measurement, clipping, etc.).

## Future roadmap

1. More 3D input formats (FBX, IFC, CityGML, point clouds).
2. Self-hosted terrain and imagery (e.g. Copernicus DEM, OpenStreetMap tiles).
3. 2D layer support.
4. Object storage (S3/MinIO) and CDN support.
5. Additional services modeled on Cesium Ion / ArcGIS Online.

## Proposed defaults (to confirm)

- **License:** AGPL-3.0, which keeps the server open even when someone hosts it as a service. Alternative: Apache-2.0 if broad embedding by companies is preferred. Dependency licenses must be checked for compatibility.

## Open questions

1. Which georeferencing sidecars (`.prj`, `.xml`, others) appear in real-world city datasets, and in which forms (ESRI WKT, OGC WKT)? This confirms the georeferencing approach.
2. Where do feature attributes come from in real-world city OBJ datasets? Only an ID/name per object, or real fields (height, building ID) from sidecar files that must also be supported?
3. Tech stack: the backend is **Django** (decided). Conversion tools in Node.js (loaders.gl, 3d-tiles-tools) and C# (Obj2Tiles) run as external processes from the worker. Frontend: React + CesiumJS (proposed).
4. Solo project or open to contributors from the start?
5. Performance targets for the acceptance test (processing time, viewer frame rate, tile load times).
