<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { Pet } from '../models/pet'
import { getPetBonuses } from '../models/pet'
import ItemCard from '@/core/components/common/ItemCard.vue'
import { Button } from '@/core/components/ui/button'
import { Badge } from '@/core/components/ui/badge'

interface Props {
  pet: Pet
  showActions?: boolean
  equipped?: boolean
}

const { showActions = false, equipped = false, pet } = defineProps<Props>()

const emit = defineEmits<{
  (e: 'equip'): void
  (e: 'unequip'): void
}>()

const bonuses = computed(() => getPetBonuses(pet.effect))
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

    <div v-if="bonuses.length > 0" class="flex flex-wrap gap-1.5">
      <Badge
        v-for="bonus in bonuses"
        :key="bonus.label"
        variant="outline"
        class="border-theme-primary/30 bg-black/30 text-theme-primary"
      >
        {{ bonus.label }} {{ bonus.value }}
      </Badge>
    </div>
  </div>
</template>