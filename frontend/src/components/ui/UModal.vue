<script setup lang="ts">
/**
 * UModal - Terminal-themed modal dialog
 *
 * Features:
 * - Backdrop with scanlines
 * - CRT screen effect
 * - Keyboard escape to close
 * - Click outside to close (optional)
 */

interface Props {
  modelValue: boolean
  title?: string
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full'
  closeOnEscape?: boolean
  closeOnClickOutside?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md',
  closeOnEscape: true,
  closeOnClickOutside: true
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'close'): void
}>()

const sizeClasses = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl',
  full: 'max-w-full mx-4'
}

const close = () => {
  emit('update:modelValue', false)
  emit('close')
}

const handleBackdropClick = () => {
  if (props.closeOnClickOutside) {
    close()
  }
}

const handleEscape = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && props.closeOnEscape) {
    close()
  }
}

// Register escape key listener when modal is open
import { onMounted, onUnmounted, watch } from 'vue'

watch(() => props.modelValue, (isOpen) => {
  if (isOpen) {
    document.addEventListener('keydown', handleEscape)
    document.body.style.overflow = 'hidden' // Prevent background scroll
  } else {
    document.removeEventListener('keydown', handleEscape)
    document.body.style.overflow = ''
  }
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleEscape)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="modelValue"
        class="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-modal"
        @click="handleBackdropClick"
      >
        <!-- Modal Content -->
        <div
          :class="[
            'bg-surface border-2 border-terminalGreen rounded-lg p-8 w-full crt-screen',
            sizeClasses[size]
          ]"
          @click.stop
        >
          <!-- Header -->
          <div v-if="$slots.header || title" class="flex items-center justify-between mb-6">
            <slot name="header">
              <h2 class="text-2xl font-bold terminal-glow">{{ title }}</h2>
            </slot>
            <button
              @click="close"
              class="text-gray-400 hover:text-terminalGreen transition-colors p-1"
              aria-label="Close modal"
            >
              <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Body -->
          <div class="mb-6">
            <slot></slot>
          </div>

          <!-- Footer -->
          <div v-if="$slots.footer" class="flex justify-end space-x-4">
            <slot name="footer">
              <UButton variant="secondary" @click="close">Cancel</UButton>
              <UButton variant="primary">Confirm</UButton>
            </slot>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
