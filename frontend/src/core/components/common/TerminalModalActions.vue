<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'

const props = withDefaults(
  defineProps<{
    cancelLabel: string
    confirmLabel: string
    confirmIcon?: string
    alignment?: 'end' | 'between'
    confirmDisabled?: boolean
  }>(),
  { confirmIcon: 'mdi:check', alignment: 'end', confirmDisabled: false }
)

const emit = defineEmits<{
  cancel: []
  confirm: []
}>()
</script>

<template>
  <div class="flex w-full max-sm:flex-col gap-3" :class="props.alignment === 'between' ? 'justify-between' : 'justify-end'">
    <Button class="modal-button cancel shrink-0 whitespace-nowrap max-sm:w-full" variant="secondary" size="lg" @click="emit('cancel')">
      <Icon icon="mdi:close" class="h-5 w-5" />
      {{ cancelLabel }}
    </Button>
    <Button class="modal-button confirm shrink-0 whitespace-nowrap max-sm:w-full" variant="default" size="lg" :disabled="confirmDisabled" @click="emit('confirm')">
      <Icon :icon="confirmIcon" class="h-5 w-5" />
      {{ confirmLabel }}
    </Button>
  </div>
</template>
