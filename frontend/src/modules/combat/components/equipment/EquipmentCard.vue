<script setup lang="ts">
import { Icon } from '@iconify/vue'
import type { Weapon, Outfit } from '@/modules/combat/models/equipment'
import ItemCard from '@/core/components/common/ItemCard.vue'
import { Button } from '@/core/components/ui/button'

interface Props {
  item: Weapon | Outfit
  type: 'weapon' | 'outfit'
  showActions?: boolean
  equipped?: boolean
}

const { showActions = false, equipped = false, item, type } = defineProps<Props>()

const emit = defineEmits<{
  (e: 'equip'): void
  (e: 'unequip'): void
}>()
</script>

<template>
  <div
    class="equipment-card"
    :class="[
      'flex flex-col gap-3 rounded-lg border-2 p-4 transition-all duration-200',
      equipped
        ? 'border-theme-primary bg-black/50 shadow-[0_0_12px_var(--color-theme-glow)]'
        : 'border-(--color-theme-glow) bg-black/30 hover:border-theme-primary hover:bg-black/50 hover:-translate-y-0.5 hover:shadow-glow-md',
    ]"
  >
    <ItemCard
      :item="item"
      :item-type="type"
      variant="list"
      :show-value-as-stat="item.value != null"
    >
      <template #actions>
        <div v-if="showActions" class="flex gap-2">
          <Button
            v-if="!equipped"
            class="w-full"
            variant="secondary"
            @click="emit('equip')"
          >
            <Icon icon="mdi:check" />
            Equip
          </Button>
          <Button
            v-else
            class="w-full"
            variant="destructive"
            @click="emit('unequip')"
          >
            <Icon icon="mdi:close" />
            Unequip
          </Button>
        </div>
      </template>
    </ItemCard>
  </div>
</template>