<script setup lang="ts">
import { WrenchScrewdriverIcon, XMarkIcon } from '@heroicons/vue/24/solid'
import { UButton } from '@/components/ui'

const props = defineProps<{
  buildModeActive: boolean
}>()

const emit = defineEmits<{
  (e: 'toggleBuildMode'): void
}>()
</script>

<template>
  <UButton
    :variant="buildModeActive ? 'danger' : 'secondary'"
    :icon="buildModeActive ? XMarkIcon : WrenchScrewdriverIcon"
    @click="emit('toggleBuildMode')"
  >
    {{ buildModeActive ? 'Cancel Building' : 'Build Mode' }}
  </UButton>
</template>
