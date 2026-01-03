<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import UButton from '@/components/ui/UButton.vue'
import UBadge from '@/components/ui/UBadge.vue'
import type { components } from '@/types/api.generated'

type TrainingRead = components['schemas']['TrainingRead']
type TrainingProgress = components['schemas']['TrainingProgress']

interface Props {
  training: TrainingRead | TrainingProgress
  dwellerName?: string
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

const getStatIcon = (stat: string): string => {
  const iconMap: Record<string, string> = {
    strength: 'mdi:arm-flex',
    perception: 'mdi:eye',
    endurance: 'mdi:heart',
    charisma: 'mdi:account-voice',
    intelligence: 'mdi:brain',
    agility: 'mdi:run-fast',
    luck: 'mdi:clover'
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
  <div class="training-card" :class="{ 'ready': isReadyToComplete, 'inactive': training.status !== 'active' }">
    <div class="training-header">
      <Icon :icon="getStatIcon(training.stat_being_trained)" class="stat-icon" />
      <div class="header-content">
        <span class="stat-name">Training {{ training.stat_being_trained.toUpperCase() }}</span>
        <span v-if="dwellerName" class="dweller-name">{{ dwellerName }}</span>
      </div>
      <UBadge :variant="training.status === 'active' ? 'info' : training.status === 'completed' ? 'success' : 'default'">
        {{ training.current_stat_value }} → {{ training.target_stat_value }}
      </UBadge>
    </div>

    <div class="training-progress">
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: `${progressPercentage}%` }">
          <div class="progress-shine"></div>
        </div>
      </div>
      <span class="progress-text">{{ progressPercentage.toFixed(1) }}%</span>
    </div>

    <div class="training-footer">
      <div class="time-info">
        <Icon icon="mdi:clock-outline" class="time-icon" />
        <span class="time-remaining" :class="{ 'ready-text': isReadyToComplete }">
          {{ timeRemaining }}
        </span>
      </div>
      <div class="actions">
        <UButton
          v-if="isReadyToComplete"
          size="sm"
          variant="primary"
          @click="handleComplete"
        >
          <Icon icon="mdi:check-circle" class="h-4 w-4" />
          Complete
        </UButton>
        <UButton
          v-if="training.status === 'active'"
          size="sm"
          variant="danger"
          @click="handleCancel"
        >
          <Icon icon="mdi:close-circle" class="h-4 w-4" />
          Cancel
        </UButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.training-card {
  background: linear-gradient(135deg, rgb(0 0 0 / 0.7), rgb(15 23 42 / 0.7));
  border: 1px solid var(--color-theme-primary);
  border-radius: 0.5rem;
  padding: 1rem;
  box-shadow: 0 0 10px var(--color-theme-primary), inset 0 0 10px rgb(0 0 0 / 0.5);
  transition: all 0.3s ease;
}

.training-card:hover {
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 15px var(--color-theme-primary), inset 0 0 10px rgb(0 0 0 / 0.5);
}

.training-card.ready {
  border-color: var(--color-theme-accent);
  box-shadow: 0 0 15px var(--color-theme-accent), inset 0 0 10px rgb(0 0 0 / 0.5);
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
  margin-bottom: 0.75rem;
}

.stat-icon {
  font-size: 2rem;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 4px var(--color-theme-primary));
}

.training-card.ready .stat-icon {
  color: var(--color-theme-accent);
  filter: drop-shadow(0 0 4px var(--color-theme-accent));
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

.training-progress {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.progress-bar {
  flex: 1;
  height: 1rem;
  background: linear-gradient(to bottom, rgb(0 0 0 / 0.8), rgb(0 0 0 / 0.6));
  border: 1px solid var(--color-theme-primary);
  border-radius: 0.25rem;
  overflow: hidden;
  position: relative;
  box-shadow: inset 0 1px 3px rgb(0 0 0 / 0.5);
}

.training-card.ready .progress-bar {
  border-color: var(--color-theme-accent);
}

.progress-fill {
  height: 100%;
  background: linear-gradient(
    to right,
    var(--color-theme-primary),
    rgb(0 149 255),
    var(--color-theme-primary)
  );
  transition: width 0.5s ease-out;
  position: relative;
  box-shadow: 0 0 8px var(--color-theme-primary);
}

.training-card.ready .progress-fill {
  background: linear-gradient(
    to right,
    var(--color-theme-accent),
    var(--color-theme-primary),
    var(--color-theme-accent)
  );
  box-shadow: 0 0 8px var(--color-theme-accent);
}

.progress-shine {
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.3) 50%,
    transparent 100%
  );
  animation: shine 3s ease-in-out infinite;
}

.progress-text {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
  min-width: 3rem;
  text-align: right;
}

.training-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}

.time-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.time-icon {
  font-size: 1rem;
  color: var(--color-theme-primary);
}

.time-remaining {
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
  font-weight: bold;
}

.time-remaining.ready-text {
  color: var(--color-theme-accent);
  text-shadow: 0 0 4px var(--color-theme-accent);
  animation: pulse-text 1s ease-in-out infinite;
}

.actions {
  display: flex;
  gap: 0.5rem;
}

@keyframes shine {
  0% {
    left: -100%;
  }
  50%,
  100% {
    left: 200%;
  }
}

@keyframes pulse {
  0%,
  100% {
    box-shadow: 0 0 15px var(--color-theme-accent), inset 0 0 10px rgb(0 0 0 / 0.5);
  }
  50% {
    box-shadow: 0 0 25px var(--color-theme-accent), inset 0 0 10px rgb(0 0 0 / 0.5);
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
