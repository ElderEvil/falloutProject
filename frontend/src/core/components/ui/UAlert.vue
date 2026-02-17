<script setup lang="ts">
import { ref } from 'vue'
import type { IconComponent } from '@/core/types/utils'

/**
 * UAlert - Terminal-themed alert/notification component
 *
 * Features:
 * - Color variants for different message types
 * - Dismissible option
 * - Icon support
 */

interface Props {
  variant?: 'success' | 'warning' | 'danger' | 'info'
  title?: string
  dismissible?: boolean
  icon?: IconComponent
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'info',
  dismissible: false,
})

const emit = defineEmits<{
  (e: 'close'): void
}>()

const isVisible = ref(true)

const close = () => {
  isVisible.value = false
  emit('close')
}

const variantClasses = {
  success:
    'bg-[color:var(--color-theme-primary)]/10 ' +
    'border-[color:var(--color-theme-primary)] ' +
    'text-[color:var(--color-theme-primary)]',
  warning:
    'bg-[color:var(--color-warning)]/10 ' +
    'border-[color:var(--color-warning)] ' +
    'text-[color:var(--color-warning)]',
  danger:
    'bg-[color:var(--color-danger)]/10 ' +
    'border-[color:var(--color-danger)] ' +
    'text-[color:var(--color-danger)]',
  info: 'bg-[color:var(--color-info)]/10 border-[color:var(--color-info)] text-[color:var(--color-info)]',
}

const alertClasses = ['rounded-lg border-2 p-4', variantClasses[props.variant]].join(' ')
</script>

<template>
  <Transition name="alert">
    <div v-if="isVisible" :class="alertClasses" role="alert">
      <div class="flex items-start gap-3">
        <!-- Icon -->
        <component v-if="icon" :is="icon" class="h-5 w-5 flex-shrink-0" />

        <!-- Content -->
        <div class="flex-1">
          <h4 v-if="title" class="font-bold mb-1">{{ title }}</h4>
          <slot></slot>
        </div>

        <!-- Close Button -->
        <button
          v-if="dismissible"
          @click="close"
          class="flex-shrink-0 hover:opacity-70 transition-opacity"
          aria-label="Dismiss alert"
        >
          <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.alert-enter-active,
.alert-leave-active {
  transition: all 0.3s ease;
}

.alert-enter-from {
  opacity: 0;
  transform: translateY(-10px);
}

.alert-leave-to {
  opacity: 0;
  transform: translateX(100%);
}
</style>
