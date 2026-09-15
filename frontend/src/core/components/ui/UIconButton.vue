<script setup lang="ts">
import { Icon } from '@iconify/vue'
import UTooltip from './UTooltip.vue'

interface Props {
  icon: string
  label: string
  variant?: 'default' | 'danger'
  disabled?: boolean
}

const { variant = 'default', disabled = false } = defineProps<Props>()

// Consumer classes/attrs belong on the real <button>, not the tooltip trigger.
defineOptions({ inheritAttrs: false })

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

const variantClass = variant === 'danger' ? 'text-danger hover:border-danger hover:text-danger' : 'text-theme-primary hover:border-theme-primary'
</script>

<template>
  <UTooltip :text="label">
    <button
      v-bind="$attrs"
      type="button"
      :aria-label="label"
      :disabled="disabled"
      class="inline-flex size-7 items-center justify-center border border-transparent bg-transparent transition-[border-color,color] duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-theme-primary disabled:cursor-not-allowed disabled:opacity-50"
      :class="variantClass"
      @click="emit('click', $event)"
    >
      <Icon :icon="icon" class="size-4" :ariaHidden="true" />
    </button>
  </UTooltip>
</template>
