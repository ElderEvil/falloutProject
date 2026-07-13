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

const {
  size = 'md',
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
  lg: 'max-w-5xl max-h-[80vh]',
  xl: 'max-w-6xl max-h-[90vh]',
  full: 'max-w-full mx-4 max-h-[90vh]',
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

const handleEscape = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && closeOnEscape) {
    close()
  }
}

// Register escape key listener when modal is open
import { useId, onUnmounted, watch, computed, ref, nextTick } from 'vue'

const modalTitleId = useId()
const modalLabel = computed(() =>
  title ? { 'aria-labelledby': modalTitleId } : { 'aria-label': 'Dialog' }
)

// --- Focus trap ---
const modalContent = ref<HTMLElement | null>(null)
const previousActiveElement = ref<HTMLElement | null>(null)

const FOCUSABLE_SELECTOR =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"]):not([disabled])'

function getFocusableElements(): HTMLElement[] {
  if (!modalContent.value) return []
  return Array.from(modalContent.value.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
}

function focusFirstElement(): void {
  const elements = getFocusableElements()
  if (elements.length > 0) {
    elements[0].focus()
  }
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Tab') return

  const elements = getFocusableElements()
  if (elements.length === 0) {
    event.preventDefault()
    return
  }

  const firstElement = elements[0]
  const lastElement = elements[elements.length - 1]

  if (event.shiftKey) {
    if (document.activeElement === firstElement) {
      event.preventDefault()
      lastElement.focus()
    }
  } else {
    if (
      document.activeElement === lastElement ||
      !modalContent.value?.contains(document.activeElement)
    ) {
      event.preventDefault()
      firstElement.focus()
    }
  }
}

watch(
  () => modelValue,
  async (isOpen) => {
    if (isOpen) {
      previousActiveElement.value = document.activeElement as HTMLElement | null
      document.addEventListener('keydown', handleEscape)
      document.body.style.overflow = 'hidden' // Prevent background scroll
      await nextTick()
      focusFirstElement()
    } else {
      document.removeEventListener('keydown', handleEscape)
      document.body.style.overflow = ''
      if (previousActiveElement.value && document.body.contains(previousActiveElement.value)) {
        previousActiveElement.value.focus()
      }
      previousActiveElement.value = null
    }
  }
)

onUnmounted(() => {
  document.removeEventListener('keydown', handleEscape)
  document.body.style.overflow = ''
  if (previousActiveElement.value && document.body.contains(previousActiveElement.value)) {
    previousActiveElement.value.focus()
  }
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
          ref="modalContent"
          role="dialog"
          aria-modal="true"
          v-bind="modalLabel"
          :class="[
            'bg-surface border-2 rounded-lg w-full crt-screen flex flex-col overflow-hidden',
            'border-terminalGreen',
            sizeClasses[size],
          ]"
          @click.stop
          @keydown="handleKeydown"
        >
          <!-- Header -->
          <div
            v-if="$slots.header || title"
            class="flex items-center justify-between p-6 pb-4 flex-shrink-0"
          >
            <slot name="header">
              <h2 :id="modalTitleId" class="text-2xl font-bold terminal-glow">{{ title }}</h2>
            </slot>
            <button @click="close" class="modal-close-btn flex-shrink-0" aria-label="Close modal">
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
  color: var(--color-gray-500);
  cursor: pointer;
  padding: 0.25rem;
  transition: all 0.2s;
}

.modal-close-btn:hover {
  color: var(--color-terminal-green);
  transform: scale(1.1);
}
</style>
