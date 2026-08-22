<script setup lang="ts">
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { UButton } from '@/core/components/ui'
import type { DiscoveryRouteRead, WastelandLocationWithDwellers, VaultMarkerRead } from '../models/map'
import MapMarker from './MapMarker.vue'
import MapLegend from './MapLegend.vue'
import MarkerListPanel from './MarkerListPanel.vue'
import TerrainLayer from './TerrainLayer.vue'
import { spreadMarkers } from '../utils/spreadMarkers'
import { useMapZoomPan } from '../composables/useMapZoomPan'

interface Props {
  locations: WastelandLocationWithDwellers[]
  vaultMarkers: VaultMarkerRead[]
  discoveryRoutes?: DiscoveryRouteRead[]
}

const props = withDefaults(defineProps<Props>(), { discoveryRoutes: () => [] })

const emit = defineEmits<{
  (
    e: 'marker-click',
    payload:
      | { kind: 'location'; data: WastelandLocationWithDwellers }
      | { kind: 'vault'; data: VaultMarkerRead }
  ): void
}>()

// ── Marker visibility filter ─────────────────────────────────────
// Hide single-dweller VISITED locations from the SVG to reduce clutter
// (they remain in the marker list panel and detail modal).
const visibleLocations = computed(() =>
  props.locations.filter((loc) => !(loc.type === 'visited' && loc.dwellers.length < 2))
)

const knownLocations = computed(() => props.locations.filter((loc) => loc.is_unlocked !== false))

const discoveryRouteLines = computed(() =>
  props.discoveryRoutes.map((route) => route.points.map((point) => `${point.coord_x},${point.coord_y}`).join(' '))
)

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
} = useMapZoomPan()

const svgRef = ref<SVGSVGElement | null>(null)
const selectedMarkerId = ref<string | null>(null)
const hasDragMoved = ref(false)

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

// ── Grid lines ─────────────────────────────────────────────────────────
const gridLines = computed(() => {
  const lines: number[] = []
  for (let i = 0; i <= 160; i += 10) {
    lines.push(i)
  }
  return lines
})

// ── Spread markers ─────────────────────────────────────────────────────
const spreadMap = computed(() => {
  const allInputs = [
    ...visibleLocations.value.map((loc) => ({
      id: `loc-${loc.id}`,
      x: loc.coord_x,
      y: loc.coord_y,
    })),
    ...props.vaultMarkers.map((vm, idx) => ({
      id: `vault-${idx}`,
      x: vm.coord_x,
      y: vm.coord_y,
    })),
  ]
  return spreadMarkers(allInputs, {
    collisionRadius: 7.2,
    maxDisplace: 4.0,
    iterations: 5,
  })
})

function getSpread(id: string, fallbackX: number, fallbackY: number) {
  const result = spreadMap.value.get(id)
  return result ?? { renderX: fallbackX, renderY: fallbackY }
}

// ── Marker interactions ────────────────────────────────────────────────
function onLocationClick(loc: WastelandLocationWithDwellers) {
  if (hasDragMoved.value) return
  selectedMarkerId.value = `loc-${loc.id}`
  emit('marker-click', { kind: 'location', data: loc })
}

function onVaultClick(marker: VaultMarkerRead) {
  if (hasDragMoved.value) return
  const idx = props.vaultMarkers.indexOf(marker)
  selectedMarkerId.value = `vault-${idx}`
  emit('marker-click', { kind: 'vault', data: marker })
}

function onPanelMarkerSelect(payload: {
  kind: 'location' | 'vault'
  data: WastelandLocationWithDwellers | VaultMarkerRead
}) {
  const id =
    payload.kind === 'location'
      ? `loc-${(payload.data as WastelandLocationWithDwellers).id}`
      : `vault-${props.vaultMarkers.indexOf(payload.data as VaultMarkerRead)}`

  const pos = spreadMap.value.get(id)
  if (pos) {
    focusOnMarker(pos.renderX, pos.renderY)
  } else if (payload.kind === 'location') {
    // Hidden single-dweller visited marker — focus its raw coords
    focusOnMarker(
      (payload.data as WastelandLocationWithDwellers).coord_x,
      (payload.data as WastelandLocationWithDwellers).coord_y
    )
  } else {
    focusOnMarker(
      (payload.data as VaultMarkerRead).coord_x,
      (payload.data as VaultMarkerRead).coord_y
    )
  }
  selectedMarkerId.value = id
  emit('marker-click', payload as any)
}
</script>

<template>
  <div class="world-map-layout">
    <div
      class="world-map-container crt-screen"
      :class="{ 'is-zoomed': isZoomed, 'is-dragging': isDragging }"
      @mousemove="handleMouseMove"
      @mouseup="handleMouseUp"
      @mouseleave="handleMouseUp"
      @wheel.prevent="handleWheel"
    >
      <svg
        ref="svgRef"
        :viewBox="viewBox"
        xmlns="http://www.w3.org/2000/svg"
        class="world-map-svg"
        focusable="false"
        @mousedown="handleMouseDown"
      >
      <!-- Terrain layer (bottom — behind grid and markers) -->
      <TerrainLayer />

      <!-- Grid lines -->
      <line
        v-for="pos in gridLines"
        :key="`h-${pos}`"
        :x1="0"
        :y1="pos"
        :x2="160"
        :y2="pos"
        class="grid-line"
      />
      <line
        v-for="pos in gridLines"
        :key="`v-${pos}`"
        :x1="pos"
        :y1="0"
        :x2="pos"
        :y2="160"
        class="grid-line"
      />

      <!-- Discovery routes (per-exploration trail) -->
      <polyline
        v-for="(route, i) in discoveryRouteLines"
        :key="`route-${i}`"
        :points="route"
        class="stroke-[var(--color-theme-accent)] stroke-[0.4] opacity-[0.55] [stroke-dasharray:2_2] [stroke-linecap:round]"
        fill="none"
      />

      <!-- Location markers (spread-adjusted positions) -->
      <MapMarker
        v-for="loc in visibleLocations"
        :key="`loc-${loc.id}`"
        :x="getSpread(`loc-${loc.id}`, loc.coord_x, loc.coord_y).renderX"
        :y="getSpread(`loc-${loc.id}`, loc.coord_x, loc.coord_y).renderY"
        :name="loc.name"
        :type="loc.type"
        :is_unlocked="loc.is_unlocked"
        :selected="selectedMarkerId === `loc-${loc.id}`"
        @click="onLocationClick(loc)"
      />

      <!-- Vault markers (spread-adjusted positions) -->
      <MapMarker
        v-for="(vm, idx) in vaultMarkers"
        :key="`vault-${idx}`"
        :x="getSpread(`vault-${idx}`, vm.coord_x, vm.coord_y).renderX"
        :y="getSpread(`vault-${idx}`, vm.coord_x, vm.coord_y).renderY"
        :name="vm.name"
        :type="vm.type"
        :selected="selectedMarkerId === `vault-${idx}`"
        @click="onVaultClick(vm)"
      />
      </svg>

      <!-- Zoom controls overlay -->
      <div class="zoom-controls" role="group" aria-label="Map zoom controls">
        <UButton variant="ghost" size="xs" aria-label="Zoom in" class="zoom-btn" @click="zoomIn()">
          <Icon icon="mdi:plus" class="zoom-icon" />
        </UButton>
        <UButton variant="ghost" size="xs" aria-label="Zoom out" class="zoom-btn" @click="zoomOut()">
          <Icon icon="mdi:minus" class="zoom-icon" />
        </UButton>
        <UButton
          variant="ghost"
          size="xs"
          :disabled="!isZoomed"
          aria-label="Reset zoom"
          class="zoom-btn"
          @click="resetZoom()"
        >
          <Icon icon="mdi:arrow-expand-all" class="zoom-icon" />
        </UButton>
        <span v-if="isZoomed" class="zoom-level">{{ Math.round(zoom * 100) }}%</span>
      </div>

      <!-- Legend overlay -->
      <MapLegend />
    </div>

    <!-- Persistent desktop location index -->
    <MarkerListPanel
      :docked="true"
      :locations="knownLocations"
      :vault-markers="vaultMarkers"
      :selected-marker-id="selectedMarkerId"
      @marker-select="onPanelMarkerSelect"
    />
  </div>
</template>

<style scoped>
.world-map-layout {
  display: grid;
  grid-template-columns: minmax(0, 800px) minmax(12rem, 14rem);
  align-items: stretch;
  gap: 1rem;
  width: 100%;
  max-width: 65rem;
}

.world-map-container {
  width: 100%;
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

.grid-line {
  stroke: var(--color-theme-primary);
  stroke-width: 0.15;
  stroke-opacity: 0.12;
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
