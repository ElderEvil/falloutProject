<script setup lang="ts">
import { Icon } from '@iconify/vue'
import UTooltip from '@/core/components/ui/UTooltip.vue'

interface Props {
  bio?: string | null
  firstName: string
  generatingBio?: boolean
  isAnyGenerating?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'generate-bio'): void
}>()
</script>

<template>
  <div class="dweller-bio">
    <div class="bio-header">
      <h3 class="bio-title">Biography</h3>
      <UTooltip text="Generate biography with AI" position="top">
        <button
          @click="emit('generate-bio')"
          class="generate-bio-button"
          :disabled="props.isAnyGenerating"
        >
          <Icon
            :icon="generatingBio ? 'mdi:loading' : 'mdi:pencil-plus'"
            class="h-5 w-5"
            :class="{ 'animate-spin': generatingBio }"
          />
          <span>{{ bio ? 'Regenerate' : 'Generate' }}</span>
        </button>
      </UTooltip>
    </div>
    <div class="bio-content">
      <template v-if="bio">
        <p class="bio-text">{{ bio }}</p>
      </template>
      <template v-else>
        <div class="bio-placeholder">
          <p class="placeholder-text">
            No biography available for {{ firstName }} yet.
          </p>
          <p class="placeholder-hint">
            Click "Generate" to create a unique backstory!
          </p>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.dweller-bio {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.bio-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 2px solid var(--color-theme-glow);
  padding-bottom: 0.5rem;
}

.bio-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.generate-bio-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: rgba(31, 41, 55, 0.8);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  color: var(--color-theme-primary);
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  animation: pulse-glow 2s ease-in-out infinite;
}

.generate-bio-button:hover:not(:disabled) {
  animation: none;
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 15px var(--color-theme-primary);
  background: rgba(31, 41, 55, 1);
}

.generate-bio-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

@keyframes pulse-glow {
  0%, 100% {
    box-shadow: 0 0 5px var(--color-theme-glow);
  }
  50% {
    box-shadow: 0 0 12px var(--color-theme-primary);
  }
}

.bio-content {
  padding: 1rem;
  background: rgba(0, 0, 0, 0.3);
  border-left: 3px solid var(--color-theme-primary);
  border-radius: 4px;
}

.bio-text {
  max-width: 70ch;
  line-height: 1.7;
  color: var(--color-theme-primary);
  font-size: 1rem;
  text-shadow: 0 0 3px var(--color-theme-glow);
  white-space: pre-wrap;
}

.bio-placeholder {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  text-align: center;
  padding: 2rem 1rem;
}

.placeholder-text {
  color: var(--color-theme-primary);
  font-size: 1rem;
  text-shadow: 0 0 2px var(--color-theme-glow);
  opacity: 0.7;
}

.placeholder-hint {
  color: var(--color-theme-primary);
  font-size: 0.875rem;
  font-style: italic;
  text-shadow: 0 0 2px var(--color-theme-glow);
  opacity: 0.5;
}
</style>
