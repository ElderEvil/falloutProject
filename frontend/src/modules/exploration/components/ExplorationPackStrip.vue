<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Progress } from '@/core/components/ui/progress'
import { getItemIcon } from '@/core/models/items'
import type { Exploration, LootItem } from '@/modules/exploration/stores/exploration'

const props = defineProps<{
  exploration: Exploration
}>()

/** Loot icons are a glance cue, not an inventory; the count carries the rest. */
const MAX_ICONS = 10

// Keep this filter in step with the backend pack rule in
// backend/app/utils/exploration_carry.py: capacity is 15 + 2 x Strength, and
// equipped gear plus stimpaks/radaways (the medical pouch) never take pack slots.
const POUCH_ITEM_TYPES = new Set(['stimpak', 'radaway'])

const isPouchItem = (item: LootItem) => {
  const type = (item.item_type ?? '').trim().toLowerCase()
  if (type) return POUCH_ITEM_TYPES.has(type)
  // Legacy entries may predate item_type; the name is the only signal left.
  return POUCH_ITEM_TYPES.has((item.item_name ?? '').trim().toLowerCase())
}

const packItems = computed<LootItem[]>(() =>
  (props.exploration.loot_collected ?? []).filter((item) => !item.equipped && !isPouchItem(item))
)

const derivedSlotsUsed = computed(() =>
  packItems.value.reduce((total, item) => total + Math.max(1, Number(item.quantity) || 1), 0)
)

// The payload numbers are authoritative once the backend ships them; the local
// derivation keeps the strip honest on payloads that predate the change.
const capacity = computed(
  () => props.exploration.carry_capacity ?? 15 + 2 * (props.exploration.dweller_strength ?? 0)
)
const used = computed(() => props.exploration.pack_slots_used ?? derivedSlotsUsed.value)

const isFull = computed(() => capacity.value > 0 && used.value >= capacity.value)
const fillPercentage = computed(() =>
  capacity.value > 0 ? Math.min(100, (used.value / capacity.value) * 100) : 0
)

const visibleIcons = computed(() => packItems.value.slice(0, MAX_ICONS))
const overflowCount = computed(() => Math.max(0, packItems.value.length - MAX_ICONS))
</script>

<template>
  <div class="pack-strip flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
    <span class="text-[0.625rem] uppercase tracking-[0.05em]">Pack</span>
    <span
      class="pack-count font-bold tabular-nums"
      :class="isFull ? 'text-warning' : 'text-foreground'"
    >
      {{ used }} / {{ capacity }}
    </span>
    <Progress
      class="h-1 min-w-16 flex-1"
      size="xs"
      :tone="isFull ? 'warning' : 'default'"
      :model-value="fillPercentage"
      label="Pack capacity"
      :value-text="`${used} of ${capacity} slots`"
    />
    <span class="flex items-center gap-0.5" aria-hidden="true">
      <span
        v-for="(item, index) in visibleIcons"
        :key="`${item.item_name}-${index}`"
        class="pack-item inline-flex text-muted-foreground"
        :title="item.item_name"
      >
        <Icon
          :icon="getItemIcon(item.item_type ?? 'item', { name: item.item_name })"
          class="size-3.5"
        />
      </span>
      <span v-if="overflowCount > 0" class="pack-overflow text-[0.625rem] tabular-nums">
        +{{ overflowCount }}
      </span>
    </span>
    <span
      v-if="isFull"
      class="pack-full-tag rounded-sm border border-warning/40 px-1 text-[0.625rem] font-bold uppercase tracking-[0.05em] text-warning"
    >
      Pack full
    </span>
  </div>
</template>
