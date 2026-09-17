<template>
  <div class="couple-family-diagram">
    <div v-if="children.length" class="children-row">
      <button
        v-for="child in children"
        :key="child.id"
        type="button"
        class="child-node"
        :title="`${child.first_name} ${child.last_name}`"
        @click="emit('select', child.id)"
      >
        <Icon icon="mdi:human-child" class="child-icon" />
        {{ child.first_name }}
      </button>
    </div>
    <div v-else class="no-children">
      <span class="no-children-text">No children</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'

interface Props {
  dweller1: DwellerShort
  dweller2: DwellerShort
}

const props = defineProps<Props>()

const emit = defineEmits<{ (e: 'select', dwellerId: string): void }>()

const { filter: dwellerStore } = useDwellerStore()

const children = computed(() =>
  dwellerStore.dwellers.filter(
    (d) =>
      (d.parent_1_id === props.dweller1.id && d.parent_2_id === props.dweller2.id) ||
      (d.parent_1_id === props.dweller2.id && d.parent_2_id === props.dweller1.id)
  )
)
</script>

<style scoped>
.couple-family-diagram {
  margin-top: 0.25rem;
  padding-left: 1.5rem;
}

.children-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.child-node {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.2rem 0.6rem;
  background: rgba(0, 255, 0, 0.05);
  border: 1px solid var(--color-theme-primary);
  border-radius: 0.375rem;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
  font-size: 0.8125rem;
  opacity: 0.9;
  cursor: pointer;
  transition: all 0.2s;
}

.child-node:hover {
  box-shadow: 0 0 10px var(--color-theme-glow);
  background: rgba(0, 255, 0, 0.15);
}

.child-icon {
  font-size: 0.875rem;
}

.no-children {
  margin-top: 0.125rem;
}

.no-children-text {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.4;
}
</style>
