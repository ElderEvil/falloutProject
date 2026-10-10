<script setup lang="ts">
/**
 * ExplorationItemRow — one rarity-bordered loot row (name, rarity, quantity)
 * shared by the collected-items list and the overflow decision list.
 *
 * Trailing content (check mark or Take/Sell actions) comes from the default
 * slot so each call site keeps its own markup.
 */
import type { LootItem } from '@/modules/exploration/stores/exploration'
import { getRarityColor } from '@/modules/exploration/models/exploration'

defineProps<{ item: LootItem }>()
</script>

<template>
  <div class="item-entry" :style="{ borderColor: getRarityColor(item.rarity) }">
    <div class="item-info">
      <div class="item-name" :style="{ color: getRarityColor(item.rarity) }">
        {{ item.item_name }}
      </div>
      <div class="item-meta">
        <span class="item-rarity" :style="{ color: getRarityColor(item.rarity) }">{{
          item.rarity
        }}</span>
        <span class="item-quantity">x{{ item.quantity }}</span>
      </div>
    </div>
    <slot />
  </div>
</template>

<style scoped>
.item-entry {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid;
  border-radius: 6px;
  transition: all 0.2s ease;
}

.item-entry:hover {
  background: color-mix(in srgb, var(--color-theme-primary) 8%, transparent);
  transform: translateX(4px);
}

.item-info {
  flex: 1;
}

.item-name {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.item-meta {
  display: flex;
  gap: 1rem;
  font-size: 0.875rem;
}

.item-rarity {
  font-weight: 600;
}

.item-quantity {
  color: color-mix(in srgb, var(--color-theme-primary) 70%, transparent);
}
</style>
