<script setup lang="ts">
import type { CombatEffect } from '../models/playback'

defineProps<{
  effect: CombatEffect
  preparing?: boolean
  skill?: boolean
  metal?: boolean
  facing?: 'left' | 'right'
}>()
</script>

<template>
  <svg
    class="combat-effect pointer-events-none absolute inset-0 z-20 size-full overflow-visible text-theme-primary"
    :class="[
      `combat-effect--${effect}`,
      {
        'combat-effect--prepare': preparing,
        'combat-effect--skill': skill,
        'combat-effect--left': facing === 'left',
      },
    ]"
    viewBox="0 0 100 100"
    fill="none"
    stroke="currentColor"
    stroke-width="3"
    aria-hidden="true"
  >
    <template v-if="preparing">
      <circle v-if="['beam', 'pulse', 'flame'].includes(effect)" cx="60" cy="50" r="15" />
      <path
        v-else-if="['shot', 'burst', 'blast', 'debris'].includes(effect)"
        d="M45 38h18v24H45m18-12h12"
      />
      <path v-else d="M25 65Q20 30 65 25" stroke-dasharray="5 5" />
    </template>
    <template v-else-if="effect === 'beam'">
      <path d="M0 47H100M0 53H100" />
      <circle cx="50" cy="50" r="19" />
    </template>
    <template v-else-if="effect === 'pulse'">
      <ellipse cx="50" cy="50" rx="28" ry="15" />
      <path d="M0 45h20M0 55h20m22-14 16 9-16 9" />
    </template>
    <template v-else-if="effect === 'burst'">
      <path d="m0 30 45 12M0 50h50M0 70l45-12m12-25-4 9 12-3m-6 20-5-8 13 2" />
    </template>
    <template v-else-if="effect === 'debris'">
      <path
        d="m12 30 12-4 5 10-12 5Zm24 15 13-7 9 10-11 12Zm-12 25 6-9 12 6-7 10ZM3 48h15m40-25 8-6m-6 51 10 5"
      />
    </template>
    <template v-else-if="effect === 'punch'">
      <path
        d="M27 39h36l10 12-10 13H29l-7-12Zm9 0V28m12 11V25m12 14V29M76 34l9-7m-6 24h13m-16 17 9 7"
      />
    </template>
    <template v-else-if="effect === 'thrust'">
      <path d="M5 50h65m-17-12 24 12-24 12m30-28-4 8m3 17 4 8" />
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
      <path d="M0 47h35m8-10 7 8 10-6-4 12 11 5-14 2-4 12-6-12-12-3 11-7Z" />
    </template>
    <path v-else d="m20 80 60-60M30 85 85 30M18 55l11 4-6-12m38 30 1-13 11 5" />
    <path
      v-if="metal && !preparing"
      class="armor-sparks"
      d="m30 35-12-12m36 5 3-16m18 30 17-6M33 69 20 81m40-11 6 18M17 53H4"
    />
  </svg>
</template>

<style scoped>
.combat-effect {
  animation: combat-effect-impact 200ms ease-out both;
  filter: drop-shadow(0 0 4px currentColor);
}
.combat-effect--left {
  scale: -1 1;
}
.combat-effect--shot,
.combat-effect--burst,
.combat-effect--blast,
.combat-effect--debris,
.combat-effect--flame {
  color: var(--color-warning);
}
.combat-effect--pulse {
  color: var(--color-info);
}
.combat-effect--beam {
  stroke-width: 2;
}
.armor-sparks {
  color: var(--color-warning);
  stroke: currentColor;
  stroke-width: 4;
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
