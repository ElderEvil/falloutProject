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
import UButton from './UButton.vue'

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
  sm: 'max-w-sm max-h-[60vh]',
  md: 'max-w-md max-h-[65vh]',
  lg: 'max-w-5xl max-h-[80vh]',
  xl: 'max-w-6xl max-h-[90vh]',
  full: 'max-w-full mx-4 max-h-[90vh]'
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
            'bg-surface border-2 rounded-lg w-full crt-screen flex flex-col overflow-hidden',
            sizeClasses[size]
          ]"
          style="border-color: var(--color-terminal-green)"
          @click.stop
        >
          <!-- Header -->
          <div v-if="$slots.header || title" class="flex items-center justify-between p-6 pb-4 flex-shrink-0">
            <slot name="header">
              <h2 class="text-2xl font-bold terminal-glow">{{ title }}</h2>
            </slot>
            <button
              @click="close"
              class="modal-close-btn flex-shrink-0"
              aria-label="Close modal"
            >
              <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Body -->
          <div class="flex-1 overflow-y-auto px-6 pb-6">
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

.modal-close-btn {
  background: none;
  border: none;
  color: #888;
  cursor: pointer;
  padding: 0.25rem;
  transition: all 0.2s;
}

.modal-close-btn:hover {
  color: var(--color-terminal-green);
  transform: scale(1.1);
}
</style>
