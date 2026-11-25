export interface MapConfig {
  cesium_ion_token: string;
}

export async function fetchMapConfig(): Promise<MapConfig> {
  const response = await fetch("/api/map-config/");
  if (!response.ok) {
    throw new Error(`map-config request failed: ${response.status}`);
  }
  return response.json();
}
