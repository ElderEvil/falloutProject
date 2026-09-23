<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import TerminalEmptyState from '@/core/components/common/TerminalEmptyState.vue'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/core/components/ui/tooltip'
import { useDwellerDetailContext } from './DwellerDetailContext'
import type { VisualAttributes } from '../models/dweller'
import DwellerIdentitySignal from './DwellerIdentitySignal.vue'

const ctx = useDwellerDetailContext()

const visualAttributes = computed<VisualAttributes | null>(
  () => ctx.dweller.value?.visual_attributes ?? null
)
const generatingAppearance = computed(() => ctx.generatingAppearance.value)
const isAnyGenerating = computed(() => ctx.isAnyGenerating.value)

// Helper to capitalize first letter
const capitalize = (str: string) => str.charAt(0).toUpperCase() + str.slice(1)

// Format attributes for display
const formattedAttributes = computed(() => {
  if (!visualAttributes.value) return []

  const attrs = visualAttributes.value
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
  const va = visualAttributes.value
  if (!va) return false
  const keys = Object.keys(va)
  return keys.some((k) => !IDENTITY_FIELDS.has(k))
})

/** True if AI can still generate (no substantial attributes yet). */
const canGenerateAppearance = computed(
  () => !visualAttributes.value || !hasSubstantialAttributes.value
)
</script>

<template>
  <div class="appearance-container">
    <div class="appearance-header">
      <div class="header-buttons">
        <TooltipProvider :delay-duration="200">
          <Tooltip v-if="canGenerateAppearance">
            <TooltipTrigger as-child>
              <Button
                @click="ctx.actions.generateAppearance()"
                class="generate-button"
                variant="outline"
                size="sm"
                :disabled="isAnyGenerating"
              >
                <Icon
                  :icon="generatingAppearance ? 'mdi:loading' : 'mdi:auto-fix'"
                  class="h-5 w-5"
                  :class="{ 'animate-spin': generatingAppearance }"
                />
                <span>{{ hasSubstantialAttributes ? 'Regenerate appearance' : 'Generate appearance' }}</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top"
              >Creates or replaces visual attributes; it does not generate a portrait</TooltipContent
            >
          </Tooltip>

          <Tooltip v-if="hasSubstantialAttributes">
            <TooltipTrigger as-child>
              <Button
                @click="ctx.actions.editAppearance()"
                class="generate-button"
                variant="outline"
                size="sm"
              >
                <Icon icon="mdi:pencil" class="h-5 w-5" />
                <span>Edit appearance</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">Adjust visual attributes manually</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>

    <div v-if="hasSubstantialAttributes" class="appearance-content">
      <DwellerIdentitySignal :visual-attributes="visualAttributes" hide-race />
      <div v-for="attr in formattedAttributes" :key="attr.label" class="attribute-row">
        <span class="attribute-label">{{ attr.label }}:</span>
        <span class="attribute-value">{{ attr.value }}</span>
      </div>
    </div>

    <TerminalEmptyState
      v-else
      icon="mdi:account-box-outline"
      title="No appearance yet"
      description="Generate this dweller's look to fill in build, hair, facial features, clothing and pose."
      compact
    >
      <template #actions>
        <Button
          variant="outline"
          size="sm"
          :disabled="isAnyGenerating"
          @click="ctx.actions.generateAppearance()"
        >
          <Icon
            :icon="generatingAppearance ? 'mdi:loading' : 'mdi:auto-fix'"
            class="h-4 w-4"
            :class="{ 'animate-spin': generatingAppearance }"
          />
          <span>Generate appearance</span>
        </Button>
      </template>
    </TerminalEmptyState>
  </div>
</template>

<style scoped>
.appearance-container {
  width: 100%;
}

.appearance-header {
  display: flex;
  justify-content: flex-start;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
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
</style>
