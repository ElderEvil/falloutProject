<script setup lang="ts">
import { computed } from 'vue'
import type { WastelandLocationWithDwellers, VaultMarkerRead } from '../models/map'
import MapMarker from './MapMarker.vue'

interface Props {
  locations: WastelandLocationWithDwellers[]
  vaultMarkers: VaultMarkerRead[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (
    e: 'marker-click',
    payload:
      | { kind: 'location'; data: WastelandLocationWithDwellers }
      | { kind: 'vault'; data: VaultMarkerRead }
  ): void
}>()

const gridLines = computed(() => {
  const lines: number[] = []
  for (let i = 0; i <= 100; i += 10) {
    lines.push(i)
  }
  return lines
})

function onLocationClick(loc: WastelandLocationWithDwellers) {
  emit('marker-click', { kind: 'location', data: loc })
}

function onVaultClick(marker: VaultMarkerRead) {
  emit('marker-click', { kind: 'vault', data: marker })
}
</script>

<template>
  <div class="world-map-container crt-screen">
    <svg
      viewBox="0 0 100 100"
      xmlns="http://www.w3.org/2000/svg"
      class="world-map-svg"
      role="img"
      aria-label="Wasteland world map"
    >
      <!-- Grid lines -->
      <line
        v-for="pos in gridLines"
        :key="`h-${pos}`"
        :x1="0"
        :y1="pos"
        :x2="100"
        :y2="pos"
        class="grid-line"
      />
      <line
        v-for="pos in gridLines"
        :key="`v-${pos}`"
        :x1="pos"
        :y1="0"
        :x2="pos"
        :y2="100"
        class="grid-line"
      />

      <!-- Location markers -->
      <MapMarker
        v-for="loc in locations"
        :key="`loc-${loc.id}`"
        :x="loc.coord_x"
        :y="loc.coord_y"
        :name="loc.name"
        :type="loc.type"
        @click="onLocationClick(loc)"
      />

      <!-- Vault markers (computed, display-only) -->
      <MapMarker
        v-for="(vm, idx) in vaultMarkers"
        :key="`vault-${idx}`"
        :x="vm.coord_x"
        :y="vm.coord_y"
        :name="vm.name"
        :type="vm.type"
        @click="onVaultClick(vm)"
      />
    </svg>
  </div>
</template>

<style scoped>
.world-map-container {
  width: 100%;
  max-width: 800px;
  aspect-ratio: 1 / 1;
  border: 1px solid var(--color-theme-primary);
  background-color: var(--color-terminal-background);
  box-shadow:
    inset 0 0 40px rgba(0, 0, 0, 0.6),
    0 0 10px var(--color-theme-glow);
  overflow: hidden;
  position: relative;
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
</style>
