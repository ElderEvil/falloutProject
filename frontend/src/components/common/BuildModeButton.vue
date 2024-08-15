<script setup lang="ts">
import { WrenchScrewdriverIcon } from '@heroicons/vue/24/solid'

const props = defineProps<{
  buildModeActive: boolean
}>()

const emit = defineEmits<{
  (e: 'toggleBuildMode'): void
}>()
</script>

<template>
  <button
    @click="emit('toggleBuildMode')"
    class="flex items-center rounded px-4 py-2"
    :class="buildModeActive ? 'bg-red-700' : 'bg-gray-700'"
  >
    <WrenchScrewdriverIcon class="h-5 w-5" v-if="!buildModeActive" />
    <span v-else>X</span>
    <span class="ml-2">{{ buildModeActive ? 'Cancel Building' : 'Build Mode' }}</span>
  </button>
</template>
