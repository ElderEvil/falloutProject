<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import DwellerChildCard from './DwellerChildCard.vue'
import { allChildren } from '../../models/dwellerFamily'

interface Props {
  vaultId: string
}

defineProps<Props>()

const emit = defineEmits<{ (e: 'select', dwellerId: string): void }>()

const { filter: dwellerStore } = useDwellerStore()

const children = computed(() => allChildren(dwellerStore.allDwellers))
</script>

<template>
  <div class="py-4">
    <div
      v-if="children.length === 0"
      class="flex flex-col items-center justify-center px-8 py-16 text-center"
    >
      <Icon icon="mdi:human-child" class="mb-4 h-16 w-16 text-theme-primary/30" />
      <p class="mb-2 text-lg text-theme-primary">No children growing in this vault yet.</p>
      <p class="text-sm text-theme-primary/60">Partners need to conceive and give birth first!</p>
    </div>

    <div v-else class="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-4">
      <DwellerChildCard
        v-for="child in children"
        :key="child.id"
        :dweller="child"
        @select="emit('select', $event)"
      />
    </div>
  </div>
</template>
