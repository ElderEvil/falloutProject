<script setup lang="ts">
import { computed } from 'vue'
import type { CombatSkillIcon } from '../models/playback'

const props = defineProps<{ icon?: CombatSkillIcon | null }>()

// Original SVG path data: CC0-1.0 (https://creativecommons.org/publicdomain/zero/1.0/).
// Category selection belongs to WeaponSkill.
const paths: Record<CombatSkillIcon, string> = {
  unarmed: 'M6 12V6h3V4h3v1h3v2h3v8l-3 5H8l-4-7v-3h3l2 4',
  'melee-blunt': 'm4 8 7-5 4 6-7 5-4-6Zm6 5 8 8 3-3-9-8',
  'melee-edged': 'M8 16 20 4v6L12 18M5 13l6 6M3 21l5-5',
  'melee-pointed': 'M4 20 16 8m-3-1 7-3-4 7-3-4ZM8 15l2 2',
  'gun-pistol': 'M3 7h18v5H11l-2 8H4l2-8H3V7Zm9 5v3h3v-3M17 7V5',
  'gun-rifle': 'M2 9h5l2-3h6v3h7v3H10l-2 6H3l2-6H2V9Zm10-3V3h5m-6 9 3 5',
  'gun-shotgun': 'M2 9h20M3 12h19M3 9v3l-2 6h6l4-6m2 0 3 4M17 7v2',
  'energy-pistol': 'M3 12h7l-2 8H3l2-8M11 5a5 5 0 1 1 0 8m5-6-3 4h4l-2 4',
  'energy-rifle': 'M2 10h20M2 14h20M3 14l-2 5h6l4-5M12 7v10m4-10v10m4-10v10M5 7h3',
  'heavy-automatic': 'M2 8h8l3-3h7v13h-7l-3-3H2V8Zm11-1v9m4-9v9M5 15l-2 6h5l3-6M20 8h3m-3 6h3',
  'heavy-flamer':
    'M12 2c2 5 7 6 7 12a7 7 0 0 1-14 0c0-4 2-6 4-8 0 3 1 4 3 5 1-3 1-5 0-9Zm0 12c-2 2-3 3-3 5a3 3 0 0 0 6 0c0-2-1-3-3-5Z',
  'heavy-explosive': 'M7 9a7 7 0 1 0 8 0l-1-3h-6L7 9Zm4-3V3h5m1 1 2-2m0 4h3',
}
const selected = computed(() => (props.icon && props.icon in paths ? props.icon : 'unarmed'))
</script>

<template>
  <svg
    class="shrink-0"
    v-bind="{ 'data-skill-icon': selected }"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path :d="paths[selected]" />
  </svg>
</template>
