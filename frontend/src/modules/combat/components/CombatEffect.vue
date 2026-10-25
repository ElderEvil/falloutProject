<script setup lang="ts">
import type { CombatEffect } from '../models/playback'

defineProps<{
  effect: CombatEffect
  preparing?: boolean
  skill?: boolean
}>()
</script>

<template>
  <svg
    class="combat-effect pointer-events-none absolute inset-0 z-20 size-full overflow-visible text-theme-primary"
    :class="{ 'combat-effect--prepare': preparing, 'combat-effect--skill': skill }"
    viewBox="0 0 100 100"
    fill="none"
    stroke="currentColor"
    stroke-width="3"
    aria-hidden="true"
  >
    <circle v-if="preparing" cx="50" cy="55" r="27" stroke-dasharray="6 5" />
    <template v-else-if="effect === 'beam'">
      <path d="M0 47H100M0 53H100" />
      <circle cx="50" cy="50" r="19" />
    </template>
    <template v-else-if="effect === 'blast'">
      <circle cx="50" cy="50" r="30" />
      <path
        d="m50 8 6 23 19-15-9 23 26 3-24 11 20 17-26-5-4 26-10-24-19 18 9-25-26-2 23-12-18-17 26 6Z"
      />
    </template>
    <template v-else-if="effect === 'flame'">
      <path
        d="M50 12c8 18 28 27 28 47a28 28 0 0 1-56 0c0-13 9-24 17-32 0 11 5 15 9 18 4-10 5-20 2-33Z"
      />
      <path d="M50 48c10 12 14 18 14 25a14 14 0 0 1-28 0c0-8 7-17 14-25Z" />
    </template>
    <template v-else-if="effect === 'sweep'">
      <path d="M10 75Q25 10 90 25M20 85Q35 25 90 35M30 90Q45 40 90 45" />
    </template>
    <template v-else-if="effect === 'shot'">
      <circle cx="50" cy="50" r="13" />
      <path
        d="M50 15v16m0 38v16M15 50h16m38 0h16M25 25l10 10m30 30 10 10M25 75l10-10m30-30 10-10"
      />
    </template>
    <path v-else d="m20 80 60-60M30 85 85 30M18 55l11 4-6-12m38 30 1-13 11 5" />
  </svg>
</template>

<style scoped>
.combat-effect {
  animation: combat-effect-impact 200ms ease-out both;
  filter: drop-shadow(0 0 4px currentColor);
}
.combat-effect--prepare {
  animation: combat-effect-prepare 150ms ease-out both;
  opacity: 0.6;
}
.combat-effect--skill {
  stroke-width: 4;
  filter: drop-shadow(0 0 8px currentColor);
  animation-duration: 300ms;
}
.combat-effect--skill.combat-effect--prepare {
  animation-duration: 250ms;
}
@keyframes combat-effect-prepare {
  from {
    transform: scale(0.7);
    opacity: 0.15;
  }
  to {
    transform: scale(1);
    opacity: 0.7;
  }
}
@keyframes combat-effect-impact {
  from {
    transform: scale(0.8);
    opacity: 1;
  }
  to {
    transform: scale(1.15);
    opacity: 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  .combat-effect {
    animation: none;
    filter: none;
    opacity: 0.65;
  }
}
</style>
