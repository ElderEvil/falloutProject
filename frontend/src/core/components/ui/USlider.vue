<script setup lang="ts">
/**
 * USlider - Terminal-themed range slider.
 *
 * Single shared slider for the whole app (sound volumes, supply pickers,
 * radio speedup, appearance age). Track tints from the accent color; the
 * thumb is a solid round knob in the accent color.
 */
import { computed } from 'vue'

type Accent = 'primary' | 'success' | 'caps' | 'danger'

interface Props {
  modelValue: number
  min?: number
  max?: number
  step?: number
  /** Semantic accent for thumb + track tint (default: theme primary). */
  accent?: Accent
  'aria-label'?: string
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  min: 0,
  max: 100,
  step: 1,
  accent: 'primary',
  'aria-label': undefined,
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: number]
}>()

const accentVar = computed(
  () => `var(--color-${props.accent === 'primary' ? 'theme-primary' : props.accent})`
)

const onInput = (event: Event) => {
  emit('update:modelValue', Number((event.target as HTMLInputElement).value))
}
</script>

<template>
  <input
    type="range"
    :value="modelValue"
    :min="min"
    :max="max"
    :step="step"
    :disabled="disabled"
    :aria-label="props['aria-label']"
    class="uslider"
    :style="{ '--slider-accent': accentVar }"
    @input="onInput"
  />
</template>

<style scoped>
.uslider {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 6px;
  border-radius: 3px;
  outline: none;
  background: color-mix(in srgb, var(--slider-accent) 20%, transparent);
  cursor: pointer;
}

.uslider:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.uslider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--slider-accent);
  box-shadow: 0 0 10px color-mix(in srgb, var(--slider-accent) 50%, transparent);
  cursor: pointer;
}

.uslider::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border: none;
  border-radius: 50%;
  background: var(--slider-accent);
  box-shadow: 0 0 10px color-mix(in srgb, var(--slider-accent) 50%, transparent);
  cursor: pointer;
}

.uslider:focus-visible {
  box-shadow: 0 0 0 2px var(--color-theme-glow);
}
</style>
