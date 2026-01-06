<script setup lang="ts">
import { computed } from 'vue';
import { Icon } from '@iconify/vue';
import UTooltip from '@/components/ui/UTooltip.vue';
import type { VisualAttributes } from '@/models/dweller';

interface Props {
  visualAttributes?: VisualAttributes | null;
  generatingAppearance?: boolean;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  (e: 'generate-appearance'): void;
}>();

// Helper to capitalize first letter
const capitalize = (str: string) => str.charAt(0).toUpperCase() + str.slice(1);

// Format attributes for display
const formattedAttributes = computed(() => {
  if (!props.visualAttributes) return [];

  const attrs = props.visualAttributes;
  const formatted: Array<{ label: string; value: string }> = [];

  if (attrs.height) formatted.push({ label: 'Height', value: capitalize(attrs.height) });
  if (attrs.build) formatted.push({ label: 'Build', value: capitalize(attrs.build) });
  if (attrs.hair_style || attrs.hair_color) {
    const hair = [attrs.hair_style, attrs.hair_color].filter((val): val is string => Boolean(val)).map(capitalize).join(', ');
    formatted.push({ label: 'Hair', value: hair });
  }
  if (attrs.eye_color) formatted.push({ label: 'Eyes', value: capitalize(attrs.eye_color) });
  if (attrs.skin_tone) formatted.push({ label: 'Skin Tone', value: capitalize(attrs.skin_tone) });
  if (attrs.appearance) formatted.push({ label: 'Appearance', value: capitalize(attrs.appearance) });
  if (attrs.facial_hair) formatted.push({ label: 'Facial Hair', value: capitalize(attrs.facial_hair) });
  if (attrs.makeup) formatted.push({ label: 'Makeup', value: capitalize(attrs.makeup) });
  if (attrs.clothing_style)
    formatted.push({ label: 'Clothing', value: capitalize(attrs.clothing_style) });

  if (attrs.distinguishing_features && attrs.distinguishing_features.length > 0) {
    const features = attrs.distinguishing_features.map(capitalize).join(', ');
    formatted.push({ label: 'Features', value: features });
  }

  return formatted;
});

const hasAttributes = computed(() => formattedAttributes.value.length > 0);
</script>

<template>
  <div class="appearance-container">
    <div class="appearance-header">
      <h3 class="appearance-title">Appearance</h3>
      <UTooltip text="Generate appearance with AI" position="top">
        <button
          @click="emit('generate-appearance')"
          class="generate-appearance-button"
          :disabled="generatingAppearance"
        >
          <Icon
            :icon="generatingAppearance ? 'mdi:loading' : 'mdi:auto-fix'"
            class="h-5 w-5"
            :class="{ 'animate-spin': generatingAppearance }"
          />
          <span>{{ hasAttributes ? 'Regenerate' : 'Generate' }}</span>
        </button>
      </UTooltip>
    </div>

    <div v-if="hasAttributes" class="appearance-content">
      <div v-for="attr in formattedAttributes" :key="attr.label" class="attribute-row">
        <span class="attribute-label">{{ attr.label }}:</span>
        <span class="attribute-value">{{ attr.value }}</span>
      </div>
    </div>

    <div v-else class="no-attributes">
      <p class="no-attributes-text">No appearance data generated</p>
      <p class="no-attributes-hint">Click the Generate button above to create visual attributes</p>
    </div>
  </div>
</template>

<style scoped>
.appearance-container {
  width: 100%;
}

.appearance-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 2px solid var(--color-theme-glow);
  padding-bottom: 0.5rem;
  margin-bottom: 1rem;
}

.appearance-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.generate-appearance-button {
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

.generate-appearance-button:hover:not(:disabled) {
  animation: none;
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 15px var(--color-theme-primary);
  background: rgba(31, 41, 55, 1);
}

.generate-appearance-button:disabled {
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

.appearance-content {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.3);
  border-left: 3px solid var(--color-theme-primary);
  border-radius: 4px;
}

.attribute-row {
  display: flex;
  gap: 0.5rem;
  font-size: 1rem;
  line-height: 1.7;
}

.attribute-label {
  color: var(--color-theme-primary);
  opacity: 0.7;
  font-weight: 600;
  min-width: 120px;
  flex-shrink: 0;
}

.attribute-value {
  color: var(--color-theme-primary);
  font-weight: 400;
}

.no-attributes {
  padding: 2rem 1rem;
  text-align: center;
  border: 1px dashed var(--color-theme-glow);
  border-radius: 4px;
  background: rgba(var(--color-theme-primary-rgb), 0.02);
}

.no-attributes-text {
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
  margin-bottom: 0.5rem;
}

.no-attributes-hint {
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.5;
}
</style>
