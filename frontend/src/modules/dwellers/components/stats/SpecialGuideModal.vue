<script setup lang="ts">
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import { SPECIAL_BARS_GUIDE, SPECIAL_GUIDE } from '../../models/specialGuide'

defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const close = () => emit('update:modelValue', false)
</script>

<template>
  <TerminalModal
    :open="modelValue"
    title="S.P.E.C.I.A.L. Field Guide"
    size="md"
    max-height="65"
    @close="close"
  >
    <div class="flex-1 overflow-y-auto px-5 pt-5 pb-5">
    <div class="guide-list">
      <div v-for="entry in SPECIAL_GUIDE" :key="entry.letter" class="guide-entry">
        <div class="guide-header">
          <span class="guide-letter">{{ entry.letter }}</span>
          <div>
            <p class="guide-label">{{ entry.label }}</p>
            <p class="guide-tagline">{{ entry.tagline }}</p>
          </div>
        </div>
        <ul class="guide-effects">
          <li v-for="effect in entry.effects" :key="effect">{{ effect }}</li>
        </ul>
      </div>
    </div>
    <p class="guide-bars">{{ SPECIAL_BARS_GUIDE }}</p>
    </div>
  </TerminalModal>
</template>

<style scoped>
.guide-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.guide-entry {
  padding: 0.5rem;
  background: rgba(0, 0, 0, 0.3);
  border-left: 2px solid var(--color-theme-glow);
  border-radius: 4px;
}

.guide-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.guide-letter {
  font-weight: 700;
  font-size: 1rem;
  color: var(--color-theme-accent);
  min-width: 1.25rem;
  text-align: center;
}

.guide-label {
  font-weight: 600;
  font-size: 0.8125rem;
  color: var(--color-theme-primary);
}

.guide-tagline {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.75;
}

.guide-effects {
  margin: 0;
  padding-left: 1.75rem;
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.85;
  line-height: 1.5;
  list-style-type: square;
}

.guide-bars {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--color-theme-glow);
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
  line-height: 1.5;
}
</style>
