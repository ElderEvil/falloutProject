<script setup lang="ts">
import { computed } from 'vue'
import { generateTerrain } from '../utils/wastelandTerrain'

/**
 * TerrainLayer — deterministic background terrain for the wasteland map.
 *
 * Renders BELOW grid lines and markers inside the same SVG.
 * All features are generated from a fixed seed so output is stable.
 */
const terrain = computed(() => generateTerrain())
</script>

<template>
  <!-- Terrain group — visually behind grid lines and markers -->
  <g class="terrain-layer" aria-hidden="true">
    <!-- SVG defs for noise texture and gradients -->
    <defs>
      <!-- Subtle turbulence filter for terrain patches -->
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

      <!-- Radial gradient for crater rims -->
      <radialGradient id="crater-gradient">
        <stop offset="0%" stop-color="var(--color-theme-primary)" stop-opacity="0.15" />
        <stop offset="70%" stop-color="var(--color-theme-primary)" stop-opacity="0.05" />
        <stop offset="100%" stop-color="var(--color-theme-primary)" stop-opacity="0" />
      </radialGradient>
    </defs>

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

    <!-- Contour / elevation lines -->
    <path
      v-for="(contour, i) in terrain.contours"
      :key="`contour-${i}`"
      :d="contour.d"
      :opacity="contour.opacity"
      class="terrain-contour"
      fill="none"
    />

    <!-- Road segments connecting hub anchors -->
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
</style>
