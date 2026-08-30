<script setup lang="ts">
import { Icon } from '@iconify/vue'

interface Props {
  count: number
}

const { count } = defineProps<Props>()
</script>

<template>
  <span
    v-if="count > 0"
    class="flex items-center gap-1 text-sm font-semibold"
    :title="`${count} ${count === 1 ? 'place' : 'places'} visited`"
  >
    <Icon icon="mdi:map-outline" class="h-4 w-4 text-theme-primary/60" />
    {{ count }}
  </span>
</template>
