<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRadioStore } from '../stores/radio'
import type { RadioMode } from '@/modules/radio/models/radio'
import UCard from '@/core/components/ui/UCard.vue'
import UButton from '@/core/components/ui/UButton.vue'
import UBadge from '@/core/components/ui/UBadge.vue'

interface Props {
  vaultId: string
}

const props = defineProps<Props>()

defineEmits<{
  'manual-recruit': []
}>()

const radioStore = useRadioStore()

const stats = computed(() => radioStore.radioStats)
const isLoading = computed(() => radioStore.isLoading)
const isRecruiting = computed(() => radioStore.isRecruiting)

const formatRate = computed(() => {
  return radioStore.formatRecruitmentRate(stats.value)
})

const estimatedTime = computed(() => {
  if (!stats.value || stats.value.estimated_hours_per_recruit === 0) {
    return 'N/A'
  }

  const hours = stats.value.estimated_hours_per_recruit
  if (hours < 1) {
    return `${Math.round(hours * 60)} min`
  } else if (hours < 24) {
    return `${hours.toFixed(1)} hours`
  } else {
    return `${(hours / 24).toFixed(1)} days`
  }
})

const currentMode = computed(() => stats.value?.radio_mode || 'recruitment')
const isRecruitmentMode = computed(() => currentMode.value === 'recruitment')

async function refreshStats() {
  await radioStore.fetchRadioStats(props.vaultId)
}

async function toggleMode() {
  const newMode: RadioMode = isRecruitmentMode.value ? 'happiness' : 'recruitment'
  await radioStore.setRadioMode(props.vaultId, newMode)
}

// Speedup controls
const selectedRoomIndex = ref(0)
const currentSpeedup = computed(() => {
  if (!stats.value?.speedup_multipliers?.length) return 1.0
  return stats.value.speedup_multipliers[selectedRoomIndex.value]?.speedup || 1.0
})

// Local state for slider to avoid lag
const localSpeedup = ref(1.0)
let debounceTimer: ReturnType<typeof setTimeout> | null = null

// Update local speedup when actual speedup changes
watch(currentSpeedup, (newValue) => {
  localSpeedup.value = newValue
})

function handleSliderChange(value: number) {
  // Update local state immediately for smooth UI
  localSpeedup.value = value

  // Debounce backend update
  if (debounceTimer) {
    clearTimeout(debounceTimer)
  }

  debounceTimer = setTimeout(async () => {
    if (!stats.value?.speedup_multipliers?.length) return

    const roomId = stats.value.speedup_multipliers[selectedRoomIndex.value]?.room_id
    if (roomId) {
      await radioStore.setRadioSpeedup(props.vaultId, roomId, value)
    }
  }, 500) // Wait 500ms after user stops sliding
}

// Initialize local speedup on mount
onMounted(() => {
  localSpeedup.value = currentSpeedup.value
  refreshStats()
})

</script>

<template>
  <UCard class="radio-stats-panel">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-xl font-mono" style="color: var(--color-theme-primary);">📻 Radio Room</h2>
      <UButton @click="refreshStats" :disabled="isLoading" size="sm">
        Refresh
      </UButton>
    </div>

    <div v-if="isLoading" class="text-center py-4">
      <div class="text-2xl animate-pulse">📻</div>
      <p class="text-sm text-gray-400 mt-1">Loading...</p>
    </div>

    <div v-else-if="!stats || !stats.has_radio" class="text-center py-8 text-gray-400">
      <p>No radio room built yet.</p>
      <p class="text-sm mt-2">Build a radio room to attract new dwellers!</p>
    </div>

    <div v-else class="space-y-4">
      <!-- Radio Mode Toggle -->
      <div class="radio-mode-panel">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm font-semibold" style="color: var(--color-theme-primary);">Radio Mode</span>
          <UBadge :variant="isRecruitmentMode ? 'info' : 'default'">
            {{ isRecruitmentMode ? 'Recruitment' : 'Happiness' }}
          </UBadge>
        </div>
        <p class="text-xs text-gray-400 mb-3">
          {{ isRecruitmentMode
            ? 'Attracts new dwellers to your vault'
            : 'Boosts happiness for all dwellers' }}
        </p>
        <UButton @click="toggleMode" size="sm" class="w-full mode-switch-button">
          Switch to {{ isRecruitmentMode ? 'Happiness Mode' : 'Recruitment Mode' }}
        </UButton>
      </div>

      <!-- Speedup Controls -->
      <div class="speedup-panel">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm font-semibold" style="color: var(--color-theme-primary);">Speedup Multiplier</span>
          <UBadge variant="warning">{{ localSpeedup.toFixed(1) }}x</UBadge>
        </div>

        <!-- Room selector if multiple radio rooms -->
        <div v-if="stats.speedup_multipliers.length > 1" class="mb-3">
          <label class="text-xs text-gray-400 mb-1 block">Radio Room:</label>
          <select
            v-model="selectedRoomIndex"
            class="room-selector"
          >
            <option
              v-for="(_, index) in stats.speedup_multipliers"
              :key="index"
              :value="index"
            >
              Radio Room {{ index + 1 }}
            </option>
          </select>
        </div>

        <!-- Slider -->
        <div class="space-y-2">
          <input
            type="range"
            min="1"
            max="10"
            step="0.5"
            :value="localSpeedup"
            @input="(e) => handleSliderChange(parseFloat((e.target as HTMLInputElement).value))"
            class="speedup-slider"
          />
          <div class="flex justify-between text-xs text-gray-500">
            <span>1x</span>
            <span>5.5x</span>
            <span>10x</span>
          </div>
        </div>
        <p class="text-xs text-gray-400 mt-2">
          Higher speedup = faster {{ isRecruitmentMode ? 'recruitment' : 'happiness gain' }}
        </p>
      </div>

      <div class="divider"></div>

      <!-- Stats (only show if in recruitment mode) -->
      <div v-if="isRecruitmentMode" class="space-y-2">
        <div class="flex justify-between items-center">
          <span class="text-gray-400">Radio Rooms:</span>
          <span class="stat-value">{{ stats.radio_rooms_count }}</span>
        </div>

        <div class="flex justify-between items-center">
          <span class="text-gray-400">Recruitment Rate:</span>
          <span class="stat-value">{{ formatRate }}</span>
        </div>

        <div class="flex justify-between items-center">
          <span class="text-gray-400">Avg. Time Per Recruit:</span>
          <span class="stat-value">{{ estimatedTime }}</span>
        </div>
      </div>

      <div class="divider"></div>

      <!-- Manual recruitment -->
      <div class="space-y-2">
        <div class="flex justify-between items-center">
          <span class="text-gray-400">Manual Recruitment:</span>
<UBadge variant="warning">
            {{ stats.manual_cost_caps }} caps
          </UBadge>
        </div>

        <UButton
          @click="$emit('manual-recruit')"
          :disabled="isRecruiting"
          variant="primary"
          class="w-full recruit-button"
        >
          {{ isRecruiting ? 'Recruiting...' : 'Recruit Dweller Now' }}
        </UButton>
      </div>
    </div>
  </UCard>
</template>

<style scoped>
.radio-mode-panel,
.speedup-panel {
  background-color: rgba(0, 0, 0, 0.3);
  border: 2px solid var(--color-theme-border);
  border-radius: 8px;
  padding: 12px;
}

.room-selector {
  width: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  border: 2px solid var(--color-theme-border);
  color: var(--color-theme-primary);
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 0.875rem;
}

.room-selector:focus {
  outline: none;
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 0 2px var(--color-theme-glow);
}

.speedup-slider {
  width: 100%;
  height: 6px;
  cursor: pointer;
  -webkit-appearance: none;
  appearance: none;
  background: rgba(0, 0, 0, 0.5);
  border-radius: 5px;
  outline: none;
}

.speedup-slider::-webkit-slider-track {
  width: 100%;
  height: 6px;
  background: rgba(0, 0, 0, 0.5);
  border-radius: 5px;
}

.speedup-slider::-moz-range-track {
  width: 100%;
  height: 6px;
  background: rgba(0, 0, 0, 0.5);
  border-radius: 5px;
}

.speedup-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--color-theme-primary);
  border: 2px solid var(--color-theme-accent);
  cursor: pointer;
  box-shadow: 0 0 8px var(--color-theme-glow);
  transition: transform 0.2s;
}

.speedup-slider::-webkit-slider-thumb:hover {
  transform: scale(1.2);
}

.speedup-slider::-moz-range-thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--color-theme-primary);
  border: 2px solid var(--color-theme-accent);
  cursor: pointer;
  box-shadow: 0 0 8px var(--color-theme-glow);
  transition: transform 0.2s;
}

.speedup-slider::-moz-range-thumb:hover {
  transform: scale(1.2);
}

.divider {
  border-top: 1px solid var(--color-theme-border);
}

.stat-value {
  font-family: monospace;
  color: var(--color-theme-primary);
}

.mode-switch-button,
.recruit-button {
  background: var(--color-theme-primary);
  border: 2px solid var(--color-theme-primary);
  transition: all 0.2s;
}

.mode-switch-button:hover:not(:disabled),
.recruit-button:hover:not(:disabled) {
  background: var(--color-theme-accent);
  border-color: var(--color-theme-accent);
  box-shadow: 0 0 8px var(--color-theme-glow);
}

.mode-switch-button:disabled,
.recruit-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
