<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { UButton } from '@/core/components/ui'

withDefaults(
  defineProps<{
    cancelLabel: string
    confirmLabel: string
    confirmIcon?: string
  }>(),
  { confirmIcon: 'mdi:check' }
)

const emit = defineEmits<{
  cancel: []
  confirm: []
}>()
</script>

<template>
  <div class="flex flex-wrap justify-end gap-3">
    <UButton class="modal-button cancel" variant="secondary" size="lg" @click="emit('cancel')">
      <Icon icon="mdi:close" class="h-5 w-5" />
      {{ cancelLabel }}
    </UButton>
    <UButton class="modal-button confirm" size="lg" @click="emit('confirm')">
      <Icon :icon="confirmIcon" class="h-5 w-5" />
      {{ confirmLabel }}
    </UButton>
  </div>
</template>
