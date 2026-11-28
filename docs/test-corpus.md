# Reference test corpus

Candidate datasets for the reference test corpus (task **P1.1** in [implementation-plan.md](../implementation-plan.md)). The corpus must cover many coordinate systems, units, height systems, locations, file structures and sizes. No single dataset is the target; every dataset in the corpus must pass.

**Status:** candidates only. Nothing has been downloaded or tested yet. Links and facts were checked on **2026-11-25** through the official pages and catalogue records cited in each entry.

How to read the facts:

- **✔ verified:** confirmed on the official page or catalogue record linked in the entry.
- **⚠ conflicting:** official sources disagree. Check the downloaded data before relying on it.
- **? unverified:** a likely value that no official source confirmed, usually because the site blocked automated access. Confirm it from the downloaded files (for example `metadata.xml`, `.prj` or the CityGML `srsName`).

Licenses must be rechecked on the download page before any data is added to the repository or CI.

---

## Summary

| # | Dataset | Region | Format we'd use | CRS | Height | Units | License |
|---|---|---|---|---|---|---|---|
| 1 | 3D BAG | Netherlands (whole country) | OBJ tiles; 3D Tiles (streamed) | EPSG:7415 (RD New + NAP) ✔ | NAP ✔ | m | CC BY 4.0 ✔ |
| 2 | Helsinki 3D | Finland, 60°N | OBJ; 3D Tiles (Kalasatama) | EPSG:3879 (ETRS-GK25) ✔ | N2000 ✔ | m | CC BY 4.0 ✔ |
| 3 | City of Melbourne Photomesh 2020 | Australia (south) | OBJ tiles (+ SLPK) | MGA Zone 55 ✔ (GDA94 or GDA2020 ?) | AHD ⚠ | m | CC BY ⚠ (3.0 AU or 4.0) |
| 4 | Montréal Bâtiments 3D 2020 | Canada | CityGML, 3DM, DWG | NAD83(CSRS) MTM zone 8 ✔ (EPSG:2950 ?) | CGVD28 ✔ | m | CC BY 4.0 ✔ |
| 5 | Berlin LoD2 | Germany | CityGML ? | EPSG:25833 ✔ | DHHN2016 ? | m | dl-de/zero-2.0 ✔ |
| 6 | swissBUILDINGS3D 3.0 Beta | Switzerland + Liechtenstein | CityGML 2.0, DWG, FileGDB | LV95 ✔ (EPSG:2056) | LN02 ✔ | m | swisstopo free-geodata terms ? |
| 7 | PLATEAU | Japan (300+ cities) | CityGML; 3D Tiles ? | EPSG:6697 (JGD2011, geographic + height) ✔ | JGD2011 height ✔ | degrees + m | CC BY 4.0–compatible ⚠ |
| 8 | NYC 3D Building Model (DCP) | USA | ? | NY State Plane Long Island ? (EPSG:2263) | NAVD88 ? | US survey ft ? | City open data ? |
| 9 | CesiumGS 3d-tiles-samples | Synthetic | 3D Tiles 1.0 / 1.1 | ECEF | — | m | per tileset ? |

---

## 1. 3D BAG (Netherlands)

- **Source:** [3dbag.nl](https://3dbag.nl/en/download) (downloads), [docs.3dbag.nl](https://docs.3dbag.nl/en/)
- **Producer:** TU Delft 3D geoinformation group and 3DGI.
- **Coverage:** every building in the Netherlands, about 10 million. ✔
- **Formats:** ✔
  - **OBJ:** downloadable per tile as a ZIP with three OBJ files, one for each LoD (1.2, 1.3, 2.2). See [OBJ delivery](https://docs.3dbag.nl/en/delivery/obj/).
  - **3D Tiles:** published as streamed tilesets, one per LoD, for example `https://data.3dbag.nl/v20250903/cesium3dtiles/lod22/tileset.json`. See [web services](https://docs.3dbag.nl/en/delivery/webservices/). No bulk 3D Tiles download is documented.
  - Also CityJSON, GeoPackage, WMS and WFS.
- **CRS:** EPSG:7415, Amersfoort / RD New + NAP height, for OBJ and CityJSON. The 3D Tiles are in EPSG:4978 (ECEF). ✔
- **Units:** metres. ✔
- **License:** CC BY 4.0, credited as "© 3DBAG by tudelft3d and 3DGI". See [copyright](https://docs.3dbag.nl/en/copyright/). ✔
- **What it covers in the corpus:**
  - a national grid (RD New) with a compound CRS
  - many small tiled OBJs
  - one object per building
  - untextured models
  - a ready-made 3D Tiles tileset to test **3D Tiles input** (P1.9)
  - the full country as a **very large** dataset

## 2. Helsinki 3D city models (Finland)

- **Source:** [Helsinki 3D (hel.fi)](https://hel.fi/en/decision-making/information-on-helsinki/maps-and-geospatial-data/helsinki-3d), [avoindata.suomi.fi dataset](https://avoindata.suomi.fi/data/en_GB/dataset/helsingin-3d-kaupunkimalli), [Kalasatama reality mesh resource](https://hri.fi/data/en/dataset/helsingin-3d-kaupunkimalli/resource/c5f9e149-7dc3-413c-b3c8-b71cc9d6dbfc). Downloads are at `kartta.hel.fi/3d/`.
- **Coverage:**
  - Kalasatama reality mesh (2017) ✔
  - citywide reality mesh (OBJ, 3MX) ✔
  - 3D buildings: a [separate dataset](https://avoindata.suomi.fi/data/en_GB/dataset/helsingin-3d-rakennukset)
- **Formats:**
  - **Kalasatama:** DAE, FBX, **OBJ**, **3D Tiles** and 3MX/3SM. ✔
  - **Citywide mesh:** OBJ and 3MX. ✔
- **CRS:** ETRS-GK25 (EPSG:3879). ✔
- **Height:** N2000. ✔
- **Units:** metres.
- **License:** CC BY 4.0. ✔
- **What it covers in the corpus:**
  - **high latitude** (60°N)
  - a textured photogrammetry mesh, one merged mesh rather than per-building objects
  - a national Gauss-Krüger grid
  - a small 3D Tiles set for import tests

Note: the hri.fi pages block automated access. The facts above come from the avoindata.suomi.fi and hel.fi pages.

## 3. City of Melbourne 3D Textured Mesh (Photomesh) 2020 (Australia)

- **Source:** [data.gov.au record](https://data.gov.au/data/dataset/c2b2351f-d129-4940-b37b-da1a37565734), [Victorian Government DataVic record](https://discover.data.vic.gov.au/dataset/city-of-melbourne-3d-textured-mesh-photomesh-2020). A 2018 edition also exists.
- **Coverage:** the whole municipality, split into tiles. It includes buildings, trees and terrain. ✔
- **Formats:** OBJ with `.mtl` and `.jpg` textures, plus SLPK. Each download also has `metadata.xml` (with the origin) and `Tile_Index.kml`. ✔
- **LoD:** levels L13 to L20, named in the OBJ file names. ✔
- **Size:** the 2018 ZIP is 9.7 GB. The 2020 size is not stated.
- **CRS:** MGA Zone 55. ✔ Whether it is GDA94 (EPSG:28355) or GDA2020 (EPSG:7855) is **unverified**; check `metadata.xml`.
- **Height:** Australian Height Datum (AHD). ⚠ One record states it and another leaves it blank.
- **Resolution:** ⚠ records disagree between 7.5 cm and 2 cm ground sample distance.
- **Units:** metres.
- **License:** ⚠ CC BY 3.0 Australia on data.gov.au; "CC BY" on DataVic.
- **What it covers in the corpus:**
  - **southern hemisphere**
  - many tiled, textured OBJs, with an origin offset taken from a sidecar file (`metadata.xml`, not a `.prj`)
  - an existing SLPK for **SLPK input** tests (P1.8)
  - a large dataset

## 4. Montréal Bâtiments 3D 2020 (Canada)

- **Source:** [Données Québec dataset](https://www.donneesquebec.ca/recherche/dataset/vmtl-batiments-3d-2020-maquette-lod2-avec-textures). Older 2009, 2013 and 2016 models also exist.
- **Coverage:** the tiles listed cover the Ville-Marie, Outremont and Côte-des-Neiges–Notre-Dame-de-Grâce boroughs. ✔ Whether other boroughs are included is not confirmed.
- **Formats:** CityGML LoD2 with textures, 3DM (Rhino) with textures, and DWG without textures for Ville-Marie. ✔ OBJ is not offered.
- **CRS:** NAD83(CSRS) (98), MTM zone 8 projection. ✔ It is likely EPSG:2950. ?
- **Height:** CGVD28. ✔
- **Accuracy:** roofs are ±30–40 cm; walls are extrapolated to 3 m below ground. ✔
- **Units:** metres.
- **License:** CC BY 4.0. ✔
- **What it covers in the corpus:**
  - North America outside the US
  - an MTM projection
  - an older vertical datum (CGVD28)
  - per-building, textured LoD2 models
  - an OBJ test case after converting the CityGML, until CityGML input is supported

## 5. Berlin 3D building models LoD2 (Germany)

- **Source:** [Berlin geodata catalogue record](https://gdi.berlin.de/geonetwork/srv/api/records/3c7c49af-00a4-3bcd-bc00-20e7f0f1b7bf), [INSPIRE ATOM download feed](https://gdi.berlin.de/data/a_lod2/atom/)
- **Coverage:** the whole state of Berlin, within the WGS84 bounding box N 52.69, S 52.33, E 13.77, W 13.08. ✔
- **Formats:** the catalogue record doesn't name the file format. It is likely CityGML, which the BKG nationwide LoD2 product uses. ? OBJ is not confirmed.
- **CRS:** EPSG:25833 (ETRS89 / UTM zone 33N). ✔
- **Height:** not stated. It is likely DHHN2016. ?
- **Units:** metres.
- **License:** [Datenlizenz Deutschland – Zero 2.0](https://www.govdata.de/dl-de/zero-2-0). ✔
- **What it covers in the corpus:**
  - UTM
  - per-building LoD2 models
  - a large city

## 6. swissBUILDINGS3D 3.0 Beta (Switzerland)

- **Source:** [swisstopo product page](https://www.swisstopo.admin.ch/en/landscape-model-swissbuildings3d-3-0-beta)
- **Coverage:** Switzerland and Liechtenstein. ✔ The product is a beta, with ±30–50 cm accuracy. ✔
- **Formats and sizes:** ✔
  - DWG: about 40 MB per tile, about 160 GB for the whole country
  - ESRI File Geodatabase: about 16 MB per tile, about 50 GB for the whole country
  - CityGML 2.0: only buildings with an EGID, about 120 MB per tile
  - OBJ and 3D Tiles are not offered
- **CRS:** LV95 (EPSG:2056). ✔
- **Height:** LN02. ✔ The page also mentions a past LHN95 transformation error.
- **Units:** metres.
- **License:** free of charge. The terms are in swisstopo's [terms of use for free geodata](https://www.swisstopo.admin.ch/en/terms-of-use-free-geodata-and-geoservices), which I haven't read. ?
- **What it covers in the corpus:**
  - a national grid
  - a non-ellipsoidal national height system (LN02), which tests vertical datum conversion
  - a **full national dataset in the tens to hundreds of GB**

## 7. PLATEAU (Japan)

- **Source:** [MLIT PLATEAU open data](https://www.mlit.go.jp/plateau/opendata) and the per-city downloads on the [G-spatial Information Center](https://www.geospatial.jp/ckan/dataset/plateau)
- **Coverage:** 306 locations, last updated 2026-05-11. ✔
- **Formats:** CityGML is the main format. ✔ The OpenStreetMap wiki also lists 3D Tiles, GeoPackage and JSON downloads. MLIT documents 3D Tiles as output of its [PLATEAU GIS Converter](https://www.mlit.go.jp/plateau/learning/tpc30/). Whether 3D Tiles can be downloaded directly for each city is **unverified** because the city pages block automated access. ?
- **CRS:** EPSG:6697 (JGD2011 geographic, latitude/longitude plus height), or EPSG:6668 without height. ✔ See [MLIT TOPIC 3-4](https://www.mlit.go.jp/plateau/learning/tpc03-4/).
- **Height:** JGD2011 vertical. ✔
- **Units:** degrees horizontally, metres vertically.
- **License:** described as CC BY 4.0–compatible and free for commercial use, but the terms vary by dataset. ⚠ Check each city's page and the MLIT site policy.
- **What it covers in the corpus:**
  - a **geographic** source CRS instead of a projected one
  - an **axis-order trap**: some tools swap latitude and longitude for EPSG:6697
  - non-ASCII (Japanese) attribute names and values
  - very large national coverage

## 8. NYC 3D Building Model (USA)

- **Source:**
  - NYC Department of City Planning (DCP): [NYC 3D Model by Community District](https://www.nyc.gov/site/planning/data-maps/open-data/dwn-nyc-3d-model-download.page). The page has moved; the new address is not confirmed.
  - [metadata PDF](https://www.nyc.gov/assets/planning/download/pdf/data-maps/open-data/nyc-3d-model-metadata.pdf)
  - [data.gov record](https://catalog.data.gov/dataset/3-d-building-model)
- **Coverage:** every building in the 2014 aerial survey, split into 59 community districts with base layers. ✔ (data.gov record)
- **Formats:** data.gov says three formats are available, but doesn't name them. ? Check whether OBJ is one of them.
- **CRS:** likely NY State Plane Long Island, in US survey feet (EPSG:2263). ?
- **Height:** likely NAVD88. ?
- **Units:** likely **US survey feet**. ?
- **License:** NYC open data, "for informational purposes only". ?
- **What it covers in the corpus:**
  - US State Plane
  - **US survey feet**
  - one object per building

This is the dataset the scope mentions. Per the design principle, it is one entry and not the target.

## 9. CesiumGS 3d-tiles-samples (synthetic)

- **Source:** [github.com/CesiumGS/3d-tiles-samples](https://github.com/CesiumGS/3d-tiles-samples)
- **Contents:** ✔
  - 3D Tiles **1.1** samples: MetadataGranularities, SparseImplicitQuadtree, SparseImplicitOctree, MultipleContents, BoundingBoxTests and TilesetWithFullMetadata
  - **1.0** samples: TilesetWithDiscreteLOD, TilesetWithRequestVolume and TilesetWithTreeBillboards
  - glTF samples using `EXT_mesh_features` and `EXT_structural_metadata`
- **License:** no repository-wide license confirmed. Some tilesets have usage notes in their own README. ? Check each tileset folder.
- **What it covers in the corpus:**
  - small, fast **CI** fixtures for 3D Tiles input (P1.9) and validation (P1.11)
  - reference output for feature IDs and metadata (P4.4)

---

## Not usable: streaming only

These can be viewed but not downloaded, cached or re-served under their terms, so they can't be corpus entries:

- **Google Photorealistic 3D Tiles**
- **Cesium OSM Buildings** and **Cesium ion's Japan 3D Buildings** (built from PLATEAU). Use the PLATEAU source data instead.

## Coverage against P1.1

| P1.1 requirement | Covered by | Gap |
|---|---|---|
| UTM | Berlin | — |
| US State Plane | NYC ? | Confirm NYC's CRS |
| National grids | RD New (3D BAG), ETRS-GK25 (Helsinki), LV95 (Swiss), MTM (Montréal) | British National Grid, Lambert-93 not yet included |
| CRS needing a grid-based datum shift | RD New, LV95 and NAD83(CSRS) are candidates | Confirm which transformations need PROJ grids |
| `.prj` in ESRI WKT and OGC WKT | — | **Gap:** none of these confirms a `.prj`. Create synthetic `.prj` variants |
| Metres | All except NYC | — |
| US survey feet | NYC ? | Confirm |
| International feet | — | **Gap:** create a synthetic sample |
| Northern / southern hemisphere | Most / Melbourne | — |
| High latitude | Helsinki (60°N) | Something further north would be stronger |
| Near the antimeridian | — | **Gap:** for example New Zealand (Chatham Islands) or Fiji, or synthetic |
| City spanning two UTM zones | — | **Gap** |
| Ellipsoidal heights | 3D BAG 3D Tiles (ECEF) | Need a source dataset with ellipsoidal Z |
| Orthometric heights | NAP, N2000, AHD, CGVD28, LN02, NAVD88 ? | — |
| No reliable Z | — | **Gap:** synthetic |
| One large OBJ vs many tiled OBJs | Helsinki citywide mesh vs 3D BAG / Melbourne tiles | — |
| One object per building vs one merged mesh | 3D BAG, NYC vs Helsinki, Melbourne meshes | — |
| Textured vs untextured | Helsinki, Melbourne, Montréal vs 3D BAG | — |
| Missing `.prj` | Melbourne (origin in `metadata.xml`) | — |
| Non-ASCII names | PLATEAU | Needs CityGML → OBJ conversion |
| Small / district / full city (tens of GB) | 3d-tiles-samples, single tiles / Kalasatama / Melbourne, Swiss, 3D BAG | — |

## Next steps

1. Download one small tile from each dataset and record the real CRS, height system, units and file layout. That replaces every ? above.
2. Read each license on its download page and record the exact attribution text.
3. Fill the gaps: British National Grid or Lambert-93, international feet, the antimeridian, a city spanning two UTM zones, a source with ellipsoidal heights, no Z values, and ESRI/OGC `.prj` variants. Use synthetic data where no open dataset exists.
4. Pick the small CI subset.
