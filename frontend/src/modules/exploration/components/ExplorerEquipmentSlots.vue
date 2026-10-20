<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { getItemIcon } from '@/core/models/items'

const props = defineProps<{
  weaponName: string | null
  outfitName: string | null
  petName: string | null
  weapon?: { weapon_subtype?: string } | null
  outfit?: { outfit_type?: string } | null
  pet?: { name?: string } | null
}>()

const equipmentSlots = computed(() => [
  {
    label: 'Weapon',
    icon: props.weaponName ? getItemIcon('weapon', props.weapon ?? {}) : 'fa6-solid:hand-fist',
    name: props.weaponName ?? 'Unarmed',
  },
  {
    label: 'Outfit',
    icon: getItemIcon('outfit', props.outfit ?? {}),
    name: props.outfitName ?? 'Vault Suit',
  },
  {
    label: 'Pet',
    icon: getItemIcon('pet', props.pet ?? {}),
    name: props.petName ?? 'None',
  },
])
</script>

<template>
  <div class="explorer-equipment-slots grid grid-cols-1 gap-3 mb-4 sm:grid-cols-3 sm:gap-4">
    <div
      v-for="slot in equipmentSlots"
      :key="slot.label"
      class="flex items-center gap-4 rounded-md border border-theme-primary bg-terminal-background p-3 shadow-[0_0_10px_rgba(var(--color-theme-primary-rgb),0.1)]"
    >
      <Icon
        :icon="slot.icon"
        class="h-8 w-8 shrink-0 text-theme-primary drop-shadow-[0_0_5px_var(--color-theme-glow)]"
      />
      <div class="flex min-w-0 flex-col">
        <span class="text-[0.625rem] uppercase tracking-[0.05em] text-theme-primary/70"
          >{{ slot.label }}</span
        >
        <span
          class="truncate text-sm font-bold text-theme-primary [text-shadow:0_0_5px_var(--color-theme-glow)]"
          >{{ slot.name }}</span
        >
      </div>
    </div>
  </div>
</template>
