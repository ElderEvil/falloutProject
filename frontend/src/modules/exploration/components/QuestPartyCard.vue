<script setup lang="ts">
import { computed } from 'vue'
import PartyRoster from './PartyRoster.vue'
import { Icon } from '@iconify/vue'
import { Card } from '@/core/components/ui/card'
import { Badge } from '@/core/components/ui/badge'
import { Progress } from '@/core/components/ui/progress'
import { useNow } from '@/core/composables/useNow'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import {
  linearProgress,
  parseStartTimeMs,
} from '@/modules/exploration/composables/useExplorationProgress'
import { isQuestReturning } from '@/modules/progression/models/quest'
import type { VaultQuest } from '@/modules/progression/models/quest'

interface Props {
  quest: VaultQuest
  partyMembers: DwellerShort[]
  selected?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{ select: [] }>()

const now = useNow(1000)

const isReturning = computed(() => isQuestReturning(props.quest))

const progressPercentage = computed(() => {
  if (isReturning.value) {
    if (!props.quest.return_started_at || !props.quest.return_completes_at) return 100
    return linearProgress(
      parseStartTimeMs(props.quest.return_started_at),
      parseStartTimeMs(props.quest.return_completes_at),
      now.value
    )
  }
  if (!props.quest.started_at || !props.quest.duration_minutes) return 0

  const start = parseStartTimeMs(props.quest.started_at)
  return linearProgress(start, start + props.quest.duration_minutes * 60 * 1000, now.value)
})

const timeRemaining = computed(() => {
  if (isReturning.value) {
    if (!props.quest.return_completes_at) return 'Travelling home'
    const remainingMinutes = Math.max(
      0,
      Math.ceil((parseStartTimeMs(props.quest.return_completes_at) - now.value) / 60_000)
    )
    return `Travelling home — ${remainingMinutes}m left`
  }
  if (progressPercentage.value >= 100) return 'Rewards ready'

  const remainingMinutes = Math.ceil(
    (props.quest.duration_minutes ?? 0) * (1 - progressPercentage.value / 100)
  )
  const hours = Math.floor(remainingMinutes / 60)
  return hours > 0 ? `${hours}h ${remainingMinutes % 60}m left` : `${remainingMinutes}m left`
})
</script>

<template>
  <!-- @vue-ignore -->
  <Card
    class="quest-party-card gap-0 rounded-lg border-2 border-theme-primary/20 bg-surface-raised p-6 ring-0"
    :class="{ selected }"
    @click="emit('select')"
  >
    <div class="mission-header">
      <div class="mission-type">
        <Icon icon="mdi:sword-cross" class="mission-icon" />
        <span>Quest party</span>
      </div>
      <Badge variant="outline" class="border-theme-accent/50 bg-theme-accent/10 text-theme-accent">
        <Icon :icon="isReturning ? 'mdi:home-import-outline' : 'mdi:sword-cross'" class="h-3 w-3" />
        {{ isReturning ? 'RETURNING' : 'QUESTING' }}
      </Badge>
    </div>

    <h3 class="quest-title">{{ quest.title }}</h3>

    <div class="mission-progress">
      <div class="progress-labels">
        <span>{{ isReturning ? 'Return progress' : 'Mission progress' }}</span>
        <span>{{ Math.round(progressPercentage) }}%</span>
      </div>
      <Progress :model-value="progressPercentage" class="h-2" />
      <span class="mission-time">{{ timeRemaining }}</span>
    </div>

    <PartyRoster :members="partyMembers" />
  </Card>
</template>

<style scoped>
.quest-party-card {
  display: grid;
  gap: 14px;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.quest-party-card:hover,
.quest-party-card.selected {
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 16px var(--color-theme-glow);
}

.quest-party-card:hover {
  transform: translateY(-2px);
}

.mission-header,
.mission-type,
.progress-labels {
  display: flex;
  align-items: center;
}

.mission-header,
.progress-labels {
  justify-content: space-between;
  gap: 12px;
}

.mission-type {
  gap: 8px;
  color: var(--color-theme-primary);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.mission-icon {
  color: var(--color-theme-accent);
}

.mission-time {
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.7);
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
  white-space: nowrap;
}

.quest-title {
  color: var(--color-theme-primary);
  font-size: 1.1rem;
  font-weight: 700;
  line-height: 1.25;
}

.mission-progress {
  display: grid;
}

.mission-progress {
  gap: 6px;
}

.progress-labels {
  color: var(--color-theme-primary);
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  opacity: 0.8;
  text-transform: uppercase;
}
</style>
