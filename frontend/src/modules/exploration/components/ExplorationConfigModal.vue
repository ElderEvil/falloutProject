<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Icon } from '@iconify/vue'

interface VaultMedicalSupplies {
  stimpaks: number
  radaways: number
}

interface DwellerInfo {
  dwellerId: string
  firstName: string
  lastName: string
  currentRoomId?: string
}

const props = defineProps<{
  dweller: DwellerInfo | null
  vaultMedicalSupplies: VaultMedicalSupplies
}>()

const emit = defineEmits<{
  confirm: [duration: number, stimpaks: number, radaways: number]
  cancel: []
}>()

const selectedDuration = ref(4)
const selectedStimpaks = ref(0)
const selectedRadaways = ref(0)

const DWELLER_MAX_SUPPLIES = 15

const maxStimpaks = computed(() =>
  Math.min(props.vaultMedicalSupplies.stimpaks, DWELLER_MAX_SUPPLIES)
)

const maxRadaways = computed(() =>
  Math.min(props.vaultMedicalSupplies.radaways, DWELLER_MAX_SUPPLIES)
)

// Reset values when dweller changes (modal opens)
watch(
  () => props.dweller,
  (dweller) => {
    if (dweller) {
      selectedDuration.value = 4
      selectedStimpaks.value = Math.min(
        5,
        props.vaultMedicalSupplies.stimpaks,
        DWELLER_MAX_SUPPLIES
      )
      selectedRadaways.value = Math.min(
        5,
        props.vaultMedicalSupplies.radaways,
        DWELLER_MAX_SUPPLIES
      )
    }
  }
)

const handleConfirm = () => {
  emit('confirm', selectedDuration.value, selectedStimpaks.value, selectedRadaways.value)
}

const handleCancel = () => {
  emit('cancel')
}
</script>

<template>
  <div v-if="dweller" class="modal-overlay" @click="handleCancel">
    <div class="modal-content" @click.stop>
      <h3 class="modal-title">
        <Icon icon="mdi:clock-outline" class="inline h-6 w-6" />
        Select Exploration Duration
      </h3>
      <p class="modal-subtitle">How long should {{ dweller.firstName }} explore?</p>
      <div class="duration-options">
        <button
          v-for="duration in [1, 2, 4, 8, 12, 24]"
          :key="duration"
          @click="selectedDuration = duration"
          class="duration-button"
          :class="{ active: selectedDuration === duration }"
        >
          {{ duration }}h
        </button>
      </div>

      <div class="medical-supplies">
        <h4 class="supply-title">
          <Icon icon="mdi:medical-bag" class="inline h-5 w-5" />
          Medical Supplies
        </h4>
        <div class="supply-inputs">
          <div class="supply-item">
            <div class="flex items-center justify-between mb-1">
              <label class="text-xs">Stimpaks (Heals HP)</label>
              <span class="text-xs font-bold"
                >{{ selectedStimpaks }} / {{ vaultMedicalSupplies.stimpaks }}</span
              >
            </div>
            <input
              type="range"
              v-model.number="selectedStimpaks"
              min="0"
              :max="maxStimpaks"
              class="supply-slider stimpak-slider"
            />
          </div>
          <div class="supply-item">
            <div class="flex items-center justify-between mb-1">
              <label class="text-xs">RadAway (Removes Rads)</label>
              <span class="text-xs font-bold"
                >{{ selectedRadaways }} / {{ vaultMedicalSupplies.radaways }}</span
              >
            </div>
            <input
              type="range"
              v-model.number="selectedRadaways"
              min="0"
              :max="maxRadaways"
              class="supply-slider radaway-slider"
            />
          </div>
        </div>
        <p class="text-[10px] text-orange-400 mt-2">
          * Selected items will be removed from vault storage and used automatically in the
          wasteland.
        </p>
      </div>

      <div class="modal-actions">
        <button @click="handleCancel" class="modal-button cancel">
          <Icon icon="mdi:close" class="h-5 w-5" />
          Cancel
        </button>
        <button @click="handleConfirm" class="modal-button confirm">
          <Icon icon="mdi:check" class="h-5 w-5" />
          Send to Wasteland
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.modal-content {
  background: rgba(20, 20, 20, 0.95);
  border: 2px solid rgba(205, 133, 63, 0.6);
  border-radius: 12px;
  padding: 2rem;
  max-width: 500px;
  width: 90%;
  font-family: 'Courier New', monospace;
  animation: slideUp 0.3s ease-out;
}

@keyframes slideUp {
  from {
    transform: translateY(50px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.modal-title {
  color: rgba(205, 133, 63, 1);
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.modal-subtitle {
  color: rgba(205, 133, 63, 0.7);
  font-size: 0.875rem;
  margin-bottom: 1.5rem;
}

.duration-options {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.duration-button {
  background: rgba(205, 133, 63, 0.2);
  border: 2px solid rgba(205, 133, 63, 0.4);
  color: rgba(205, 133, 63, 1);
  padding: 0.75rem;
  border-radius: 6px;
  font-size: 1rem;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: 'Courier New', monospace;
}

.duration-button:hover {
  background: rgba(205, 133, 63, 0.3);
  border-color: rgba(205, 133, 63, 0.6);
}

.duration-button.active {
  background: rgba(205, 133, 63, 0.5);
  border-color: rgba(205, 133, 63, 1);
  box-shadow: 0 0 15px rgba(205, 133, 63, 0.4);
}

.medical-supplies {
  margin-bottom: 2rem;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(205, 133, 63, 0.3);
  border-radius: 8px;
}

.supply-title {
  color: rgba(205, 133, 63, 1);
  font-size: 1rem;
  font-weight: bold;
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.supply-inputs {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.supply-item {
  display: flex;
  flex-direction: column;
}

.supply-slider {
  -webkit-appearance: none;
  width: 100%;
  height: 6px;
  border-radius: 3px;
  outline: none;
  background: rgba(205, 133, 63, 0.2);
}

.stimpak-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--color-success);
  cursor: pointer;
  box-shadow: 0 0 10px rgba(76, 175, 80, 0.5);
}

.radaway-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--color-caps);
  cursor: pointer;
  box-shadow: 0 0 10px rgba(255, 235, 59, 0.5);
}

.modal-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
}

.modal-button {
  padding: 0.75rem 1.5rem;
  border-radius: 6px;
  font-weight: bold;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: all 0.2s ease;
  font-family: 'Courier New', monospace;
  border: 2px solid;
}

.modal-button.cancel {
  background: rgba(128, 128, 128, 0.2);
  border-color: rgba(128, 128, 128, 0.5);
  color: rgba(200, 200, 200, 1);
}

.modal-button.cancel:hover {
  background: rgba(128, 128, 128, 0.3);
  border-color: rgba(128, 128, 128, 0.8);
}

.modal-button.confirm {
  background: var(--color-theme-glow);
  border-color: var(--color-theme-primary);
  color: var(--color-theme-primary);
}

.modal-button.confirm:hover {
  background: var(--color-theme-glow);
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 15px var(--color-theme-glow);
}
</style>
