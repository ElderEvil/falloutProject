<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Badge } from '@/core/components/ui/badge'
import { Progress } from '@/core/components/ui/progress'
import { useNow } from '@/core/composables/useNow'
import { formatDuration } from '@/core/utils/time'
import type { components } from '@/core/types/api.generated'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import { parseStartTimeMs } from '@/modules/exploration/composables/useExplorationProgress'
import { getAbilityConfig } from '@/modules/dwellers/models/dweller'

type TrainingRead = components['schemas']['TrainingRead']
type TrainingProgress = components['schemas']['TrainingProgress']

interface Props {
  training: TrainingRead | TrainingProgress
  dwellerName?: string
  dwellerImage?: string | null
  roomName?: string
  continuousTraining?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'cancel', trainingId: string): void
  (e: 'complete', trainingId: string): void
}>()

const now = useNow(1000)
const ability = computed(() => getAbilityConfig(props.training.stat_being_trained))
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

const fillGradient = computed(() => {
  if (isReadyToComplete.value) {
    return 'linear-gradient(to right, var(--color-theme-accent), var(--color-theme-primary), var(--color-theme-accent))'
  }
  return 'linear-gradient(to right, var(--color-theme-primary), var(--color-theme-accent), var(--color-theme-primary))'
})

const portraitStateClass = computed(() =>
  isReadyToComplete.value ? 'border-theme-accent shadow-[0_0_8px_var(--color-theme-accent)]' : ''
)

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
    class="training-progress-card rounded-lg border bg-transparent px-2.5 py-2 shadow-[0_0_10px_var(--color-theme-primary),inset_0_0_10px_rgb(0_0_0_/_0.5)] transition-colors duration-200"
    :class="{
      'border-theme-primary hover:shadow-[0_0_15px_var(--color-theme-primary),inset_0_0_10px_rgb(0_0_0_/_0.5)]':
        !isReadyToComplete && training.status === 'active',
      'completion-ready border-theme-accent': isReadyToComplete,
      'border-theme-glow opacity-60 hover:shadow-[0_0_15px_var(--color-theme-primary),inset_0_0_10px_rgb(0_0_0_/_0.5)]':
        training.status !== 'active',
    }"
  >
    <div class="mb-2 flex items-start gap-2">
      <DwellerPortrait
        :thumbnail-url="dwellerImage"
        :alt="dwellerName ?? 'Dweller'"
        :image-class="`size-10 shrink-0 rounded-md border border-theme-glow object-cover [image-rendering:pixelated] ${portraitStateClass}`"
        :fallback-class="`flex size-10 shrink-0 items-center justify-center rounded-md border border-theme-glow bg-surface-sunken text-theme-primary ${portraitStateClass}`"
      />
      <div class="flex min-w-0 flex-1 flex-col gap-1">
        <div class="flex min-w-0 items-center gap-2">
          <span class="min-w-0 flex-1 truncate font-mono text-sm font-bold text-theme-primary">{{
            dwellerName ?? 'Dweller'
          }}</span>
          <Badge v-if="isCompletingSoon" variant="secondary">Soon</Badge>
          <span
            v-if="continuousTraining && training.status === 'active'"
            class="shrink-0 whitespace-nowrap font-mono text-xs text-theme-accent"
            >Goal: 10</span
          >
        </div>
        <div
          class="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-xs text-theme-primary"
        >
          <span class="inline-flex items-center gap-1">
            <Icon :icon="ability?.icon ?? 'mdi:star'" class="completion-stat-icon shrink-0" />
            {{ ability?.label ?? training.stat_being_trained }} {{ training.current_stat_value }} →
            {{ training.target_stat_value }}
          </span>
          <span v-if="roomName" class="text-muted-foreground">{{ roomName }}</span>
        </div>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-2">
      <Progress
        class="h-1.5 min-w-16 flex-1"
        :fill="fillGradient"
        :model-value="progressPercentage"
      />
      <span
        class="completion-time whitespace-nowrap font-mono text-xs text-theme-primary"
        :class="{ 'text-theme-accent': isReadyToComplete }"
        >{{ timeRemaining }}</span
      >
      <div class="flex shrink-0 gap-1">
        <Button v-if="isReadyToComplete" size="xs" variant="default" @click="handleComplete">
          <Icon icon="mdi:check-circle" />
          Complete
        </Button>
        <Button
          v-if="training.status === 'active'"
          size="xs"
          variant="destructive"
          @click="handleCancel"
        >
          <Icon icon="mdi:close-circle" />
          Cancel
        </Button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.completion-ready {
  box-shadow:
    0 0 14px var(--color-theme-accent),
    inset 0 0 10px rgb(0 0 0 / 0.5);
}
</style>
