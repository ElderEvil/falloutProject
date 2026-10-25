<script setup lang="ts">
import { computed } from 'vue'
import {
  Bomb,
  ChevronsRight,
  Crosshair,
  Expand,
  FastForward,
  Flame,
  Hammer,
  HandFist,
  MoveUpRight,
  ScanLine,
  Sword,
  Zap,
  type LucideIcon,
} from '@lucide/vue'
import type { CombatSkillIcon } from '../models/playback'

const props = defineProps<{ icon?: CombatSkillIcon | null }>()

// Category selection belongs to WeaponSkill; the glyph depicts the skill's action.
const icons: Record<CombatSkillIcon, LucideIcon> = {
  unarmed: HandFist,
  'melee-blunt': Hammer,
  'melee-edged': Sword,
  'melee-pointed': MoveUpRight,
  'gun-pistol': FastForward,
  'gun-rifle': Crosshair,
  'gun-shotgun': Expand,
  'energy-pistol': Zap,
  'energy-rifle': ScanLine,
  'heavy-automatic': ChevronsRight,
  'heavy-flamer': Flame,
  'heavy-explosive': Bomb,
}
const selected = computed(() => (props.icon && props.icon in icons ? props.icon : 'unarmed'))
</script>

<template>
  <component
    :is="icons[selected]"
    class="shrink-0"
    v-bind="{ 'data-skill-icon': selected }"
    aria-hidden="true"
  />
</template>
