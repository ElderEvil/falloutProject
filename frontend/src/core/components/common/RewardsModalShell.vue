<script setup lang="ts">
/**
 * RewardsModalShell — shared CRT-styled modal shell for reward displays.
 *
 * Provides the overlay, animated content frame, header (icon + title + close),
 * scrollable body, and footer. Consumers supply body content via the default
 * slot and action buttons via the footer slot.
 */
import { Icon } from '@iconify/vue'

withDefaults(
  defineProps<{
    show: boolean
    title: string
    headerIcon?: string
    maxWidth?: string
  }>(),
  { headerIcon: 'mdi:treasure-chest', maxWidth: '800px' }
)

const emit = defineEmits<{ close: [] }>()
</script>

<template>
  <Teleport to="body">
    <div v-if="show" class="modal-overlay" @click="emit('close')">
      <div class="modal-content" :style="{ maxWidth }" @click.stop>
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
  background: var(--color-surface-dark);
  border: 2px solid var(--color-theme-primary);
  border-radius: 8px;
  width: 90%;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 0 40px var(--color-theme-glow);
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
}
</style>
