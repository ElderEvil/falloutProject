<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRadioStore } from '@/stores/radio'
import type { RadioMode } from '@/models/radio'
import UCard from '@/components/ui/UCard.vue'
import UButton from '@/components/ui/UButton.vue'
import UBadge from '@/components/ui/UBadge.vue'

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

async function updateSpeedup(value: number) {
  if (!stats.value?.speedup_multipliers?.length) return

  const roomId = stats.value.speedup_multipliers[selectedRoomIndex.value]?.room_id
  if (roomId) {
    await radioStore.setRadioSpeedup(props.vaultId, roomId, value)
  }
}

onMounted(() => {
  refreshStats()
})
</script>

<template>
  <UCard class="radio-stats-panel">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-xl font-mono text-green-400">📻 Radio Room</h2>
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
      <div class="bg-gray-800 border border-green-700 rounded-lg p-3">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm font-semibold text-green-400">Radio Mode</span>
          <UBadge :color="isRecruitmentMode ? 'blue' : 'purple'">
            {{ isRecruitmentMode ? 'Recruitment' : 'Happiness' }}
          </UBadge>
        </div>
        <p class="text-xs text-gray-400 mb-3">
          {{ isRecruitmentMode
            ? 'Attracts new dwellers to your vault'
            : 'Boosts happiness for all dwellers' }}
        </p>
        <UButton @click="toggleMode" size="sm" class="w-full">
          Switch to {{ isRecruitmentMode ? 'Happiness Mode' : 'Recruitment Mode' }}
        </UButton>
      </div>

      <!-- Speedup Controls -->
      <div class="bg-gray-800 border border-green-700 rounded-lg p-3">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm font-semibold text-green-400">Speedup Multiplier</span>
          <UBadge color="yellow">{{ currentSpeedup.toFixed(1) }}x</UBadge>
        </div>

        <!-- Room selector if multiple radio rooms -->
        <div v-if="stats.speedup_multipliers.length > 1" class="mb-3">
          <label class="text-xs text-gray-400 mb-1 block">Radio Room:</label>
          <select
            v-model="selectedRoomIndex"
            class="w-full bg-gray-900 border border-green-700 text-green-400 rounded px-2 py-1 text-sm"
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
            :value="currentSpeedup"
            @input="(e) => updateSpeedup(parseFloat((e.target as HTMLInputElement).value))"
            class="w-full accent-green-500"
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

      <div class="border-t border-green-800"></div>

      <!-- Stats (only show if in recruitment mode) -->
      <div v-if="isRecruitmentMode" class="space-y-2">
        <div class="flex justify-between items-center">
          <span class="text-gray-400">Radio Rooms:</span>
          <span class="font-mono text-green-400">{{ stats.radio_rooms_count }}</span>
        </div>

        <div class="flex justify-between items-center">
          <span class="text-gray-400">Recruitment Rate:</span>
          <span class="font-mono text-green-400">{{ formatRate }}</span>
        </div>

        <div class="flex justify-between items-center">
          <span class="text-gray-400">Avg. Time Per Recruit:</span>
          <span class="font-mono text-green-400">{{ estimatedTime }}</span>
        </div>
      </div>

      <div class="border-t border-green-800"></div>

      <!-- Manual recruitment -->
      <div class="space-y-2">
        <div class="flex justify-between items-center">
          <span class="text-gray-400">Manual Recruitment:</span>
          <UBadge color="yellow">
            {{ stats.manual_cost_caps }} caps
          </UBadge>
        </div>

        <UButton
          @click="$emit('manual-recruit')"
          :disabled="isRecruiting"
          variant="primary"
          class="w-full"
        >
          {{ isRecruiting ? 'Recruiting...' : 'Recruit Dweller Now' }}
        </UButton>
      </div>
    </div>
  </UCard>
</template>
