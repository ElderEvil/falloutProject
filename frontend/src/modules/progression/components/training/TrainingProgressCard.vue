<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import UButton from '@/core/components/ui/UButton.vue'
import UBadge from '@/core/components/ui/UBadge.vue'
import UProgressBar from '@/core/components/ui/UProgressBar.vue'
import type { components } from '@/core/types/api.generated'
import { normalizeImageUrl } from '@/core/utils/image'

type TrainingRead = components['schemas']['TrainingRead']
type TrainingProgress = components['schemas']['TrainingProgress']

interface Props {
  training: TrainingRead | TrainingProgress
  dwellerName?: string
  dwellerImage?: string | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'cancel', trainingId: string): void
  (e: 'complete', trainingId: string): void
}>()

const now = ref(Date.now())
let intervalId: number | null = null

onMounted(() => {
  // Update time every second
  intervalId = window.setInterval(() => {
    now.value = Date.now()
  }, 1000)
})

onUnmounted(() => {
  if (intervalId) {
    clearInterval(intervalId)
  }
})

const progressPercentage = computed(() => {
  // Prefer the backend's persisted progress when present (it's 0.0-1.0),
  // but recompute live from timestamps so the bar fills even when the
  // game-loop worker hasn't persisted an update yet.
  const started = new Date(props.training.started_at).getTime()
  const end = new Date(props.training.estimated_completion_at).getTime()
  const total = end - started
  if (total > 0 && props.training.status === 'active') {
    const elapsed = Math.min(Math.max(now.value - started, 0), total)
    const livePercent = (elapsed / total) * 100
    return Math.min(100, Math.max(props.training.progress * 100, livePercent))
  }
  return Math.min(100, props.training.progress * 100)
})

const timeRemaining = computed(() => {
  if (props.training.status !== 'active') {
    return props.training.status === 'completed' ? 'Completed' : 'Cancelled'
  }

  const completionTime = new Date(props.training.estimated_completion_at).getTime()
  const remaining = completionTime - now.value

  if (remaining <= 0) {
    return 'Ready to complete!'
  }

  const hours = Math.floor(remaining / (1000 * 60 * 60))
  const minutes = Math.floor((remaining % (1000 * 60 * 60)) / (1000 * 60))
  const seconds = Math.floor((remaining % (1000 * 60)) / 1000)

  if (hours > 0) {
    return `${hours}h ${minutes}m`
  } else if (minutes > 0) {
    return `${minutes}m ${seconds}s`
  } else {
    return `${seconds}s`
  }
})

const isReadyToComplete = computed(() => {
  if (props.training.status !== 'active') return false
  const completionTime = new Date(props.training.estimated_completion_at).getTime()
  return completionTime <= now.value
})

const fillGradient = computed(() => {
  if (isReadyToComplete.value) {
    return 'linear-gradient(to right, var(--color-theme-accent), var(--color-theme-primary), var(--color-theme-accent))'
  }
  return 'linear-gradient(to right, var(--color-theme-primary), var(--color-theme-accent), var(--color-theme-primary))'
})

const getStatIcon = (stat: string): string => {
  const iconMap: Record<string, string> = {
    strength: 'mdi:arm-flex',
    perception: 'mdi:eye',
    endurance: 'mdi:heart',
    charisma: 'mdi:account-voice',
    intelligence: 'mdi:brain',
    agility: 'mdi:run-fast',
    luck: 'mdi:clover',
  }
  return iconMap[stat.toLowerCase()] || 'mdi:star'
}

const handleCancel = () => {
  if (props.training.id) {
    emit('cancel', props.training.id)
  }
}

const handleComplete = () => {
  if (props.training.id) {
    emit('complete', props.training.id)
  }
}
</script>

<template>
  <div
    class="training-card"
    :class="{ ready: isReadyToComplete, inactive: training.status !== 'active' }"
  >
    <div class="training-header">
      <div class="training-visual">
        <img
          v-if="dwellerImage"
          :src="normalizeImageUrl(dwellerImage)"
          :alt="dwellerName ?? 'Dweller'"
          class="dweller-avatar"
        />
        <Icon v-else icon="mdi:account" class="dweller-placeholder" />
        <Icon :icon="getStatIcon(training.stat_being_trained)" class="stat-icon" />
      </div>
      <div class="header-content">
        <span v-if="dwellerName" class="dweller-name">{{ dwellerName }}</span>
        <span class="stat-name">Training {{ training.stat_being_trained.toUpperCase() }}</span>
      </div>
      <UBadge
        :variant="
          training.status === 'active'
            ? 'info'
            : training.status === 'completed'
              ? 'success'
              : 'default'
        "
      >
        {{ training.current_stat_value }} → {{ training.target_stat_value }}
      </UBadge>
    </div>

    <div class="training-progress-row">
      <div class="training-progress">
        <UProgressBar
          :model-value="progressPercentage"
          :height="12"
          :color="fillGradient"
          :glow="false"
        />
        <span class="progress-text">{{ progressPercentage.toFixed(0) }}%</span>
      </div>
      <div class="time-info">
        <Icon icon="mdi:clock-outline" class="time-icon" />
        <span class="time-remaining" :class="{ 'ready-text': isReadyToComplete }">
          {{ timeRemaining }}
        </span>
      </div>
      <div class="actions">
        <UButton v-if="isReadyToComplete" size="xs" variant="primary" @click="handleComplete">
          <Icon icon="mdi:check-circle" class="h-3.5 w-3.5" />
          Complete
        </UButton>
        <UButton
          v-if="training.status === 'active'"
          size="xs"
          variant="danger"
          @click="handleCancel"
        >
          <Icon icon="mdi:close-circle" class="h-3.5 w-3.5" />
          Cancel
        </UButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.training-card {
  background: transparent;
  border: 1px solid var(--color-theme-primary);
  border-radius: 0.5rem;
  padding: 0.625rem 0.75rem;
  box-shadow:
    0 0 10px var(--color-theme-primary),
    inset 0 0 10px rgb(0 0 0 / 0.5);
  transition: all 0.3s ease;
}

.training-card:hover {
  border-color: var(--color-theme-primary);
  box-shadow:
    0 0 15px var(--color-theme-primary),
    inset 0 0 10px rgb(0 0 0 / 0.5);
}

.training-card.ready {
  border-color: var(--color-theme-accent);
  box-shadow:
    0 0 15px var(--color-theme-accent),
    inset 0 0 10px rgb(0 0 0 / 0.5);
  animation: pulse 2s ease-in-out infinite;
}

.training-card.inactive {
  opacity: 0.6;
  border-color: var(--color-theme-glow);
}

.training-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.training-visual {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  flex-shrink: 0;
}

.stat-icon {
  font-size: 1.5rem;
  color: var(--color-theme-primary);
}

.dweller-avatar {
  flex-shrink: 0;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 0.375rem;
  border: 1px solid var(--color-theme-glow);
  object-fit: cover;
  image-rendering: pixelated;
}

.dweller-placeholder {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 0.375rem;
  border: 1px solid var(--color-theme-glow);
  color: var(--color-theme-primary);
  background: rgb(0 0 0 / 0.3);
}

.dweller-placeholder svg {
  width: 1.75rem;
  height: 1.75rem;
}

.training-card.ready .dweller-placeholder {
  border-color: var(--color-theme-accent);
  box-shadow: 0 0 8px var(--color-theme-accent);
}

.training-card.ready .dweller-avatar {
  border-color: var(--color-theme-accent);
  box-shadow: 0 0 8px var(--color-theme-accent);
}

.training-card.ready .stat-icon {
  color: var(--color-theme-accent);
  animation: bounce 1s ease-in-out infinite;
}

.header-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.stat-name {
  font-size: 0.875rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.dweller-name {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
}

.training-progress-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.training-progress {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.progress-text {
  flex-shrink: 0;
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
  min-width: 2.5rem;
  text-align: right;
}

.time-info {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  flex-shrink: 0;
}

.time-icon {
  font-size: 0.875rem;
  color: var(--color-theme-primary);
}

.time-remaining {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
  font-weight: bold;
  white-space: nowrap;
}

.time-remaining.ready-text {
  color: var(--color-theme-accent);
  text-shadow: 0 0 4px var(--color-theme-accent);
  animation: pulse-text 1s ease-in-out infinite;
}

.actions {
  display: flex;
  gap: 0.375rem;
  flex-shrink: 0;
}

@keyframes pulse {
  0%,
  100% {
    box-shadow:
      0 0 15px var(--color-theme-accent),
      inset 0 0 10px rgb(0 0 0 / 0.5);
  }
  50% {
    box-shadow:
      0 0 25px var(--color-theme-accent),
      inset 0 0 10px rgb(0 0 0 / 0.5);
  }
}

@keyframes bounce {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-5px);
  }
}

@keyframes pulse-text {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}
</style>
