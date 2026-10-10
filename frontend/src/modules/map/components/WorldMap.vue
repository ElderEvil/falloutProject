<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { Icon } from '@iconify/vue'
import { useMediaQuery } from '@vueuse/core'
import { Button } from '@/core/components/ui/button'
import { formatRemaining } from '@/modules/exploration/composables/useExplorationProgress'
import type {
  DiscoveryRouteRead,
  ExpeditionSiteMarkerRead,
  ExplorerTrack,
  MarkerClickPayload,
  PlaceGroup,
  PlayerVaultMarkerRead,
  WastelandLocationWithDwellers,
  VaultMarkerRead,
} from '../models/map'
import { EXPEDITION_SITE_ICON, locationMarkerIcon } from '../models/markerTypeMeta'
import { groupColor } from '../models/groupColors'
import MapClusterMarker from './MapClusterMarker.vue'
import MapMarker from './MapMarker.vue'
import MapLegend from './MapLegend.vue'
import MarkerListPanel from './MarkerListPanel.vue'
import AtlasTerrain from './AtlasTerrain.vue'
import FogLayer from './FogLayer.vue'
import { registryToTile, ATLAS_TILES } from '../utils/atlasProjection'
import { computeExploredMask, isExploredTile } from '../utils/fog'
import { useMarkerSelection } from '../composables/useMarkerSelection'
import { smoothPath } from '../utils/tracePath'
import { useMapZoomPan, MAX_ZOOM } from '../composables/useMapZoomPan'
import { useMapStore } from '../stores/map'
import { isKnownLocation } from '../utils/visibility'
import { isMarkerVisible } from '../utils/declutter'
import { clusterMarkers, type MarkerCluster } from '../utils/clusterMarkers'
import { buildRoutesByExploration } from '../utils/explorerTracks'
import { explorerHeading } from '../utils/explorerHeading'
import { matchesSiteTypeFilter } from '../utils/siteFilter'

interface Props {
  locations: WastelandLocationWithDwellers[]
  vaultMarkers: VaultMarkerRead[]
  playerVaults?: PlayerVaultMarkerRead[]
  discoveryRoutes?: DiscoveryRouteRead[]
  expeditionSites?: ExpeditionSiteMarkerRead[]
  explorerTracks?: ExplorerTrack[]
  fogDisabled?: boolean
  groupColors?: boolean
  siteTypeFilter?: string | null
  readyLocationIds?: string[] | null
  selectedMarkerId: string | null
}

const props = withDefaults(defineProps<Props>(), {
  playerVaults: () => [],
  discoveryRoutes: () => [],
  expeditionSites: () => [],
  explorerTracks: () => [],
  fogDisabled: false,
  groupColors: false,
  siteTypeFilter: null,
  readyLocationIds: null,
})

const emit = defineEmits<{
  (e: 'marker-click', payload: MarkerClickPayload): void
  (e: 'update:selectedMarkerId', value: string | null): void
  /** Own-vault marker clicked: open its summary panel instead of navigating. */
  (e: 'vault-info', vaultId: string): void
  /** Dispatched party clicked: open its exploration details. */
  (e: 'party-click', explorationId: string): void
  /** Free-roam explorer clicked: open its dweller popover at screen x/y. */
  (e: 'dweller-click', payload: { track: ExplorerTrack; x: number; y: number }): void
}>()

// ── Marker visibility filter ─────────────────────────────────────
// The index stays known-only. The SVG shows known markers plus dimmed "?" hint
// pins, but only where the derived fog of war has been explored — fogged tiles
// reveal nothing. The home vault is always revealed.
const readyIds = computed(() =>
  props.readyLocationIds === null ? null : new Set(props.readyLocationIds)
)
const matchesReadyFilter = (loc: WastelandLocationWithDwellers) =>
  readyIds.value === null ||
  loc.type === 'home_vault' ||
  (isKnownLocation(loc) && readyIds.value.has(loc.id))
const knownLocations = computed(() =>
  props.locations.filter((loc) => isKnownLocation(loc) && matchesReadyFilter(loc))
)

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
        .filter(
          (route) =>
            route.points.length > 0 && route.points.every((point) => point.location_id == null)
        )
        .map((route) => route.points),
    },
    gridTiles.value
  )
)

function isExploredCoord(coord: { coord_x: number; coord_y: number }): boolean {
  return isExploredTile(
    exploredMask.value,
    registryToTile(coord.coord_x, gridTiles.value),
    registryToTile(coord.coord_y, gridTiles.value),
    gridTiles.value
  )
}

// P3 site-type filter: place markers only. The home vault is not an archetype
// and always stays; vault signals, own-vault markers, expedition sites and
// explorers render outside this list and are never filtered. Fog/declutter
// downstream stay unchanged.
const visibleLocations = computed(() => {
  const filtered = props.locations.filter(
    (loc) => matchesSiteTypeFilter(loc, props.siteTypeFilter) && matchesReadyFilter(loc)
  )
  return props.fogDisabled || readyIds.value !== null
    ? filtered
    : filtered.filter(
        (loc) => !(loc.type === 'visited' && loc.dwellers.length < 2) && isExploredCoord(loc)
      )
})

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
  ].filter((hint) => props.fogDisabled || isExploredCoord(hint))
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
// Dispatched runs mark their target location as "exploring"; the status lists
// the whole dispatch party (anchor first) when party data is present, and a
// solo run collapses to the single anchor. Free-roam runs get a small
// last-known-position marker at the end of their discovery trail instead.
const exploringByLocation = computed(() => {
  const byLocation = new Map<string, string>()
  for (const track of props.explorerTracks) {
    if (!track.targetLocationId) continue
    byLocation.set(
      track.targetLocationId,
      track.partyNames.length ? `Exploring — ${track.partyNames.join(', ')}` : 'Dispatching'
    )
  }
  return byLocation
})

const movingTracks = computed(() => props.explorerTracks.filter((track) => track.lastKnown))
const freeRoamTracks = computed(() => movingTracks.value.filter((track) => !track.targetLocationId))

// Heading chevrons for the free-roam markers: trail vector when the run has a
// usable outbound trail, otherwise the bearing back home. Tracks with neither
// keep the bare thumbnail/marker (no chevron).
const freeRoamChevrons = computed(() => {
  const routesByExploration = buildRoutesByExploration(props.discoveryRoutes)
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
  isPanned,
  isDragging,
  viewBox,
  canPan,
  zoomIn,
  zoomOut,
  resetZoom,
  focusOnMarker,
  syncViewport,
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
const isWideLayout = useMediaQuery('(min-width: 1280px)')
const svgRef = ref<SVGSVGElement | null>(null)
const containerRef = ref<HTMLDivElement | null>(null)

function onOwnVaultClick(vault: PlayerVaultMarkerRead): void {
  if (hasDragMoved.value) return
  emit('vault-info', vault.vault_id)
}

const groupIconByKey = computed(
  () => new Map([...mapStore.placeGroupByKey].map(([key, group]) => [key, group.icon]))
)

// Catalog risk/base difficulty ride the same place-group rows as the icons;
// MapMarker turns them into the danger ring/glow ramp.
function locationGroup(loc: WastelandLocationWithDwellers): PlaceGroup | undefined {
  return loc.group_key ? mapStore.placeGroupByKey.get(loc.group_key) : undefined
}

// The map fills a full-bleed rectangular pane, so the composable needs the
// rendered aspect ratio to know which axis its cover fit crops.
let resizeObserver: ResizeObserver | null = null

function syncViewportAspect(): void {
  const rect = svgRef.value?.getBoundingClientRect()
  if (rect) syncViewport(rect)
}

onMounted(() => {
  syncViewportAspect()
  if (typeof ResizeObserver === 'undefined') return
  resizeObserver = new ResizeObserver(syncViewportAspect)
  if (containerRef.value) resizeObserver.observe(containerRef.value)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
})

// Compensate for SVG zoom so markers grow with its square root.
const markerScale = computed(() => 1 / Math.sqrt(zoom.value))

// ── Declutter ─────────────────────────────────────────────────────────
// Primary markers (home vault, selection, discoveries, active explorers and
// expedition sites) always render — dense discoveries collapse into cluster
// badges instead of being hidden. Secondary locations and anonymous vault
// hints stay hidden at overview zoom and reappear as the player zooms in.
const renderedLocations = computed(() =>
  visibleLocations.value.filter(
    (loc) =>
      readyIds.value !== null ||
      isMarkerVisible(
        {
          type: loc.type,
          selected: props.selectedMarkerId === `loc-${loc.id}`,
          exploring: exploringByLocation.value.has(loc.id),
        },
        zoom.value
      )
  )
)

const renderedVaultHints = computed(() =>
  foreignVaultHints.value.filter(() => isMarkerVisible({ type: 'vault' }, zoom.value))
)

const selectedMarkerId = computed<string | null>({
  get: () => props.selectedMarkerId,
  set: (value) => emit('update:selectedMarkerId', value),
})

const { hasDragMoved, onLocationClick, onSiteClick, onPanelMarkerSelect } = useMarkerSelection(
  selectedMarkerId,
  focusOnMarker,
  emit
)

// The home vault renders as a location marker rather than a player-vault
// marker, so route its click to the own-vault summary too; every other
// location keeps the generic details flow.
function onLocationMarkerClick(loc: WastelandLocationWithDwellers) {
  if (hasDragMoved.value) return
  if (loc.type === 'home_vault') {
    emit('vault-info', loc.vault_id)
    return
  }
  onLocationClick(loc)
}

// Explorer popover anchor: pointer activation carries screen coordinates.
// Keyboard activation (Enter/Space) has none, so fall back to the focused
// marker's on-screen box.
function onExplorerClick(track: ExplorerTrack, event: Event) {
  if (hasDragMoved.value) return
  if (track.targetLocationId) {
    emit('party-click', track.explorationId)
    return
  }
  let x = 0
  let y = 0
  if (event instanceof MouseEvent) {
    x = event.clientX
    y = event.clientY
  } else {
    const rect = (event.target as Element | null)?.getBoundingClientRect()
    if (rect) {
      x = rect.left + rect.width / 2
      y = rect.top + rect.height / 2
    }
  }
  emit('dweller-click', { track, x, y })
}

// ── Discovery clustering ──────────────────────────────────────────────
// Discoveries render at every zoom, so on a dense atlas their count is what
// swamps the map. Grid cells shrink as the map zooms in, so a badge expands
// into individual, fully interactive markers on its own; a badge click zooms
// one step further, centered on the cluster. Selection and active explorers
// stay pinned individually so their rings and labels never disappear.
const locationByMarkerId = computed(
  () => new Map(renderedLocations.value.map((loc) => [`loc-${loc.id}`, loc]))
)

const clusterableDiscoveries = computed(() =>
  renderedLocations.value
    .filter(
      (loc) =>
        loc.type === 'discovery' &&
        loc.is_unlocked !== false &&
        selectedMarkerId.value !== `loc-${loc.id}` &&
        !exploringByLocation.value.has(loc.id)
    )
    .map((loc) => ({ id: `loc-${loc.id}`, x: loc.coord_x, y: loc.coord_y }))
)

const discoveryClusters = computed<MarkerCluster[]>(() =>
  // At max zoom a badge could not be split any further, so every discovery
  // renders individually instead of persisting as an unopenable cluster.
  zoom.value >= MAX_ZOOM ? [] : clusterMarkers(clusterableDiscoveries.value, { zoom: zoom.value })
)

const clusterBadges = computed(() =>
  discoveryClusters.value.filter((cluster) => cluster.members.length > 1)
)

const clusteredIds = computed(
  () =>
    new Set(clusterBadges.value.flatMap((cluster) => cluster.members.map((member) => member.id)))
)

const renderedLocationsIndividual = computed(() =>
  renderedLocations.value.filter((loc) => !clusteredIds.value.has(`loc-${loc.id}`))
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
  if (!canPan.value) return
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
      ref="containerRef"
      class="world-map-container crt-screen touch-none"
      :class="{ 'is-zoomed': isZoomed, 'is-pannable': canPan, 'is-dragging': isDragging }"
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
        preserveAspectRatio="xMidYMid slice"
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

        <!-- Location markers (stored coordinates; discoveries inside a
             cluster are rendered as the badge below instead) -->
        <MapMarker
          :scale="markerScale"
          v-for="loc in renderedLocationsIndividual"
          :key="`loc-${loc.id}`"
          :x="loc.coord_x"
          :y="loc.coord_y"
          :name="loc.name"
          :type="loc.type"
          :icon="locationMarkerIcon(loc.type, loc.group_key, groupIconByKey)"
          :color="groupColors ? groupColor(loc.group_key) : null"
          :is_unlocked="loc.is_unlocked"
          :unseen="mapStore.isUnseenDiscovery(loc)"
          :selected="selectedMarkerId === `loc-${loc.id}`"
          :cleared="loc.clear_state?.cleared ?? false"
          :exploring="exploringByLocation.has(loc.id)"
          :status="exploringByLocation.get(loc.id)"
          :risk="locationGroup(loc)?.risk"
          :base-difficulty="locationGroup(loc)?.base_difficulty"
          @click="onLocationMarkerClick(loc)"
        />

        <!-- Discovery clusters: one ×N badge per dense cell, clickable to zoom
             in until the cluster splits back into individual markers -->
        <MapClusterMarker
          :scale="markerScale"
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
          :scale="markerScale"
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
          :scale="markerScale"
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
          :scale="markerScale"
          v-for="site in expeditionSites"
          :key="`site-${site.id}`"
          :x="site.coord_x"
          :y="site.coord_y"
          :name="site.name"
          type="expedition_site"
          :icon="EXPEDITION_SITE_ICON"
          :cleared="site.cleared"
          :status="siteStatus(site)"
          :selected="selectedMarkerId === `site-${site.id}`"
          @click="onSiteClick(site)"
        />

        <!-- Moving parties open exploration details; solo explorers retain their popover. -->
        <MapMarker
          :scale="markerScale"
          v-for="track in movingTracks"
          :key="`explorer-${track.explorationId}`"
          :x="track.lastKnown!.coord_x"
          :y="track.lastKnown!.coord_y"
          :name="
            track.targetLocationId
              ? track.partyNames.join(', ') || 'Exploration party'
              : track.dwellerName || 'Explorer'
          "
          type="explorer"
          :icon="track.targetLocationId ? 'mdi:account-group' : 'mdi:account'"
          :art-src="track.targetLocationId ? null : (track.dwellerThumbnailUrl ?? null)"
          :label="track.targetLocationId ? 'Exploration party' : 'Explorer'"
          :status="
            track.targetLocationId
              ? track.status === 'returning'
                ? 'Heading home'
                : 'On expedition'
              : track.dwellerName
                ? `Last known — ${track.dwellerName}`
                : 'Last known position'
          "
          :interactive="true"
          @click="onExplorerClick(track, $event)"
        />

        <!-- Travel-direction chevrons for free-roam explorers: a small accent
             wedge rotated around the marker center. aria-hidden + non-interactive. -->
        <g
          v-for="entry in freeRoamChevrons"
          :key="`explorer-heading-${entry.track.explorationId}`"
          class="explorer-heading"
          :transform="`translate(${entry.track.lastKnown!.coord_x}, ${entry.track.lastKnown!.coord_y}) rotate(${entry.heading}) scale(${markerScale})`"
          aria-hidden="true"
        >
          <path class="explorer-heading-chevron" d="M -1.9 -4.7 L 0 -6.7 L 1.9 -4.7" />
        </g>
      </svg>

      <!-- Zoom controls overlay -->
      <div class="zoom-controls" role="group" aria-label="Map zoom controls">
        <Button variant="ghost" size="xs" aria-label="Zoom in" class="zoom-btn" @click="zoomIn()">
          <Icon icon="mdi:plus" class="zoom-icon" />
        </Button>
        <Button variant="ghost" size="xs" aria-label="Zoom out" class="zoom-btn" @click="zoomOut()">
          <Icon icon="mdi:minus" class="zoom-icon" />
        </Button>
        <Button
          variant="ghost"
          size="xs"
          :disabled="!isZoomed && !isPanned"
          aria-label="Reset zoom"
          class="zoom-btn"
          @click="resetZoom()"
        >
          <Icon icon="mdi:arrow-expand-all" class="zoom-icon" />
        </Button>
        <span v-if="isZoomed" class="zoom-level">{{ Math.round(zoom * 100) }}%</span>
      </div>

      <div v-if="$slots.status" class="absolute right-2 top-2 z-10 flex flex-col gap-1 sm:flex-row">
        <slot name="status" />
      </div>

      <!-- Legend overlay -->
      <MapLegend :site-type-filter="siteTypeFilter" />
    </div>
    <!-- Keep the index beside the map on wide screens and below it on narrow ones. -->
    <MarkerListPanel
      class="map-index"
      :docked="isWideLayout"
      :locations="knownLocations"
      :vault-markers="[]"
      :expedition-sites="expeditionSites"
      :place-groups="mapStore.placeGroups"
      :site-type-filter="siteTypeFilter"
      :selected-marker-id="selectedMarkerId"
      @marker-select="onPanelMarkerSelect"
    >
      <template #toggle-label="{ count }">Places and sites · {{ count }}</template>
    </MarkerListPanel>
  </div>
</template>

<style scoped>
.world-map-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
  width: 100%;
}

.world-map-layout :deep(.marker-list-wrapper.map-index) {
  position: static;
  display: block;
  min-width: 0;
}

.world-map-layout :deep(.map-index .marker-list-panel) {
  width: 100%;
  max-height: min(40vh, var(--map-pane-size));
  margin-top: 4px;
}

.world-map-layout :deep(.map-index .marker-list-toggle) {
  width: 100%;
  height: 36px;
  gap: 8px;
  justify-content: flex-start;
}

@media (min-width: 1280px) {
  .world-map-layout {
    grid-template-columns: minmax(0, 1fr) 260px;
    align-items: start;
  }

  .world-map-layout :deep(.map-index .marker-list-panel) {
    max-height: var(--map-pane-size);
    margin-top: 0;
  }
}

/* Full-bleed pane: the map fills the content width under a viewport-relative
   height, and the SVG's cover fit crops the square world to that shape. */
.world-map-container {
  width: 100%;
  height: var(--map-pane-size);
  border: 1px solid var(--color-theme-primary);
  background-color: var(--color-terminal-background);
  box-shadow:
    inset 0 0 40px rgba(0, 0, 0, 0.6),
    0 0 10px var(--color-theme-glow);
  overflow: hidden;
  position: relative;
}

.world-map-container.is-pannable {
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
  left: 8px;
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
</style>
