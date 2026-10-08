<script setup lang="ts">
import { computed, ref, toRef } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { formatRemaining } from '@/modules/exploration/composables/useExplorationProgress'
import type {
  DiscoveryRouteRead,
  ExpeditionSiteMarkerRead,
  ExplorerTrack,
  MarkerClickPayload,
  PlayerVaultMarkerRead,
  WastelandLocationWithDwellers,
  VaultMarkerRead,
} from '../models/map'
import { EXPEDITION_SITE_ICON, locationMarkerIcon } from '../models/markerTypeMeta'
import { markerArtDataUrl } from '../utils/markerIcons'
import MapClusterMarker from './MapClusterMarker.vue'
import MapMarker from './MapMarker.vue'
import MapLegend from './MapLegend.vue'
import MarkerListPanel from './MarkerListPanel.vue'
import AtlasTerrain from './AtlasTerrain.vue'
import FogLayer from './FogLayer.vue'
import { registryToTile, ATLAS_TILES } from '../utils/atlasProjection'
import { computeExploredMask, isExploredTile } from '../utils/fog'
import { useMapSpread } from '../composables/useMapSpread'
import { useMarkerSelection } from '../composables/useMarkerSelection'
import { smoothPath } from '../utils/tracePath'
import { useMapZoomPan, MAX_ZOOM } from '../composables/useMapZoomPan'
import { useMapStore } from '../stores/map'
import { isKnownLocation } from '../utils/visibility'
import { isMarkerVisible } from '../utils/declutter'
import { clusterMarkers, type MarkerCluster } from '../utils/clusterMarkers'
import { explorerHeading } from '../utils/explorerHeading'

interface Props {
  locations: WastelandLocationWithDwellers[]
  vaultMarkers: VaultMarkerRead[]
  playerVaults?: PlayerVaultMarkerRead[]
  discoveryRoutes?: DiscoveryRouteRead[]
  expeditionSites?: ExpeditionSiteMarkerRead[]
  explorerTracks?: ExplorerTrack[]
  fogDisabled?: boolean
  selectedMarkerId: string | null
}

const props = withDefaults(defineProps<Props>(), {
  playerVaults: () => [],
  discoveryRoutes: () => [],
  expeditionSites: () => [],
  explorerTracks: () => [],
  fogDisabled: false,
})

const emit = defineEmits<{
  (e: 'marker-click', payload: MarkerClickPayload): void
  (e: 'update:selectedMarkerId', value: string | null): void
  /** Own-vault marker clicked: open its summary panel instead of navigating. */
  (e: 'vault-info', vaultId: string): void
}>()

// ── Marker visibility filter ─────────────────────────────────────
// The index stays known-only. The SVG shows known markers plus dimmed "?" hint
// pins, but only where the derived fog of war has been explored — fogged tiles
// reveal nothing. The home vault is always revealed.
const knownLocations = computed(() => props.locations.filter(isKnownLocation))

// Fog/mask grid resolution follows the backend snapshot when loaded, so fog
// cells align with rendered terrain cells; defaults preserve current behavior.
const gridTiles = computed(() => mapStore.worldSnapshot?.width ?? ATLAS_TILES)

const exploredMask = computed(() =>
  computeExploredMask(
    {
      home: props.locations.find((loc) => loc.type === 'home_vault') ?? null,
      discovered: props.locations.filter(isKnownLocation),
      trailPoints: props.discoveryRoutes.flatMap((route) => route.points),
      // Movement trails (every point location-free) interpolate their
      // segments; legacy discovery hops keep circle-only reveals.
      travelRoutes: props.discoveryRoutes
        .filter((route) => route.points.length > 0 && route.points.every((point) => point.location_id == null))
        .map((route) => route.points),
    },
    gridTiles.value,
  ),
)

function isExploredLocation(loc: { coord_x: number; coord_y: number }): boolean {
  return isExploredTile(
    exploredMask.value,
    registryToTile(loc.coord_x, gridTiles.value),
    registryToTile(loc.coord_y, gridTiles.value),
    gridTiles.value,
  )
}

const visibleLocations = computed(() =>
  props.fogDisabled
    ? props.locations
    : props.locations.filter(
        (loc) => !(loc.type === 'visited' && loc.dwellers.length < 2) && isExploredLocation(loc),
      ),
)

function isExploredCoord(coord: { coord_x: number; coord_y: number }): boolean {
  return isExploredTile(
    exploredMask.value,
    registryToTile(coord.coord_x, gridTiles.value),
    registryToTile(coord.coord_y, gridTiles.value),
    gridTiles.value,
  )
}

// Only the player's own vaults render with identity; every other vault — other
// players' and the seeded NPC signals — is an anonymous hint, and only where the
// fog has been lifted, so the shared atlas does not flood the map with unrelated
// vaults.
const ownPlayerVaults = computed(() => {
  const homeVaultId = props.locations.find((loc) => loc.type === 'home_vault')?.vault_id
  return props.playerVaults.filter((pv) => pv.is_mine && pv.vault_id !== homeVaultId)
})

const foreignVaultHints = computed(() =>
  [
    ...props.playerVaults
      .filter((pv) => !pv.is_mine)
      .map((pv) => ({ key: `pv-${pv.vault_id}`, coord_x: pv.coord_x, coord_y: pv.coord_y })),
    ...props.vaultMarkers.map((vm) => ({
      key: `vm-${vm.name}`,
      coord_x: vm.coord_x,
      coord_y: vm.coord_y,
    })),
  ].filter((hint) => props.fogDisabled || isExploredCoord(hint)),
)

// Expeditions start at the home vault — anchor every trail there.
const homeCoords = computed<[number, number]>(() => {
  const home = props.locations.find((loc) => loc.type === 'home_vault')
  return home ? [home.coord_x, home.coord_y] : [80, 80]
})

// Amplitude 0 removes the hand-drawn wobble; steps 1 keeps only the real
// waypoints, so each trail renders as clean straight segments between them.
// Only in-progress runs draw a trail; the fog still consumes every route.
const discoveryRouteLines = computed(() =>
  props.discoveryRoutes
    .filter((route) => route.is_active)
    .map((route) =>
      smoothPath([
        homeCoords.value,
        ...route.points.map((point): [number, number] => [point.coord_x, point.coord_y]),
      ])
    )
)

// ── Explorer tracking ────────────────────────────────────────────────────
// Dispatched runs mark their target location as "exploring"; free-roam runs
// get a small last-known-position marker at the end of their discovery trail.
const exploringByLocation = computed(() => {
  const byLocation = new Map<string, string>()
  for (const track of props.explorerTracks) {
    if (!track.targetLocationId) continue
    byLocation.set(
      track.targetLocationId,
      track.dwellerName ? `Exploring — ${track.dwellerName}` : 'Dispatching'
    )
  }
  return byLocation
})

const freeRoamTracks = computed(() =>
  props.explorerTracks.filter((track) => !track.targetLocationId && track.lastKnown)
)

// Heading chevrons for the free-roam markers: trail vector when the run has a
// usable outbound trail, otherwise the bearing back home. Tracks with neither
// keep the bare thumbnail/marker (no chevron).
const freeRoamChevrons = computed(() => {
  const routesByExploration = new Map(
    props.discoveryRoutes.map((route) => [route.exploration_id, route])
  )
  const home = { coord_x: homeCoords.value[0], coord_y: homeCoords.value[1] }
  return freeRoamTracks.value.flatMap((track) => {
    const heading = explorerHeading(track, routesByExploration.get(track.explorationId), home)
    return heading === null ? [] : [{ track, heading }]
  })
})

// ── Expedition site state ────────────────────────────────────────────────
function siteStatus(site: ExpeditionSiteMarkerRead): string {
  const level = `LVL ${site.min_dweller_level}`
  const rooms = `${site.room_total} ROOMS`
  if (site.block_reason === 'open') return `IN PROGRESS · ${level} · ${rooms}`
  if (site.cleared) {
    const cooldown =
      site.cooldown_remaining_seconds > 0
        ? `COOLDOWN ${formatRemaining(site.cooldown_remaining_seconds)} · `
        : ''
    return `CLEARED · ${cooldown}${level} · ${rooms}`
  }
  return `READY · ${level} · ${rooms}`
}

// ── Zoom & Pan ────────────────────────────────────────────────────────
const {
  zoom,
  isZoomed,
  isDragging,
  viewBox,
  zoomIn,
  zoomOut,
  resetZoom,
  focusOnMarker,
  onWheel,
  onDragStart,
  onDragMove,
  onDragEnd,
  isPinching,
  onTouchStart,
  onTouchMove,
  onTouchEnd,
} = useMapZoomPan()

const mapStore = useMapStore()
const svgRef = ref<SVGSVGElement | null>(null)
const vaultMarkers = toRef(props, 'vaultMarkers')

function onOwnVaultClick(vault: PlayerVaultMarkerRead): void {
  emit('vault-info', vault.vault_id)
}

const groupIconByKey = computed(
  () => new Map(mapStore.placeGroups.map((group) => [group.key, group.icon])),
)

const { spreadMap, getSpread } = useMapSpread(visibleLocations, vaultMarkers)

// ── Declutter ─────────────────────────────────────────────────────────
// Primary markers (home vault, selection, discoveries, active explorers and
// expedition sites) always render — dense discoveries collapse into cluster
// badges instead of being hidden. Secondary locations and anonymous vault
// hints stay hidden at overview zoom and reappear as the player zooms in.
const renderedLocations = computed(() =>
  visibleLocations.value.filter((loc) =>
    isMarkerVisible(
      {
        type: loc.type,
        selected: props.selectedMarkerId === `loc-${loc.id}`,
        exploring: exploringByLocation.value.has(loc.id),
      },
      zoom.value,
    ),
  ),
)

const renderedVaultHints = computed(() =>
  foreignVaultHints.value.filter(() => isMarkerVisible({ type: 'vault' }, zoom.value)),
)

const selectedMarkerId = computed<string | null>({
  get: () => props.selectedMarkerId,
  set: (value) => emit('update:selectedMarkerId', value),
})

const { hasDragMoved, onLocationClick, onSiteClick, onPanelMarkerSelect } = useMarkerSelection(
  selectedMarkerId,
  spreadMap,
  focusOnMarker,
  emit,
)

// ── Discovery clustering ──────────────────────────────────────────────
// Discoveries render at every zoom, so on a dense atlas their count is what
// swamps the map. Grid cells shrink as the map zooms in, so a badge expands
// into individual, fully interactive markers on its own; a badge click zooms
// one step further, centered on the cluster. Selection and active explorers
// stay pinned individually so their rings and labels never disappear.
const locationByMarkerId = computed(
  () => new Map(renderedLocations.value.map((loc) => [`loc-${loc.id}`, loc])),
)

const clusterableDiscoveries = computed(() =>
  renderedLocations.value
    .filter(
      (loc) =>
        loc.type === 'discovery' &&
        loc.is_unlocked !== false &&
        selectedMarkerId.value !== `loc-${loc.id}` &&
        !exploringByLocation.value.has(loc.id),
    )
    .map((loc) => {
      const spread = getSpread(`loc-${loc.id}`, loc.coord_x, loc.coord_y)
      return { id: `loc-${loc.id}`, x: spread.renderX, y: spread.renderY }
    }),
)

const discoveryClusters = computed(() =>
  clusterMarkers(clusterableDiscoveries.value, { zoom: zoom.value }),
)

const clusterBadges = computed(() =>
  discoveryClusters.value.filter((cluster) => cluster.members.length > 1),
)

const clusteredIds = computed(
  () =>
    new Set(
      clusterBadges.value.flatMap((cluster) => cluster.members.map((member) => member.id)),
    ),
)

const renderedLocationsIndividual = computed(() =>
  renderedLocations.value.filter((loc) => !clusteredIds.value.has(`loc-${loc.id}`)),
)

function clusterHasUnseen(cluster: MarkerCluster): boolean {
  return cluster.members.some((member) => {
    const loc = locationByMarkerId.value.get(member.id)
    return loc ? mapStore.isUnseenDiscovery(loc) : false
  })
}

function onClusterClick(cluster: MarkerCluster) {
  if (hasDragMoved.value) return
  focusOnMarker(cluster.x, cluster.y, Math.min(MAX_ZOOM, zoom.value + 1))
}

function getSvgRect(): DOMRect {
  return svgRef.value?.getBoundingClientRect() ?? new DOMRect(0, 0, 0, 0)
}

function handleWheel(event: WheelEvent) {
  onWheel(event, getSvgRect())
}

function handleMouseDown(event: MouseEvent) {
  if (!isZoomed.value) return
  hasDragMoved.value = false
  onDragStart(event, getSvgRect())
}

function handleMouseMove(event: MouseEvent) {
  if (isDragging.value) {
    onDragMove(event, getSvgRect())
    hasDragMoved.value = true
  }
}

function handleMouseUp() {
  onDragEnd()
}

function handleTouchStart(event: TouchEvent) {
  hasDragMoved.value = false
  onTouchStart(event, getSvgRect())
}

function handleTouchMove(event: TouchEvent) {
  if (isDragging.value || isPinching.value) {
    onTouchMove(event, getSvgRect())
    hasDragMoved.value = true
  }
}

function handleTouchEnd(event: TouchEvent) {
  onTouchEnd(event)
}


</script>

<template>
  <div class="world-map-layout">
    <div
      class="world-map-container crt-screen touch-none"
      :class="{ 'is-zoomed': isZoomed, 'is-dragging': isDragging }"
      @mousemove="handleMouseMove"
      @mouseup="handleMouseUp"
      @mouseleave="handleMouseUp"
      @wheel.prevent="handleWheel"
      @touchstart="handleTouchStart"
      @touchmove="handleTouchMove"
      @touchend="handleTouchEnd"
      @touchcancel="handleTouchEnd"
    >
      <svg
        ref="svgRef"
        :viewBox="viewBox"
        xmlns="http://www.w3.org/2000/svg"
        class="world-map-svg"
        focusable="false"
        @mousedown="handleMouseDown"
      >
        <!-- Terrain layer (bottom — behind markers): biomes, rivers, roads -->
        <AtlasTerrain />

        <!-- Fog of war: derived explored mask over the terrain -->
        <FogLayer v-if="!fogDisabled" :explored="exploredMask" :tiles="gridTiles" />

        <!-- Discovery routes: dark casing under the accent line so trails read
             as roads (still above terrain/fog and below markers) -->
        <g
          v-for="(route, i) in discoveryRouteLines"
          :key="`route-${i}`"
          class="discovery-route"
          fill="none"
        >
          <path :d="route" class="discovery-route-casing" />
          <path :d="route" class="discovery-route-line" />
        </g>

        <!-- Location markers (spread-adjusted positions; discoveries inside a
             cluster are rendered as the badge below instead) -->
        <MapMarker
          v-for="loc in renderedLocationsIndividual"
          :key="`loc-${loc.id}`"
          :x="getSpread(`loc-${loc.id}`, loc.coord_x, loc.coord_y).renderX"
          :y="getSpread(`loc-${loc.id}`, loc.coord_x, loc.coord_y).renderY"
          :name="loc.name"
          :type="loc.type"
          :icon="locationMarkerIcon(loc.type, loc.group_key, groupIconByKey)"
          :art-src="markerArtDataUrl(loc.group_key)"
          :is_unlocked="loc.is_unlocked"
          :unseen="mapStore.isUnseenDiscovery(loc)"
          :selected="selectedMarkerId === `loc-${loc.id}`"
          :cleared="loc.clear_state?.cleared ?? false"
          :exploring="exploringByLocation.has(loc.id)"
          :status="exploringByLocation.get(loc.id)"
          @click="onLocationClick(loc)"
        />

        <!-- Discovery clusters: one ×N badge per dense cell, clickable to zoom
             in until the cluster splits back into individual markers -->
        <MapClusterMarker
          v-for="cluster in clusterBadges"
          :key="cluster.id"
          :x="cluster.x"
          :y="cluster.y"
          :count="cluster.members.length"
          :unseen="clusterHasUnseen(cluster)"
          @click="onClusterClick(cluster)"
        />

        <!-- Your vaults (identity shown) -->
        <MapMarker
          v-for="pv in ownPlayerVaults"
          :key="`pv-${pv.vault_id}`"
          :x="pv.coord_x"
          :y="pv.coord_y"
          :name="`Vault ${pv.number}`"
          type="home_vault"
          label="Your Vault"
          :status="`View details`"
          @click="onOwnVaultClick(pv)"
        />

        <!-- Other vaults: anonymous hints, only where the fog is lifted and
             the map is zoomed past the declutter threshold -->
        <MapMarker
          v-for="hint in renderedVaultHints"
          :key="hint.key"
          :x="hint.coord_x"
          :y="hint.coord_y"
          name="Unknown vault"
          type="vault"
          icon="mdi:help-circle-outline"
          label="Unexplored signal"
          :interactive="false"
        />

        <!-- Expedition site markers (fixed coordinates, already viewBox-scaled) -->
        <MapMarker
          v-for="site in expeditionSites"
          :key="`site-${site.id}`"
          :x="site.coord_x"
          :y="site.coord_y"
          :name="site.name"
          type="expedition_site"
          :icon="EXPEDITION_SITE_ICON"
          :art-src="markerArtDataUrl(site.id)"
          :cleared="site.cleared"
          :status="siteStatus(site)"
          :selected="selectedMarkerId === `site-${site.id}`"
          @click="onSiteClick(site)"
        />

        <!-- Free-roam explorer last-known positions (non-interactive) -->
        <MapMarker
          v-for="track in freeRoamTracks"
          :key="`explorer-${track.explorationId}`"
          :x="track.lastKnown!.coord_x"
          :y="track.lastKnown!.coord_y"
          :name="track.dwellerName || 'Explorer'"
          type="explorer"
          icon="mdi:walk"
          :art-src="track.dwellerThumbnailUrl ?? null"
          label="Explorer"
          :status="track.dwellerName ? `Last known — ${track.dwellerName}` : 'Last known position'"
          :interactive="false"
        />

        <!-- Travel-direction chevrons for free-roam explorers: a small accent
             wedge rotated around the marker center. aria-hidden + non-interactive. -->
        <g
          v-for="entry in freeRoamChevrons"
          :key="`explorer-heading-${entry.track.explorationId}`"
          class="explorer-heading"
          :transform="`translate(${entry.track.lastKnown!.coord_x}, ${entry.track.lastKnown!.coord_y}) rotate(${entry.heading})`"
          aria-hidden="true"
        >
          <path class="explorer-heading-chevron" d="M -1.7 -3.4 L 0 -5.5 L 1.7 -3.4" />
        </g>
      </svg>

      <!-- Zoom controls overlay -->
      <div class="zoom-controls" role="group" aria-label="Map zoom controls">
        <Button variant="ghost" size="xs" aria-label="Zoom in" class="zoom-btn" @click="zoomIn()">
          <Icon icon="mdi:plus" class="zoom-icon" />
        </Button>
        <Button
          variant="ghost"
          size="xs"
          aria-label="Zoom out"
          class="zoom-btn"
          @click="zoomOut()"
        >
          <Icon icon="mdi:minus" class="zoom-icon" />
        </Button>
        <Button
          variant="ghost"
          size="xs"
          :disabled="!isZoomed"
          aria-label="Reset zoom"
          class="zoom-btn"
          @click="resetZoom()"
        >
          <Icon icon="mdi:arrow-expand-all" class="zoom-icon" />
        </Button>
        <span v-if="isZoomed" class="zoom-level">{{ Math.round(zoom * 100) }}%</span>
      </div>

      <!-- Legend overlay -->
      <MapLegend />
    </div>

    <!-- Persistent desktop location index -->
    <MarkerListPanel
      :docked="true"
      :locations="knownLocations"
      :vault-markers="[]"
      :expedition-sites="expeditionSites"
      :place-groups="mapStore.placeGroups"
      :selected-marker-id="selectedMarkerId"
      @marker-select="onPanelMarkerSelect"
    />
  </div>
</template>

<style scoped>
.world-map-layout {
  display: grid;
  grid-template-columns: auto minmax(12rem, 14rem);
  align-items: start;
  gap: 0.75rem;
  width: fit-content;
  max-width: min(80rem, 100%);
}

.world-map-container {
  width: var(--map-pane-size);
  max-width: min(100%, calc(100vw - 2rem));
  aspect-ratio: 1 / 1;
  border: 1px solid var(--color-theme-primary);
  background-color: var(--color-terminal-background);
  box-shadow:
    inset 0 0 40px rgba(0, 0, 0, 0.6),
    0 0 10px var(--color-theme-glow);
  overflow: hidden;
  position: relative;
}

.world-map-container.is-zoomed {
  cursor: grab;
}

/* Locked ("Unknown Location") labels stay hidden at overview zoom to avoid
   wallpapering the map; zooming in means intent to inspect, so reveal them. */
.world-map-container.is-zoomed :deep(.map-marker.marker-locked .marker-label) {
  opacity: 1;
}

.world-map-container.is-dragging {
  cursor: grabbing;
}

.world-map-container.is-dragging :deep(.map-marker) {
  cursor: grabbing;
}

.world-map-svg {
  width: 100%;
  height: 100%;
  display: block;
}

/* Cased discovery routes: a wider, near-opaque dark under-stroke reads as a
   road edge; the brighter accent line on top keeps the trail legible wherever
   routes cross each other or busy terrain. */
.discovery-route {
  pointer-events: none;
}

.discovery-route-casing {
  stroke: color-mix(in srgb, var(--color-terminal-background) 92%, transparent);
  stroke-width: 1.3;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 2 1.4;
}

.discovery-route-line {
  stroke: var(--color-theme-accent);
  stroke-width: 0.45;
  opacity: 0.8;
  stroke-linecap: round;
  stroke-dasharray: 2 1.4;
}

/* Free-roam explorer travel direction: accent chevron outside the marker ring. */
.explorer-heading {
  pointer-events: none;
}

.explorer-heading-chevron {
  fill: none;
  stroke: var(--color-theme-accent);
  stroke-width: 0.6;
  stroke-linecap: round;
  stroke-linejoin: round;
}



/* Zoom controls overlay */
.zoom-controls {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 10;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.zoom-btn {
  width: 28px;
  height: 28px;
  padding: 0 !important;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--color-surface) 90%, transparent);
  border: 1px solid var(--color-theme-primary) !important;
  border-radius: 2px;
  min-height: 0 !important;
}

.zoom-icon {
  width: 16px;
  height: 16px;
}

.zoom-level {
  font-family: var(--font-family-mono);
  font-size: 9px;
  color: var(--color-theme-primary);
  opacity: 0.6;
  margin-top: 2px;
  letter-spacing: 0.05em;
}

@media (max-width: 64rem) {
  .world-map-layout {
    grid-template-columns: minmax(0, 1fr);
    max-width: 800px;
  }

  .marker-list-wrapper :deep(.marker-list-panel) {
    height: auto;
    min-height: 14rem;
  }
}
</style>
