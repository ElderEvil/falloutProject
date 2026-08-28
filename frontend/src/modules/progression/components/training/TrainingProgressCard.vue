<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import UButton from '@/core/components/ui/UButton.vue'
import UBadge from '@/core/components/ui/UBadge.vue'
import UProgressBar from '@/core/components/ui/UProgressBar.vue'
import type { components } from '@/core/types/api.generated'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import { parseUtcDate } from '@/core/utils/date'

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
  const started = parseUtcDate(props.training.started_at).getTime()
  const end = parseUtcDate(props.training.estimated_completion_at).getTime()
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

  const completionTime = parseUtcDate(props.training.estimated_completion_at).getTime()
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
  const completionTime = parseUtcDate(props.training.estimated_completion_at).getTime()
  return completionTime <= now.value
})

const fillGradient = computed(() => {
  if (isReadyToComplete.value) {
    return 'linear-gradient(to right, var(--color-theme-accent), var(--color-theme-primary), var(--color-theme-accent))'
  }
  return 'linear-gradient(to right, var(--color-theme-primary), var(--color-theme-accent), var(--color-theme-primary))'
})

const portraitStateClass = computed(() =>
  isReadyToComplete.value
    ? 'border-theme-accent shadow-[0_0_8px_var(--color-theme-accent)]'
    : ''
)

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
    class="rounded-lg border bg-transparent px-3 py-2.5 shadow-[0_0_10px_var(--color-theme-primary),inset_0_0_10px_rgb(0_0_0_/_0.5)] transition-all duration-300"
    :class="{
      'border-theme-primary hover:shadow-[0_0_15px_var(--color-theme-primary),inset_0_0_10px_rgb(0_0_0_/_0.5)]':
        !isReadyToComplete && training.status === 'active',
      'border-theme-accent shadow-[0_0_15px_var(--color-theme-accent),inset_0_0_10px_rgb(0_0_0_/_0.5)] animate-[pulse_2s_ease-in-out_infinite]':
        isReadyToComplete,
      'border-theme-glow opacity-60 hover:shadow-[0_0_15px_var(--color-theme-primary),inset_0_0_10px_rgb(0_0_0_/_0.5)]':
        training.status !== 'active',
    }"
  >
    <div class="mb-2 flex items-center gap-3">
      <div class="flex shrink-0 items-center gap-1.5">
        <DwellerPortrait
          :image-url="dwellerImage"
          :alt="dwellerName ?? 'Dweller'"
          :image-class="`h-10 w-10 shrink-0 rounded-md border border-theme-glow object-cover [image-rendering:pixelated] ${portraitStateClass}`"
          :fallback-class="`flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-theme-glow bg-surface-sunken text-theme-primary ${portraitStateClass}`"
        />
        <Icon
          :icon="getStatIcon(training.stat_being_trained)"
          class="text-2xl text-theme-primary"
          :class="{
            'text-theme-accent animate-[bounce_1s_ease-in-out_infinite]': isReadyToComplete,
          }"
        />
      </div>
      <div class="flex flex-1 flex-col gap-1">
        <span v-if="dwellerName" class="font-mono text-xs text-theme-primary">{{
          dwellerName
        }}</span>
        <span class="font-mono text-sm font-bold uppercase tracking-[0.05em] text-theme-primary"
          >Training {{ training.stat_being_trained.toUpperCase() }}</span
        >
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

    <div class="flex items-center gap-3">
      <div class="flex min-w-0 flex-1 items-center gap-2">
        <UProgressBar
          :model-value="progressPercentage"
          :height="12"
          :color="fillGradient"
          :glow="false"
        />
        <span class="w-10 shrink-0 text-right font-mono text-xs text-theme-primary"
          >{{ progressPercentage.toFixed(0) }}%</span
        >
      </div>
      <div class="flex shrink-0 items-center gap-1.5">
        <Icon icon="mdi:clock-outline" class="text-sm text-theme-primary" />
        <span
          class="whitespace-nowrap font-mono text-xs font-bold text-theme-primary"
          :class="{
            'text-theme-accent [text-shadow:0_0_4px_var(--color-theme-accent)] animate-[pulse-text_1s_ease-in-out_infinite]':
              isReadyToComplete,
          }"
        >
          {{ timeRemaining }}
        </span>
      </div>
      <div class="flex shrink-0 gap-1.5">
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
