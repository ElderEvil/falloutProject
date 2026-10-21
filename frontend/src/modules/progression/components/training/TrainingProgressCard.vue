<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import LearningProgressCard from './LearningProgressCard.vue'
import { useNow } from '@/core/composables/useNow'
import { formatDuration } from '@/core/utils/time'
import type { components } from '@/core/types/api.generated'
import { parseStartTimeMs } from '@/modules/exploration/composables/useExplorationProgress'

type TrainingRead = components['schemas']['TrainingRead']
type TrainingProgress = components['schemas']['TrainingProgress']

interface Props {
  training: TrainingRead | TrainingProgress
  dwellerName?: string
  dwellerImage?: string | null
  continuousTraining?: boolean
  isSavingGoal?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'cancel', trainingId: string): void
  (e: 'complete', trainingId: string): void
  (e: 'goal', trainingId: string, value: number): void
}>()

const goal = computed(() => props.training.goal_stat_value ?? 10)
const changeGoal = (delta: number) => {
  const value = goal.value + delta
  if (!props.isSavingGoal && value >= props.training.target_stat_value && value <= 10) {
    emit('goal', props.training.id, value)
  }
}
const now = useNow(1000)
const isCompletingSoon = computed(() => {
  const remaining = Date.parse(props.training.estimated_completion_at) - now.value
  return props.training.status === 'active' && remaining > 0 && remaining <= 10 * 60_000
})

const progressPercentage = computed(() => {
  // Prefer the backend's persisted progress when present (it's 0.0-1.0),
  // but recompute live from timestamps so the bar fills even when the
  // game-loop worker hasn't persisted an update yet.
  const started = parseStartTimeMs(props.training.started_at)
  const end = parseStartTimeMs(props.training.estimated_completion_at)
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
    return 'Ready'
  }

  return formatDuration(Math.ceil(remaining / 60_000) * 60, { omitZeroHours: true, suffix: 'left' })
})

const isReadyToComplete = computed(() => {
  if (props.training.status !== 'active') return false
  const completionTime = new Date(props.training.estimated_completion_at).getTime()
  return completionTime <= now.value
})

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
  <LearningProgressCard
    class="training-progress-card"
    :name="dwellerName"
    :image="dwellerImage"
    :stat="training.stat_being_trained"
    :current-stat="training.current_stat_value"
    :target-stat="training.target_stat_value"
    :progress="progressPercentage"
    :time-remaining="timeRemaining"
    :ready="isReadyToComplete"
    :soon="isCompletingSoon"
    :inactive="training.status !== 'active'"
  >
    <template v-if="training.status === 'active'" #goal>
      <div
        role="group"
        :aria-label="`Training goal for ${dwellerName ?? 'Dweller'}`"
        class="flex items-center gap-1 text-theme-accent"
      >
        <span class="mr-1">Goal:</span>
        <Button
          size="icon-sm"
          class="size-7"
          variant="outline"
          :aria-label="`Decrease goal for ${dwellerName ?? 'Dweller'}`"
          :disabled="isSavingGoal || goal <= training.target_stat_value"
          @click="changeGoal(-1)"
        >
          <Icon icon="mdi:minus" />
        </Button>
        <output class="min-w-5 text-center tabular-nums" aria-live="polite">{{ goal }}</output>
        <Button
          size="icon-sm"
          class="size-7"
          variant="outline"
          :aria-label="`Increase goal for ${dwellerName ?? 'Dweller'}`"
          :disabled="isSavingGoal || goal >= 10"
          @click="changeGoal(1)"
        >
          <Icon icon="mdi:plus" />
        </Button>
      </div>
    </template>
    <template v-if="training.status === 'active'" #actions>
      <Button v-if="isReadyToComplete" size="xs" variant="default" @click="handleComplete">
        <Icon icon="mdi:check-circle" />
        Complete
      </Button>
      <Button size="xs" variant="destructive" @click="handleCancel">
        <Icon icon="mdi:close-circle" />
        Cancel
      </Button>
    </template>
  </LearningProgressCard>
</template>
