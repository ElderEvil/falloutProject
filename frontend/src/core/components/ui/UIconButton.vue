<script setup lang="ts">
import { Icon } from '@iconify/vue'

interface Props {
  icon: string
  label: string
  variant?: 'default' | 'danger'
  disabled?: boolean
}

const { variant = 'default', disabled = false } = defineProps<Props>()

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

const variantClass = variant === 'danger' ? 'text-danger hover:border-danger hover:text-danger' : 'text-theme-primary hover:border-theme-primary'
</script>

<template>
  <button
    type="button"
    :aria-label="label"
    :title="label"
    :disabled="disabled"
    class="inline-flex size-7 items-center justify-center border border-transparent bg-transparent transition-[border-color,color] duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-theme-primary disabled:cursor-not-allowed disabled:opacity-50"
    :class="variantClass"
    @click="emit('click', $event)"
  >
    <Icon :icon="icon" class="size-4" :ariaHidden="true" />
  </button>
</template>
