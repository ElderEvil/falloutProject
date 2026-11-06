# Map

Wasteland map module. Displays a schematic SVG map of the wasteland with location markers (home vault, dweller origins, visited places, exploration discoveries) and seeded vault markers for future raid targets.

## Routes

- `/vault/:id/map` — MapView

## Key Files

- `views/MapView.vue` — main map view with SidePanel + polling
- `stores/map.ts` — map state management (locations, vault markers, polling)
- `services/mapService.ts` — API service layer for map endpoints
- `models/map.ts` — TypeScript type aliases for map schemas
- `components/WorldMap.vue` — inline SVG map with grid lines and markers
- `components/AtlasTerrain.vue` — renders terrain from the backend world snapshot
- `components/AtlasRoads.vue` — renders backend highway/country centerlines below fog;
  also renders sparse railroad lines with sleepers. No client generation or travel effects.
- `components/MapMarker.vue` — individual location/vault marker on the SVG
- `components/MarkerDetailModal.vue` — detail modal with dweller links
