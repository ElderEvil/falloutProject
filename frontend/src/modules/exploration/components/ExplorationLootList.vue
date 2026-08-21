<script setup lang="ts">
import { Icon } from '@iconify/vue'
import type { LootItem } from '../stores/exploration'
import { getRarityColor } from '../models/exploration'

withDefaults(defineProps<{ items: LootItem[] }>(), { items: () => [] })
</script>

<template>
  <div
    v-if="items.length > 0"
    class="mb-4 rounded-lg border-2 border-theme-primary bg-terminal-background p-4 shadow-[0_0_20px_var(--color-theme-glow)]"
  >
    <h3 class="section-title mb-2 flex items-center text-base font-bold text-theme-primary">
      <Icon icon="mdi:package-variant" class="mr-2" />
      Loot Found ({{ items.length }})
    </h3>
    <ul class="flex max-h-[220px] flex-col gap-2 overflow-y-auto">
      <li
        v-for="(item, i) in items"
        :key="`${item.item_name}-${item.found_at}-${i}`"
        class="flex items-center justify-between rounded border-l-[3px] bg-terminal-background p-2.5 transition-all duration-200 hover:bg-theme-primary/10"
        :style="{ borderLeftColor: getRarityColor(item.rarity) }"
      >
        <div class="flex items-center gap-2">
          <Icon
            icon="mdi:treasure-chest"
            class="h-5 w-5"
            :style="{ color: getRarityColor(item.rarity) }"
          />
          <span class="text-sm font-semibold" :style="{ color: getRarityColor(item.rarity) }">
            {{ item.item_name }}
          </span>
        </div>
        <div class="flex items-center gap-2 text-xs">
          <span class="font-semibold" :style="{ color: getRarityColor(item.rarity) }">
            {{ item.rarity }}
          </span>
          <span class="text-theme-primary/70">x{{ item.quantity }}</span>
        </div>
      </li>
    </ul>
  </div>
</template>
