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
import { computed, ref, useId } from 'vue'
import { useModalBehavior } from '@/core/composables/useModalBehavior'

interface Props {
  modelValue: boolean
  title?: string
  size?: 'sm' | 'md' | 'wide' | 'lg' | 'xl' | 'full'
  surface?: 'base' | 'raised' | 'sunken'
  closeOnEscape?: boolean
  closeOnClickOutside?: boolean
}

const {
  size = 'md',
  surface = 'raised',
  closeOnEscape = true,
  closeOnClickOutside = true,
  modelValue,
  title,
} = defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'close'): void
}>()

const sizeClasses = {
  sm: 'max-w-sm max-h-[60vh]',
  md: 'max-w-md max-h-[65vh]',
  wide: 'max-w-xl max-h-[75vh]',
  lg: 'max-w-5xl max-h-[80vh]',
  xl: 'max-w-6xl max-h-[90vh]',
  full: 'max-w-full mx-4 max-h-[90vh]',
}

const surfaceClasses = {
  base: 'bg-surface',
  raised: 'bg-surface-raised',
  sunken: 'bg-surface-sunken',
}

const close = () => {
  emit('update:modelValue', false)
  emit('close')
}

const handleBackdropClick = () => {
  if (closeOnClickOutside) {
    close()
  }
}

const modalTitleId = useId()
const modalLabel = computed(() =>
  title ? { 'aria-labelledby': modalTitleId } : { 'aria-label': 'Dialog' }
)

const modalContent = ref<HTMLElement | null>(null)
const { handleKeydown } = useModalBehavior(() => modelValue, close, {
  focusTarget: modalContent,
  closeOnEscape: () => closeOnEscape,
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="modelValue"
        class="fixed inset-0 z-modal flex items-center justify-center bg-surface-canvas/85"
        @click="handleBackdropClick"
      >
        <!-- Modal Content -->
        <div
          ref="modalContent"
          role="dialog"
          tabindex="-1"
          aria-modal="true"
          v-bind="modalLabel"
          :class="[
            'flex w-full flex-col overflow-hidden rounded-lg border-2 crt-screen',
            'border-theme-primary',
            surfaceClasses[surface],
            sizeClasses[size],
          ]"
          @click.stop
          @keydown="handleKeydown"
        >
          <!-- Header -->
          <div
            v-if="$slots.header || title"
            class="flex flex-shrink-0 items-center justify-between border-b border-theme-primary/25 bg-theme-primary/5 p-6 pb-4"
          >
            <slot name="header" :title-id="modalTitleId">
              <h2 :id="modalTitleId" class="text-2xl font-bold text-theme-primary terminal-glow">{{ title }}</h2>
            </slot>
            <button
              @click="close"
              class="flex-shrink-0 cursor-pointer p-1 text-theme-primary/60 transition-[color,transform] hover:text-theme-primary hover:scale-110 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-theme-primary"
              aria-label="Close modal"
            >
              <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          <!-- Body -->
          <div class="flex-1 overflow-y-auto px-5 pb-5">
            <slot></slot>
          </div>

          <!-- Footer -->
          <div v-if="$slots.footer" class="flex flex-shrink-0 justify-end border-t border-theme-primary/25 bg-surface-sunken/40 px-5 pt-3 pb-5">
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
