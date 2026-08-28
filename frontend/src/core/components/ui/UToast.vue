<script setup lang="ts">
import { Icon } from '@iconify/vue'
import type { Toast } from '@/core/composables/useToast'

interface Props {
  toast: Toast
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'close', id: string): void
}>()

const variantConfig = {
  success: {
    icon: 'mdi:check-circle',
    borderClass: 'border-l-success',
    iconClass: 'text-success',
  },
  error: {
    icon: 'mdi:alert-circle',
    borderClass: 'border-l-danger',
    iconClass: 'text-danger',
  },
  warning: {
    icon: 'mdi:alert',
    borderClass: 'border-l-warning',
    iconClass: 'text-warning',
  },
  info: {
    icon: 'mdi:information',
    borderClass: 'border-l-info',
    iconClass: 'text-info',
  },
}

const config = variantConfig[props.toast.variant]
</script>

<template>
  <div
    :class="[
      'toast',
      config.borderClass,
      'bg-surface-raised/95 border border-surface-hover border-l-4 rounded-md shadow-md backdrop-blur-sm',
      'flex items-center gap-3 p-4 min-w-[300px] max-w-[500px]',
    ]"
    role="status"
    aria-live="polite"
  >
    <Icon :icon="config.icon" :class="['text-2xl', config.iconClass]" :ariaHidden="true" />
    <p class="min-w-0 flex-1 break-words text-sm font-medium text-theme-primary/90">{{ toast.message }}</p>
    <span
      v-if="toast.count && toast.count > 1"
      class="rounded-full bg-surface-hover px-2 py-0.5 text-xs font-bold text-theme-primary"
    >
      ×{{ toast.count }}
    </span>
    <button
      @click="emit('close', toast.id)"
      class="text-theme-primary/60 transition-colors hover:text-theme-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-theme-primary"
      aria-label="Close"
    >
      <Icon icon="mdi:close" class="text-xl" />
    </button>
  </div>
</template>
