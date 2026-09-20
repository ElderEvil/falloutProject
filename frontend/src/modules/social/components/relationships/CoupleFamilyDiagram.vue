<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import DwellerChildCard from './DwellerChildCard.vue'
import { childrenOfCouple } from '../../models/dwellerFamily'

interface Props {
  dweller1: DwellerShort
  dweller2: DwellerShort
}

const props = defineProps<Props>()

const emit = defineEmits<{ (e: 'select', dwellerId: string): void }>()

const { filter: dwellerStore } = useDwellerStore()

const children = computed(() =>
  childrenOfCouple(dwellerStore.allDwellers, props.dweller1.id, props.dweller2.id)
)
</script>

<template>
  <div class="mt-1 pl-6">
    <h4
      v-if="children.length"
      class="mb-2 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-theme-primary/70"
    >
      <Icon icon="mdi:human-child" class="h-3.5 w-3.5" />
      Children ({{ children.length }})
    </h4>

    <div v-if="children.length" class="flex flex-wrap gap-2">
      <DwellerChildCard
        v-for="child in children"
        :key="child.id"
        :dweller="child"
        class="w-56"
        @select="emit('select', $event)"
      />
    </div>

    <p v-else class="mt-0.5 text-xs text-theme-primary/40">No children yet</p>
  </div>
</template>
