import "cesium/Build/Cesium/Widgets/widgets.css";
import "./index.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { MapView } from "./MapView";

window.CESIUM_BASE_URL = CESIUM_BASE_URL;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MapView />
  </StrictMode>,
);
