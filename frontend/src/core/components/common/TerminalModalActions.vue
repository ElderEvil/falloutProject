<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { UButton } from '@/core/components/ui'

const props = withDefaults(
  defineProps<{
    cancelLabel: string
    confirmLabel: string
    confirmIcon?: string
    alignment?: 'end' | 'between'
  }>(),
  { confirmIcon: 'mdi:check', alignment: 'end' }
)

const emit = defineEmits<{
  cancel: []
  confirm: []
}>()
</script>

<template>
  <div class="flex w-full flex-nowrap gap-3" :class="props.alignment === 'between' ? 'justify-between' : 'justify-end'">
    <UButton class="modal-button cancel shrink-0 whitespace-nowrap" variant="secondary" size="lg" @click="emit('cancel')">
      <Icon icon="mdi:close" class="h-5 w-5" />
      {{ cancelLabel }}
    </UButton>
    <UButton class="modal-button confirm shrink-0 whitespace-nowrap" size="lg" @click="emit('confirm')">
      <Icon :icon="confirmIcon" class="h-5 w-5" />
      {{ confirmLabel }}
    </UButton>
  </div>
</template>
