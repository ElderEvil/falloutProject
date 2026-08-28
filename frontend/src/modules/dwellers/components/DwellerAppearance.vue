<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import UTooltip from '@/core/components/ui/UTooltip.vue'
import UButton from '@/core/components/ui/UButton.vue'
import type { VisualAttributes } from '../models/dweller'
import DwellerIdentitySignal from './DwellerIdentitySignal.vue'

interface Props {
  visualAttributes?: VisualAttributes | null
  generatingAppearance?: boolean
  isAnyGenerating?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'generate-appearance'): void
  (e: 'edit'): void
}>()

// Helper to capitalize first letter
const capitalize = (str: string) => str.charAt(0).toUpperCase() + str.slice(1)

// Format attributes for display
const formattedAttributes = computed(() => {
  if (!props.visualAttributes) return []

  const attrs = props.visualAttributes
  const formatted: Array<{ label: string; value: string }> = []

  // Physical attributes
  if (attrs.height) formatted.push({ label: 'Height', value: capitalize(attrs.height) })
  if (attrs.build) formatted.push({ label: 'Build', value: capitalize(attrs.build) })
  if (attrs.age) formatted.push({ label: 'Age', value: String(attrs.age) })
  if (attrs.hair_style || attrs.hair_color) {
    const hair = [attrs.hair_style, attrs.hair_color]
      .filter((val): val is string => Boolean(val))
      .map(capitalize)
      .join(', ')
    formatted.push({ label: 'Hair', value: hair })
  }
  if (attrs.eye_color) formatted.push({ label: 'Eyes', value: capitalize(attrs.eye_color) })
  if (attrs.skin_tone) formatted.push({ label: 'Skin Tone', value: capitalize(attrs.skin_tone) })
  if (attrs.appearance) formatted.push({ label: 'Appearance', value: capitalize(attrs.appearance) })
  if (attrs.facial_hair)
    formatted.push({ label: 'Facial Hair', value: capitalize(attrs.facial_hair) })
  if (attrs.makeup) formatted.push({ label: 'Makeup', value: capitalize(attrs.makeup) })
  if (attrs.expression) formatted.push({ label: 'Expression', value: capitalize(attrs.expression) })
  if (attrs.headgear) formatted.push({ label: 'Headgear', value: capitalize(attrs.headgear) })
  if (attrs.clothing_style)
    formatted.push({ label: 'Clothing', value: capitalize(attrs.clothing_style) })

  if (attrs.distinguishing_features && attrs.distinguishing_features.length > 0) {
    const features = attrs.distinguishing_features.map(capitalize).join(', ')
    formatted.push({ label: 'Features', value: features })
  }

  // Equipment
  if (attrs.accessory) formatted.push({ label: 'Accessory', value: capitalize(attrs.accessory) })
  if (attrs.object_held) formatted.push({ label: 'Object', value: capitalize(attrs.object_held) })

  // Scene
  if (attrs.pose) formatted.push({ label: 'Pose', value: capitalize(attrs.pose) })
  if (attrs.background) formatted.push({ label: 'Background', value: capitalize(attrs.background) })
  if (attrs.voice_line_text)
    formatted.push({ label: 'Voice Line', value: `"${attrs.voice_line_text}"` })

  return formatted
})

/** Identity-only fields that the backend considers "not substantial". */
const IDENTITY_FIELDS = new Set(['race', 'faction', 'age', 'state_of_being'])

/** True if visual_attributes has content beyond basic identity defaults. */
const hasSubstantialAttributes = computed(() => {
  const va = props.visualAttributes
  if (!va) return false
  const keys = Object.keys(va)
  return keys.some((k) => !IDENTITY_FIELDS.has(k))
})

/** True if AI can still generate (no substantial attributes yet). */
const canGenerateAppearance = computed(
  () => !props.visualAttributes || !hasSubstantialAttributes.value
)

const hasAttributes = computed(() => Boolean(props.visualAttributes && Object.keys(props.visualAttributes).length))
</script>

<template>
  <div class="appearance-container">
    <div class="appearance-header">
      <h3 class="appearance-title">Appearance</h3>
      <div class="header-buttons">
        <UTooltip
          v-if="canGenerateAppearance"
          text="Creates or replaces visual attributes; it does not generate a portrait"
          position="top"
        >
          <UButton
            @click="emit('generate-appearance')"
            class="generate-button"
            variant="secondary"
            size="sm"
            :disabled="props.isAnyGenerating"
          >
            <Icon
              :icon="generatingAppearance ? 'mdi:loading' : 'mdi:auto-fix'"
              class="h-5 w-5"
              :class="{ 'animate-spin': generatingAppearance }"
            />
            <span>{{ hasAttributes ? 'Regenerate appearance' : 'Generate appearance' }}</span>
          </UButton>
        </UTooltip>

        <UTooltip v-if="hasAttributes" text="Adjust visual attributes manually" position="top">
          <UButton @click="emit('edit')" class="generate-button" variant="secondary" size="sm">
            <Icon icon="mdi:pencil" class="h-5 w-5" />
            <span>Edit appearance</span>
          </UButton>
        </UTooltip>
      </div>
    </div>

    <div v-if="hasAttributes" class="appearance-content">
      <DwellerIdentitySignal :visual-attributes="visualAttributes" />
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
  flex-wrap: wrap;
  gap: 0.5rem;
}

.appearance-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.header-buttons {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
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
