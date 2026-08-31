<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'

interface Props {
  count: number
  title?: string
}

const props = defineProps<Props>()
const tooltip = computed(
  () => props.title ?? `${props.count} ${props.count === 1 ? 'place' : 'places'} visited`
)
</script>

<template>
  <span
    v-if="count > 0"
    class="flex items-center gap-1 text-sm font-semibold"
    :title="tooltip"
  >
    <Icon icon="mdi:map-outline" class="h-4 w-4 text-theme-primary/60" />
    {{ props.count }}
  </span>
</template>
