<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import LearningProgressCard from './LearningProgressCard.vue'
import { useNow } from '@/core/composables/useNow'
import { formatDuration } from '@/core/utils/time'
import TerminalEmptyState from '@/core/components/common/TerminalEmptyState.vue'
import { useDwellerFilterStore } from '@/modules/dwellers/stores/dwellerFilter'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { parseStartTimeMs } from '@/modules/exploration/composables/useExplorationProgress'

const dwellerStore = useDwellerFilterStore()
const roomStore = useRoomStore()

const now = useNow(1000)

// Mirrors backend TrainingService.calculate_training_duration (seconds).
const TRAINING_BASE_SECONDS = 7200
const TRAINING_PER_LEVEL_SECONDS = 1800
const TIER_MULTIPLIERS: Record<number, number> = { 1: 1.0, 2: 0.75, 3: 0.6 }

const apprentices = computed(() =>
  dwellerStore.dwellers.filter((dweller) => !!dweller.apprentice_stat)
)

const roomLookup = computed(() => {
  const lookup = new Map<string, { name: string; tier: number }>()
  for (const room of roomStore.rooms) {
    lookup.set(room.id, { name: room.name, tier: room.tier })
  }
  return lookup
})

interface ApprenticeProgress {
  id: string
  name: string
  thumbnailUrl: string | null
  roomName: string
  statKey: string
  currentStat: number
  progressPercent: number
  timeRemaining: string
  ready: boolean
}

const apprenticeCards = computed<ApprenticeProgress[]>(() => {
  return apprentices.value.map((dweller) => {
    const statKey = (dweller.apprentice_stat ?? '').toLowerCase()
    const room = dweller.room_id ? roomLookup.value.get(dweller.room_id) : undefined
    const currentStat = (dweller[statKey as keyof typeof dweller] as number) ?? 1

    const tierMultiplier = TIER_MULTIPLIERS[room?.tier ?? 1] ?? 1.0
    const durationSeconds =
      (TRAINING_BASE_SECONDS + currentStat * TRAINING_PER_LEVEL_SECONDS) * tierMultiplier

    const startedAt = dweller.apprentice_started_at
      ? parseStartTimeMs(dweller.apprentice_started_at)
      : null
    const elapsed = startedAt ? now.value - startedAt : 0
    const progressPercent = startedAt
      ? Math.min(100, Math.max(0, (elapsed / (durationSeconds * 1000)) * 100))
      : 0

    const remainingMs = durationSeconds * 1000 - elapsed
    const timeRemaining =
      remainingMs <= 0
        ? 'Ready'
        : formatDuration(Math.ceil(remainingMs / 60_000) * 60, {
            omitZeroHours: true,
            suffix: 'left',
          })

    return {
      id: dweller.id,
      name: `${dweller.first_name} ${dweller.last_name ?? ''}`.trim(),
      thumbnailUrl: dweller.thumbnail_url ?? null,
      roomName: room?.name ?? 'Production Room',
      statKey,
      currentStat,
      progressPercent,
      timeRemaining,
      ready: remainingMs <= 0,
    }
  })
})
</script>

<template>
  <section class="flex w-full flex-col gap-4">
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div class="flex items-center gap-3">
        <Icon
          icon="mdi:school"
          class="text-2xl text-theme-primary [filter:drop-shadow(0_0_4px_var(--color-theme-glow))]"
        />
        <h3 class="m-0 font-mono text-xl font-bold uppercase tracking-[0.05em] text-theme-primary">
          Apprentices ({{ apprenticeCards.length }})
        </h3>
      </div>
      <span
        class="flex items-center gap-1.5 rounded border border-theme-glow bg-black/30 px-2.5 py-1 font-mono text-xs text-theme-primary"
      >
        <Icon icon="mdi:school" class="text-sm" />
        learning on the job
      </span>
    </div>

    <TerminalEmptyState
      v-if="apprenticeCards.length === 0"
      compact
      icon="mdi:school-outline"
      title="No active apprentices"
      description="Assign youth dwellers to production rooms as apprentices to learn SPECIAL stats."
    />

    <div v-else class="flex flex-wrap gap-3">
      <LearningProgressCard
        v-for="apprentice in apprenticeCards"
        :key="apprentice.id"
        class="w-80 max-w-full min-w-0"
        kind="apprentice"
        :name="apprentice.name"
        :image="apprentice.thumbnailUrl"
        :room-name="apprentice.roomName"
        :stat="apprentice.statKey"
        :current-stat="apprentice.currentStat"
        :target-stat="Math.min(apprentice.currentStat + 1, 10)"
        :progress="apprentice.progressPercent"
        :time-remaining="apprentice.timeRemaining"
        :ready="apprentice.ready"
      />
    </div>
  </section>
</template>
