<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { Card } from '@/core/components/ui/card'
import { Badge } from '@/core/components/ui/badge'
import { Progress } from '@/core/components/ui/progress'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import DwellerIdentitySignal from '@/modules/dwellers/components/DwellerIdentitySignal.vue'
import DwellerAgeBadge from '@/modules/dwellers/components/DwellerAgeBadge.vue'
import DwellerGenderBadge from '@/modules/dwellers/components/DwellerGenderBadge.vue'
import DwellerRarityBadge from '@/modules/dwellers/components/DwellerRarityBadge.vue'
import { parseStartTimeMs } from '@/modules/exploration/composables/useExplorationProgress'
import type { VaultQuest } from '@/modules/progression/models/quest'

interface Props {
  quest: VaultQuest
  partyMembers: DwellerShort[]
  selected?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{ select: [] }>()

const now = ref(Date.now())
let timerInterval: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  timerInterval = setInterval(() => {
    now.value = Date.now()
  }, 1000)
})

onUnmounted(() => {
  if (timerInterval) clearInterval(timerInterval)
})

const isReturning = computed(
  () => props.quest.return_completes_at != null && !props.quest.is_reward_ready
)

const progressPercentage = computed(() => {
  if (isReturning.value) {
    if (!props.quest.return_started_at || !props.quest.return_completes_at) return 100
    const start = parseStartTimeMs(props.quest.return_started_at)
    const total = parseStartTimeMs(props.quest.return_completes_at) - start
    if (total <= 0) return 100
    return Math.min(100, Math.max(0, ((now.value - start) / total) * 100))
  }
  if (!props.quest.started_at || !props.quest.duration_minutes) return 0

  const start = parseStartTimeMs(props.quest.started_at)
  const duration = props.quest.duration_minutes * 60 * 1000
  return Math.min(100, Math.max(0, ((now.value - start) / duration) * 100))
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

const partyCountLabel = computed(() => `${props.partyMembers.length} / 3 assigned`)
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
        <Badge v-if="isReturning" variant="secondary">RETURNING</Badge>
      </div>
      <span class="mission-time">{{ timeRemaining }}</span>
    </div>

    <h3 class="quest-title">{{ quest.title }}</h3>

    <div v-if="!isReturning" class="mission-progress">
      <div class="progress-labels">
        <span>Mission progress</span>
        <span>{{ Math.round(progressPercentage) }}%</span>
      </div>
      <Progress :model-value="progressPercentage" class="h-2" />
    </div>
    <div v-else class="mission-returning">
      <Icon icon="mdi:home-import-outline" class="returning-icon" />
      <span>{{ timeRemaining }}</span>
    </div>

    <div class="party-section">
      <div class="party-header">
        <span>Team</span>
        <span>{{ partyCountLabel }}</span>
      </div>
      <div class="party-members">
        <div v-for="member in partyMembers" :key="member.id" class="party-member">
          <Icon icon="mdi:account" class="member-icon" />
          <div class="member-info">
            <span class="member-name">{{ member.first_name }} {{ member.last_name }}</span>
            <div class="member-badges">
              <DwellerAgeBadge :age-group="member.age_group" size="sm" />
              <DwellerGenderBadge :gender="member.gender" size="sm" />
              <DwellerRarityBadge :rarity="member.rarity" size="sm" />
              <DwellerIdentitySignal :visual-attributes="member.visual_attributes" compact />
            </div>
          </div>
          <span class="member-level">Lv.{{ member.level }}</span>
        </div>
      </div>
    </div>
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
.progress-labels,
.party-header,
.party-member {
  display: flex;
  align-items: center;
}

.mission-header,
.progress-labels,
.party-header {
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

.mission-icon,
.member-icon,
.mission-time,
.member-level {
  color: var(--color-theme-accent);
}

.mission-time {
  font-family: 'Courier New', monospace;
  font-size: 0.8rem;
  white-space: nowrap;
}

.quest-title {
  color: var(--color-theme-primary);
  font-size: 1.1rem;
  font-weight: 700;
  line-height: 1.25;
}

.mission-progress,
.party-section,
.party-members {
  display: grid;
}

.mission-returning {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--color-surface-sunken);
  border: 1px solid color-mix(in srgb, var(--color-theme-secondary) 40%, transparent);
  border-radius: 4px;
  color: var(--color-theme-secondary);
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.returning-icon {
  font-size: 1.1rem;
}

.mission-progress {
  gap: 6px;
}

.progress-labels,
.party-header {
  color: var(--color-theme-primary);
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  opacity: 0.8;
  text-transform: uppercase;
}

.party-section {
  gap: 8px;
  border-top: 1px solid color-mix(in srgb, var(--color-theme-primary) 20%, transparent);
  padding-top: 12px;
}

.party-members {
  gap: 5px;
}

.party-member {
  gap: 8px;
  color: var(--color-theme-primary);
  font-size: 0.85rem;
}

.member-info {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.member-badges {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem;
}

.member-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.member-level {
  font-size: 0.75rem;
  margin-left: auto;
}
</style>
