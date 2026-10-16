<script setup lang="ts">
import { Icon } from '@iconify/vue'
import type { Pet } from '../models/pet'
import ItemCard from '@/core/components/common/ItemCard.vue'
import { Button } from '@/core/components/ui/button'

interface Props {
  pet: Pet
  showActions?: boolean
  equipped?: boolean
  disabled?: boolean
}

const { showActions = false, equipped = false, disabled = false, pet } = defineProps<Props>()

const emit = defineEmits<{
  (e: 'equip'): void
  (e: 'unequip'): void
}>()
</script>

<template>
  <div
    class="pet-card"
    :class="[
      'flex flex-col gap-3 rounded-lg border-2 p-4 transition-all duration-200',
      equipped
        ? 'border-theme-primary bg-black/50 shadow-[0_0_12px_var(--color-theme-glow)]'
        : 'border-(--color-theme-glow) bg-black/30 hover:border-theme-primary hover:bg-black/50 hover:-translate-y-0.5 hover:shadow-glow-md',
    ]"
  >
    <ItemCard :item="pet" item-type="pet" variant="list">
      <template #actions>
        <div v-if="showActions" class="flex gap-2">
          <Button
            v-if="!equipped"
            class="w-full"
            variant="secondary"
            :disabled="disabled"
            @click="emit('equip')"
          >
            <Icon icon="mdi:check" />
            Equip
          </Button>
          <Button
            v-else
            class="w-full"
            variant="destructive"
            :disabled="disabled"
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
