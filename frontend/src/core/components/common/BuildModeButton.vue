<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { UButton } from '@/core/components/ui'
import { computed } from 'vue'

const props = defineProps<{
  buildModeActive: boolean
}>()

const emit = defineEmits<{
  (e: 'toggleBuildMode'): void
}>()

const iconName = computed(() => props.buildModeActive ? 'mdi:close' : 'mdi:hammer')
</script>

<template>
  <UButton
    :variant="buildModeActive ? 'danger' : 'secondary'"
    @click="emit('toggleBuildMode')"
    :title="buildModeActive ? 'Cancel Building (Esc)' : 'Build Mode (B)'"
  >
    <template #leading>
      <Icon :icon="iconName" class="h-5 w-5" />
    </template>
    {{ buildModeActive ? 'Cancel Building' : 'Build Mode' }}
    <template #trailing>
      <span class="hotkey-badge">{{ buildModeActive ? 'ESC' : 'B' }}</span>
    </template>
  </UButton>
</template>

<style scoped>
.hotkey-badge {
  font-size: 0.75rem;
  padding: 0.125rem 0.375rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid currentColor;
  border-radius: 3px;
  font-weight: 700;
  font-family: 'Courier New', monospace;
  opacity: 0.8;
}
</style>
