<script setup lang="ts">
import { Icon } from '@iconify/vue'

defineProps<{
  weaponName: string | null
  outfitName: string | null
}>()
</script>

<template>
  <div class="mb-4 grid grid-cols-2 gap-4">
    <div
      class="flex items-center gap-4 rounded-md border border-theme-primary bg-surface-warm-dark p-3 shadow-[0_0_10px_rgba(var(--color-theme-primary-rgb),0.1)]"
    >
      <Icon
        icon="mdi:pistol"
        class="h-8 w-8 shrink-0 text-theme-primary drop-shadow-[0_0_5px_var(--color-theme-glow)]"
      />
      <div class="flex flex-col">
        <span class="text-[0.625rem] uppercase tracking-[0.05em] text-theme-primary/70">Weapon</span>
        <span class="text-sm font-bold text-theme-primary [text-shadow:0_0_5px_var(--color-theme-glow)]">{{ weaponName || 'Unarmed' }}</span>
      </div>
    </div>
    <div
      class="flex items-center gap-4 rounded-md border border-theme-primary bg-surface-warm-dark p-3 shadow-[0_0_10px_rgba(var(--color-theme-primary-rgb),0.1)]"
    >
      <Icon
        icon="mdi:tshirt-crew"
        class="h-8 w-8 shrink-0 text-theme-primary drop-shadow-[0_0_5px_var(--color-theme-glow)]"
      />
      <div class="flex flex-col">
        <span class="text-[0.625rem] uppercase tracking-[0.05em] text-theme-primary/70">Outfit</span>
        <span class="text-sm font-bold text-theme-primary [text-shadow:0_0_5px_var(--color-theme-glow)]">{{ outfitName || 'Vault Suit' }}</span>
      </div>
    </div>
  </div>
</template>
