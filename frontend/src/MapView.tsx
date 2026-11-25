import {
  Credit,
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

        // Hide all of Cesium's built-in widgets; the app will provide its own controls.
        // The credit/attribution area stays: OSM and Cesium ion require it.
        const common = {
          animation: false,
          timeline: false,
          baseLayerPicker: false,
          geocoder: false,
          homeButton: false,
          sceneModePicker: false,
          projectionPicker: false,
          navigationHelpButton: false,
          fullscreenButton: false,
          vrButton: false,
          infoBox: false,
          selectionIndicator: false,
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
            baseLayer: new ImageryLayer(
              new OpenStreetMapImageryProvider({ url: "https://tile.openstreetmap.org/" }),
            ),
            terrainProvider: new EllipsoidTerrainProvider(),
          });
          // No Cesium ion content is used here, so the ion logo isn't required.
          // The OpenStreetMap text credit next to it stays visible.
          const logo = viewer.cesiumWidget.creditContainer.querySelector<HTMLElement>(
            ".cesium-credit-logoContainer",
          );
          if (logo) logo.style.display = "none";
          // A plain-text credit in place of the logo.
          viewer.creditDisplay.addStaticCredit(
            new Credit(
              '<a href="https://cesium.com/platform/cesiumjs/" target="_blank" rel="noopener noreferrer">Powered by CesiumJS</a>',
              true,
            ),
          );
        }
      });

    return () => {
      cancelled = true;
      if (viewer && !viewer.isDestroyed()) viewer.destroy();
    };
  }, []);

  return <div ref={containerRef} className="map" />;
}
