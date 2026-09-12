<script setup lang="ts">
import { computed } from 'vue'
import { generateTerrain } from '../utils/wastelandTerrain'

/**
 * TerrainLayer — phosphor-terminal cartography background for the wasteland map.
 *
 * Renders BELOW grid lines and markers inside the same SVG.
 * All features are generated from a fixed seed so output is stable.
 *
 * Design direction: "Phosphor Terminal Cartography"
 * - Contour lines as oscilloscope traces with phosphor bloom
 * - Terrain patches with subtle radiation glow
 * - Roads as signal-decay dashed paths
 * - Atmospheric vignette for CRT depth
 */
const terrain = computed(() => generateTerrain())
</script>

<template>
  <!-- Terrain group — visually behind grid lines and markers -->
  <g class="terrain-layer" aria-hidden="true">
    <!-- SVG defs for phosphor effects and gradients -->
    <defs>
      <!-- Phosphor bloom filter for terrain patches -->
      <filter id="terrain-noise" x="-20%" y="-20%" width="140%" height="140%">
        <feTurbulence
          type="fractalNoise"
          v-bind="{ baseFrequency: '0.65', numOctaves: '3' }"
          seed="42"
          result="noise"
        />
        <feColorMatrix type="saturate" values="0" in="noise" result="desaturated" />
        <feBlend in="SourceGraphic" in2="desaturated" mode="multiply" />
      </filter>

      <!-- Phosphor glow filter for contour traces -->
      <filter id="phosphor-trace" x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur in="SourceGraphic" stdDeviation="0.3" result="blur" />
        <feMerge>
          <feMergeNode in="blur" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>

      <!-- Radial gradient for crater rims -->
      <radialGradient id="crater-gradient">
        <stop offset="0%" stop-color="var(--color-theme-primary)" stop-opacity="0.15" />
        <stop offset="70%" stop-color="var(--color-theme-primary)" stop-opacity="0.05" />
        <stop offset="100%" stop-color="var(--color-theme-primary)" stop-opacity="0" />
      </radialGradient>

      <!-- Atmospheric vignette for CRT depth -->
      <radialGradient id="map-vignette" cx="50%" cy="50%" r="70%">
        <stop offset="0%" stop-color="var(--color-theme-primary)" stop-opacity="0.02" />
        <stop offset="60%" stop-color="transparent" stop-opacity="0" />
        <stop offset="100%" stop-color="var(--color-surface-canvas)" stop-opacity="0.4" />
      </radialGradient>

      <!-- Radiation scatter gradient for scorched terrain -->
      <radialGradient id="radiation-scatter">
        <stop offset="0%" stop-color="var(--color-theme-primary)" stop-opacity="0.08" />
        <stop offset="100%" stop-color="var(--color-theme-primary)" stop-opacity="0" />
      </radialGradient>
    </defs>

    <!-- Atmospheric vignette base -->
    <rect x="0" y="0" width="160" height="160" fill="url(#map-vignette)" class="terrain-vignette" />

    <!-- Terrain patches (scorched, dust, craters) -->
    <ellipse
      v-for="(patch, i) in terrain.patches"
      :key="`patch-${i}`"
      :cx="patch.cx"
      :cy="patch.cy"
      :rx="patch.rx"
      :ry="patch.ry"
      :transform="`rotate(${patch.rotation} ${patch.cx} ${patch.cy})`"
      :opacity="patch.opacity"
      :class="`terrain-${patch.kind}`"
    />

    <!-- Contour / elevation lines — phosphor-trace style -->
    <path
      v-for="(contour, i) in terrain.contours"
      :key="`contour-${i}`"
      :d="contour.d"
      :opacity="contour.opacity"
      class="terrain-contour"
      fill="none"
      filter="url(#phosphor-trace)"
    />

    <!-- Road segments connecting hub anchors — signal-decay paths -->
    <path
      v-for="(road, i) in terrain.roads"
      :key="`road-${i}`"
      :d="road.d"
      :opacity="road.opacity"
      :stroke-dasharray="road.dashArray"
      class="terrain-road"
      fill="none"
    />
  </g>
</template>

<style scoped>
.terrain-scorched {
  fill: var(--color-theme-primary);
  filter: url(#terrain-noise);
}

.terrain-dust {
  fill: var(--color-theme-accent);
}

.terrain-crater {
  fill: url(#crater-gradient);
}

.terrain-contour {
  stroke: var(--color-theme-primary);
  stroke-width: 0.12;
}

.terrain-road {
  stroke: var(--color-theme-accent);
  stroke-width: 0.25;
  stroke-linecap: round;
}

.terrain-vignette {
  opacity: 0.6;
}
</style>
