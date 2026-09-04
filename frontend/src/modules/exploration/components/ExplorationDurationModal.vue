<script setup lang="ts">
import { ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { UButton, USlider } from '@/core/components/ui'

interface Props {
  show: boolean
  dwellerName: string
  maxStimpaks: number
  maxRadaways: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  confirm: [payload: { duration: number; stimpaks: number; radaways: number }]
  cancel: []
}>()

const selectedDuration = ref(4)
const selectedStimpaks = ref(0)
const selectedRadaways = ref(0)

const DURATION_DEFAULT = 4
const DEFAULT_STIMPAKS = 5
const DEFAULT_RADAWAYS = 5
const DWELLER_MAX_SUPPLIES = 15

watch(
  () => props.show,
  (isVisible, wasVisible) => {
    if (isVisible && !wasVisible) {
      selectedDuration.value = DURATION_DEFAULT
      selectedStimpaks.value = Math.min(DEFAULT_STIMPAKS, props.maxStimpaks, DWELLER_MAX_SUPPLIES)
      selectedRadaways.value = Math.min(DEFAULT_RADAWAYS, props.maxRadaways, DWELLER_MAX_SUPPLIES)
    }
  },
  { immediate: true }
)

const handleCancel = () => {
  emit('cancel')
}

const handleConfirm = () => {
  emit('confirm', {
    duration: selectedDuration.value,
    stimpaks: selectedStimpaks.value,
    radaways: selectedRadaways.value,
  })
}
</script>

<template>
  <div v-if="show" class="modal-overlay fixed inset-0 z-[2000] flex items-center justify-center bg-surface-canvas/90 animate-[fade-in_0.2s_ease-out]" @click="handleCancel">
    <div class="modal-content w-[90%] max-w-[500px] rounded-xl border-2 border-theme-primary/40 bg-surface-raised p-8 font-mono shadow-glow-lg animate-[slide-up_0.3s_ease-out]" @click.stop>
      <h3 class="mb-2 flex items-center gap-2 text-2xl font-bold text-theme-primary terminal-glow">
        <Icon icon="mdi:clock-outline" class="inline h-6 w-6" />
        Select Exploration Duration
      </h3>
      <p class="mb-6 text-sm text-theme-primary/70">How long should {{ dwellerName }} explore?</p>
      <div class="mb-6 grid grid-cols-3 gap-3">
        <button
          v-for="duration in [1, 2, 4, 8, 12, 24]"
          :key="duration"
          @click="selectedDuration = duration"
          class="duration-button cursor-pointer rounded-md border-2 border-theme-primary/30 bg-theme-primary/10 p-3 font-mono text-base font-bold text-theme-primary transition-all duration-200 hover:border-theme-primary/60 hover:bg-theme-primary/20"
          :class="selectedDuration === duration
            ? 'active border-theme-primary bg-theme-primary/25 shadow-glow-md'
            : ''"
        >
          {{ duration }}h
        </button>
      </div>

      <div class="mb-8 rounded-lg border border-theme-primary/25 bg-surface-sunken p-4">
        <h4 class="mb-4 flex items-center gap-2 text-base font-bold text-theme-primary">
          <Icon icon="mdi:medical-bag" class="inline h-5 w-5" />
          Medical Supplies
        </h4>
        <div class="flex flex-col gap-5">
          <div class="flex flex-col">
            <div class="flex items-center justify-between mb-1">
              <label class="text-xs text-theme-primary/80">Stimpaks (Heals HP)</label>
              <span class="text-xs font-bold text-theme-primary"
                >{{ selectedStimpaks }} / {{ maxStimpaks }}</span
              >
            </div>
            <USlider
              v-model="selectedStimpaks"
              :min="0"
              :max="Math.min(maxStimpaks, 15)"
              aria-label="Stimpaks to carry"
            />
          </div>
          <div class="flex flex-col">
            <div class="flex items-center justify-between mb-1">
              <label class="text-xs text-theme-primary/80">RadAway (Removes Rads)</label>
              <span class="text-xs font-bold text-theme-primary"
                >{{ selectedRadaways }} / {{ maxRadaways }}</span
              >
            </div>
            <USlider
              v-model="selectedRadaways"
              :min="0"
              :max="Math.min(maxRadaways, 15)"
              aria-label="RadAway to carry"
            />
          </div>
        </div>
        <p class="mt-2 text-[10px] text-theme-primary/55">
          * Selected items will be removed from vault storage and used automatically in the
          wasteland.
        </p>
      </div>

      <div class="flex justify-end gap-3">
        <UButton
          @click="handleCancel"
          class="modal-button cancel"
          variant="secondary"
          size="lg"
        >
          <Icon icon="mdi:close" class="h-5 w-5" />
          Cancel
        </UButton>
        <UButton
          @click="handleConfirm"
          class="modal-button confirm"
          size="lg"
        >
          <Icon icon="mdi:check" class="h-5 w-5" />
          Send to Wasteland
        </UButton>
      </div>
    </div>
  </div>
</template>

<style src="./ExplorationDurationModal.css" scoped></style>
