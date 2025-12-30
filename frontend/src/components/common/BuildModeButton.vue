<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { UButton } from '@/components/ui'
import { computed } from 'vue'

const props = defineProps<{
  buildModeActive: boolean
}>()

const emit = defineEmits<{
  (e: 'toggleBuildMode'): void
}>()

const iconName = computed(() => props.buildModeActive ? 'mdi:close' : 'mdi:hammer-wrench')
</script>

<template>
  <UButton
    :variant="buildModeActive ? 'danger' : 'secondary'"
    @click="emit('toggleBuildMode')"
  >
    <template #leading>
      <Icon :icon="iconName" class="h-5 w-5" />
    </template>
    {{ buildModeActive ? 'Cancel Building' : 'Build Mode' }}
  </UButton>
</template>
