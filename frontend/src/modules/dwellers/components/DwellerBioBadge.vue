<script setup lang="ts">
import { Icon } from '@iconify/vue'

interface Props {
  hasBio: boolean
}

const { hasBio } = defineProps<Props>()
</script>

<template>
  <span v-if="hasBio" class="flex items-center gap-1" title="Has bio">
    <Icon icon="mdi:script-text-outline" class="h-4 w-4 text-theme-primary/60" />
  </span>
</template>
