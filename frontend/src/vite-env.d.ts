/// <reference types="vite/client" />

/** Injected by vite.config.ts: where Cesium's static Workers/Assets/Widgets are served. */
declare const CESIUM_BASE_URL: string;

interface Window {
  CESIUM_BASE_URL: string;
}
