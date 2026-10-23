<script setup lang="ts">
import { computed } from 'vue'
import TerminalEmptyState from '@/core/components/common/TerminalEmptyState.vue'
import { capitalize } from '@/core/utils/format'
import { formatStateOfBeing } from '../models/dweller'
import { useDwellerDetailContext } from './DwellerDetailContext'
import { isMature } from '../models/dweller'
import type { VisualAttributes } from '../models/dweller'
import DwellerIdentitySignal from './DwellerIdentitySignal.vue'

const ctx = useDwellerDetailContext()

const visualAttributes = computed<VisualAttributes | null>(
  () => ctx.dweller.value?.visual_attributes ?? null
)
const mature = computed(() => !!ctx.dweller.value && isMature(ctx.dweller.value))

// Format attributes for display
const formattedAttributes = computed(() => {
  if (!visualAttributes.value) return []

  const attrs = visualAttributes.value
  const formatted: Array<{ label: string; value: string }> = []

  // Physical attributes
  if (attrs.height) formatted.push({ label: 'Height', value: capitalize(attrs.height) })
  if (attrs.build) formatted.push({ label: 'Build', value: capitalize(attrs.build) })
  if (attrs.age) formatted.push({ label: 'Age', value: String(attrs.age) })
  if (attrs.state_of_being)
    formatted.push({ label: 'State', value: formatStateOfBeing(attrs.state_of_being) })
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
  if (mature.value && attrs.headgear)
    formatted.push({ label: 'Headgear', value: capitalize(attrs.headgear) })
  if (attrs.clothing_style)
    formatted.push({ label: 'Clothing', value: capitalize(attrs.clothing_style) })

  if (attrs.distinguishing_features && attrs.distinguishing_features.length > 0) {
    const features = attrs.distinguishing_features.map(capitalize).join(', ')
    formatted.push({ label: 'Features', value: features })
  }

  // Equipment
  if (mature.value && attrs.accessory)
    formatted.push({ label: 'Accessory', value: capitalize(attrs.accessory) })
  if (mature.value && attrs.object_held)
    formatted.push({ label: 'Object', value: capitalize(attrs.object_held) })

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
  const va = visualAttributes.value
  if (!va) return false
  return Object.entries(va).some(([key, value]) => {
    if (IDENTITY_FIELDS.has(key) || value == null || value === '') return false
    return !Array.isArray(value) || value.length > 0
  })
})
</script>

<template>
  <div class="appearance-container">
    <div v-if="hasSubstantialAttributes" class="appearance-content">
      <DwellerIdentitySignal :visual-attributes="visualAttributes" hide-race hide-state />
      <div v-for="attr in formattedAttributes" :key="attr.label" class="attribute-row">
        <span class="attribute-label">{{ attr.label }}:</span>
        <span class="attribute-value">{{ attr.value }}</span>
      </div>
    </div>

    <TerminalEmptyState
      v-else
      icon="mdi:account-box-outline"
      title="No appearance yet"
      description="No appearance details have been recorded for this dweller yet."
      compact
      transparent
    />
  </div>
</template>

<style scoped>
.appearance-container {
  width: 100%;
}

.appearance-content {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem;
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
  min-width: 9rem;
  flex-shrink: 0;
  text-align: right;
}

.attribute-value {
  color: var(--color-theme-primary);
  font-weight: 400;
}
</style>
