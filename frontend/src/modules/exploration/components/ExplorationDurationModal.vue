<script setup lang="ts">
import { ref, watch } from 'vue'
import { Icon } from '@iconify/vue'

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
  <div v-if="show" class="modal-overlay fixed inset-0 z-[2000] flex items-center justify-center bg-black/80 animate-[fade-in_0.2s_ease-out]" @click="handleCancel">
    <div class="modal-content w-[90%] max-w-[500px] rounded-xl border-2 border-[rgba(205,133,63,0.6)] bg-[rgba(20,20,20,0.95)] p-8 font-mono animate-[slide-up_0.3s_ease-out]" @click.stop>
      <h3 class="mb-2 flex items-center gap-2 text-2xl font-bold text-[rgba(205,133,63,1)]">
        <Icon icon="mdi:clock-outline" class="inline h-6 w-6" />
        Select Exploration Duration
      </h3>
      <p class="mb-6 text-sm text-[rgba(205,133,63,0.7)]">How long should {{ dwellerName }} explore?</p>
      <div class="mb-6 grid grid-cols-3 gap-3">
        <button
          v-for="duration in [1, 2, 4, 8, 12, 24]"
          :key="duration"
          @click="selectedDuration = duration"
          class="duration-button cursor-pointer rounded-md border-2 border-[rgba(205,133,63,0.4)] bg-[rgba(205,133,63,0.2)] p-3 font-mono text-base font-bold text-[rgba(205,133,63,1)] transition-all duration-200 hover:border-[rgba(205,133,63,0.6)] hover:bg-[rgba(205,133,63,0.3)]"
          :class="selectedDuration === duration
            ? 'active border-[rgba(205,133,63,1)] bg-[rgba(205,133,63,0.5)] shadow-[0_0_15px_rgba(205,133,63,0.4)]'
            : ''"
        >
          {{ duration }}h
        </button>
      </div>

      <div class="mb-8 rounded-lg border border-[rgba(205,133,63,0.3)] bg-black/40 p-4">
        <h4 class="mb-4 flex items-center gap-2 text-base font-bold text-[rgba(205,133,63,1)]">
          <Icon icon="mdi:medical-bag" class="inline h-5 w-5" />
          Medical Supplies
        </h4>
        <div class="flex flex-col gap-5">
          <div class="flex flex-col">
            <div class="flex items-center justify-between mb-1">
              <label class="text-xs">Stimpaks (Heals HP)</label>
              <span class="text-xs font-bold"
                >{{ selectedStimpaks }} / {{ maxStimpaks }}</span
              >
            </div>
            <input
              type="range"
              v-model.number="selectedStimpaks"
              min="0"
              :max="Math.min(maxStimpaks, 15)"
              class="supply-slider stimpak-slider"
            />
          </div>
          <div class="flex flex-col">
            <div class="flex items-center justify-between mb-1">
              <label class="text-xs">RadAway (Removes Rads)</label>
              <span class="text-xs font-bold"
                >{{ selectedRadaways }} / {{ maxRadaways }}</span
              >
            </div>
            <input
              type="range"
              v-model.number="selectedRadaways"
              min="0"
              :max="Math.min(maxRadaways, 15)"
              class="supply-slider radaway-slider"
            />
          </div>
        </div>
        <p class="text-[10px] text-orange-400 mt-2">
          * Selected items will be removed from vault storage and used automatically in the
          wasteland.
        </p>
      </div>

      <div class="flex justify-end gap-3">
        <button
          @click="handleCancel"
          class="modal-button cancel flex cursor-pointer items-center gap-2 rounded-md border-2 border-[rgba(128,128,128,0.5)] bg-[rgba(128,128,128,0.2)] px-6 py-3 font-mono font-bold text-[rgba(200,200,200,1)] transition-all duration-200 hover:border-[rgba(128,128,128,0.8)] hover:bg-[rgba(128,128,128,0.3)]"
        >
          <Icon icon="mdi:close" class="h-5 w-5" />
          Cancel
        </button>
        <button
          @click="handleConfirm"
          class="modal-button confirm flex cursor-pointer items-center gap-2 rounded-md border-2 border-theme-primary bg-theme-glow px-6 py-3 font-mono font-bold text-theme-primary transition-all duration-200 hover:shadow-[0_0_15px_var(--color-theme-glow)]"
        >
          <Icon icon="mdi:check" class="h-5 w-5" />
          Send to Wasteland
        </button>
      </div>
    </div>
  </div>
</template>

<style src="./ExplorationDurationModal.css" scoped></style>
