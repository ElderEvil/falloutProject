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
    bgClass: 'bg-gray-900/90 border-[--color-theme-primary]',
    iconClass: 'text-[--color-theme-primary]',
  },
  error: {
    icon: 'mdi:alert-circle',
    bgClass: 'bg-red-900/90 border-red-500',
    iconClass: 'text-red-400',
  },
  warning: {
    icon: 'mdi:alert',
    bgClass: 'bg-gray-900/90 border-[--color-theme-accent]',
    iconClass: 'text-[--color-theme-accent]',
  },
  info: {
    icon: 'mdi:information',
    bgClass: 'bg-gray-900/90 border-[--color-theme-primary]',
    iconClass: 'text-[--color-theme-primary]',
  },
}

const config = variantConfig[props.toast.variant]
</script>

<template>
  <div
    :class="[
      'toast',
      config.bgClass,
      'border-2 rounded-lg shadow-lg backdrop-blur-sm',
      'flex items-center gap-3 p-4 min-w-[300px] max-w-[500px]',
      'animate-slide-in',
    ]"
    role="alert"
  >
    <Icon :icon="config.icon" :class="['text-2xl', config.iconClass]" />
    <p class="flex-1 text-sm text-white font-medium">{{ toast.message }}</p>
    <span
      v-if="toast.count && toast.count > 1"
      class="px-2 py-0.5 text-xs font-bold rounded-full bg-[--color-theme-primary] text-black"
    >
      ×{{ toast.count }}
    </span>
    <button
      @click="emit('close', toast.id)"
      class="text-white/70 hover:text-white transition-colors"
      aria-label="Close"
    >
      <Icon icon="mdi:close" class="text-xl" />
    </button>
  </div>
</template>

<style scoped>
@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

.animate-slide-in {
  animation: slideIn 0.3s ease-out;
}

.toast {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}
</style>
