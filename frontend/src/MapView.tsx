import {
  EllipsoidTerrainProvider,
  ImageryLayer,
  Ion,
  OpenStreetMapImageryProvider,
  Terrain,
  Viewer,
} from "cesium";
import { useEffect, useRef } from "react";

import { fetchMapConfig } from "./api";

/**
 * Full-screen CesiumJS globe.
 * With a Cesium Ion token (from the backend): Ion world imagery and terrain.
 * Without one (or if the backend is unreachable): OpenStreetMap imagery on the plain ellipsoid.
 */
export function MapView() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let viewer: Viewer | undefined;
    let cancelled = false;

    fetchMapConfig()
      .then((config) => config.cesium_ion_token)
      .catch((error) => {
        console.warn("Using OSM fallback map:", error);
        return "";
      })
      .then((token) => {
        if (cancelled || !containerRef.current) return;

        const common = {
          animation: false,
          timeline: false,
          baseLayerPicker: false,
          sceneModePicker: true,
          navigationHelpButton: false,
        };

        if (token) {
          Ion.defaultAccessToken = token;
          viewer = new Viewer(containerRef.current, {
            ...common,
            terrain: Terrain.fromWorldTerrain(),
          });
        } else {
          viewer = new Viewer(containerRef.current, {
            ...common,
            geocoder: false, // the default geocoder needs an Ion token
            baseLayer: new ImageryLayer(
              new OpenStreetMapImageryProvider({ url: "https://tile.openstreetmap.org/" }),
            ),
            terrainProvider: new EllipsoidTerrainProvider(),
          });
        }
      });

    return () => {
      cancelled = true;
      if (viewer && !viewer.isDestroyed()) viewer.destroy();
    };
  }, []);

  return <div ref={containerRef} className="map" />;
}
