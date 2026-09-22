<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'

withDefaults(
  defineProps<{
    label?: string
  }>(),
  { label: 'Back' }
)

defineEmits<{
  (e: 'click', event: MouseEvent): void
}>()
</script>

<template>
  <Button variant="ghost" size="sm" :aria-label="label" @click="$emit('click', $event)">
    <Icon icon="mdi:arrow-left" class="h-5 w-5" :ariaHidden="true" />
    {{ label }}
  </Button>
</template>
