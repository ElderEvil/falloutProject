<script setup lang="ts">
import { Icon } from '@iconify/vue'
import UButton from '@/core/components/ui/UButton.vue'

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
  <UButton variant="ghost" size="sm" :aria-label="label" @click="$emit('click', $event)">
    <Icon icon="mdi:arrow-left" class="h-5 w-5" :ariaHidden="true" />
    {{ label }}
  </UButton>
</template>
