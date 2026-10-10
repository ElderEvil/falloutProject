<script setup lang="ts">
import { Slider } from '@/core/components/ui/slider'

interface Props {
  selectedStimpaks: number
  selectedRadaways: number
  /** Vault stock, shown as the "/ max" total and disables the slider at zero. */
  maxStimpaks: number
  maxRadaways: number
  /** Slider ceiling: min(maxStimpaks, 15). */
  stimpakMax: number
  /** Slider ceiling: min(maxRadaways, 15). */
  radawayMax: number
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:stimpaks', value: number[] | undefined): void
  (e: 'update:radaways', value: number[] | undefined): void
}>()
</script>

<template>
  <div class="flex flex-shrink-0 flex-col gap-3 border-t border-theme-primary/25 px-5 py-3">
    <div class="flex items-center gap-3">
      <span class="w-20 text-xs text-theme-primary/80">Stimpaks</span>
      <Slider
        class="flex-1"
        :model-value="stimpakMax > 0 ? [selectedStimpaks] : []"
        :min="0"
        :max="stimpakMax"
        :disabled="maxStimpaks <= 0"
        aria-label="Stimpaks to carry"
        @update:model-value="emit('update:stimpaks', $event)"
      />
      <span class="w-14 text-right text-xs font-bold text-theme-primary"
        >{{ selectedStimpaks }} / {{ maxStimpaks }}</span
      >
    </div>
    <div class="flex items-center gap-3">
      <span class="w-20 text-xs text-theme-primary/80">RadAway</span>
      <Slider
        class="flex-1"
        :model-value="radawayMax > 0 ? [selectedRadaways] : []"
        :min="0"
        :max="radawayMax"
        :disabled="maxRadaways <= 0"
        aria-label="RadAway to carry"
        @update:model-value="emit('update:radaways', $event)"
      />
      <span class="w-14 text-right text-xs font-bold text-theme-primary"
        >{{ selectedRadaways }} / {{ maxRadaways }}</span
      >
    </div>
  </div>
</template>
