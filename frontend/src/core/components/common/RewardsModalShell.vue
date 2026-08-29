<script setup lang="ts">
/**
 * RewardsModalShell — shared CRT-styled modal shell for reward displays.
 *
 * Provides the overlay, animated content frame, header (icon + title + close),
 * scrollable body, and footer. Consumers supply body content via the default
 * slot and action buttons via the footer slot.
 *
 * Accessibility: renders as a dialog with focus trapped while open, Escape to
 * close, and focus restored to the previously focused element on close.
 */
import { nextTick, onUnmounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'

const props = withDefaults(
  defineProps<{
    show: boolean
    title: string
    headerIcon?: string
    maxWidth?: string
  }>(),
  { headerIcon: 'mdi:treasure-chest', maxWidth: '800px' }
)

const emit = defineEmits<{ close: [] }>()

const modalRef = ref<HTMLElement | null>(null)
let previouslyFocused: HTMLElement | null = null

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])'

const handleKeydown = (event: KeyboardEvent): void => {
  if (event.key === 'Escape') {
    emit('close')
    return
  }
  if (event.key !== 'Tab' || !modalRef.value) return

  const focusable = modalRef.value.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
  if (focusable.length === 0) return

  const first = focusable[0]!
  const last = focusable[focusable.length - 1]!

  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

watch(
  () => props.show,
  async (show) => {
    if (show) {
      previouslyFocused = document.activeElement as HTMLElement | null
      await nextTick()
      modalRef.value?.focus()
    } else {
      previouslyFocused?.focus()
      previouslyFocused = null
    }
  }
)

onUnmounted(() => {
  previouslyFocused?.focus()
})
</script>

<template>
  <Teleport to="body">
    <div v-if="show" class="modal-overlay" @click="emit('close')">
      <div
        ref="modalRef"
        class="modal-content"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
        tabindex="-1"
        :style="{ maxWidth }"
        @click.stop
        @keydown="handleKeydown"
      >
        <div class="modal-header">
          <div class="header-title">
            <Icon :icon="headerIcon" class="header-icon" />
            <h2 class="title">{{ title }}</h2>
          </div>
          <button class="close-btn" aria-label="Close" @click="emit('close')">
            <Icon icon="mdi:close" />
          </button>
        </div>

        <div class="modal-body">
          <slot />
        </div>

        <div v-if="$slots.footer" class="modal-footer">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  backdrop-filter: blur(4px);
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.modal-content {
  background: linear-gradient(180deg, var(--color-surface-raised) 0%, var(--color-surface) 100%);
  border: 2px solid var(--color-theme-primary);
  border-radius: 10px;
  width: 90%;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow:
    0 0 40px var(--color-theme-glow),
    inset 0 1px 0 color-mix(in srgb, var(--color-theme-primary) 15%, transparent);
  animation: slideUp 0.3s ease;
}

@keyframes slideUp {
  from {
    transform: translateY(20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 2px solid color-mix(in srgb, var(--color-theme-primary) 30%, transparent);
  background: linear-gradient(180deg, color-mix(in srgb, var(--color-theme-primary) 4%, transparent), transparent);
  border-radius: 8px 8px 0 0;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.header-icon {
  width: 2rem;
  height: 2rem;
  color: var(--color-rarity-legendary);
  filter: drop-shadow(0 0 8px rgba(255, 215, 0, 0.6));
}

.title {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 10px var(--color-theme-glow);
}

.close-btn {
  background: transparent;
  border: 2px solid color-mix(in srgb, var(--color-theme-primary) 50%, transparent);
  color: var(--color-theme-primary);
  padding: 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
}

.close-btn:hover {
  background: color-mix(in srgb, var(--color-theme-primary) 30%, transparent);
  border-color: var(--color-theme-primary);
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1.25rem 1.5rem;
  border-top: 2px solid color-mix(in srgb, var(--color-theme-primary) 30%, transparent);
  background: color-mix(in srgb, var(--color-surface-sunken) 40%, transparent);
  border-radius: 0 0 8px 8px;
}

.modal-content:focus {
  outline: none;
}

@media (prefers-reduced-motion: reduce) {
  .modal-overlay,
  .modal-content {
    animation: none;
  }
}
</style>
