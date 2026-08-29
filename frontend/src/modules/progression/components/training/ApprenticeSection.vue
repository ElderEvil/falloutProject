<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import UProgressBar from '@/core/components/ui/UProgressBar.vue'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import TerminalEmptyState from '@/core/components/common/TerminalEmptyState.vue'
import { useDwellerFilterStore } from '@/modules/dwellers/stores/dwellerFilter'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { getAbilityConfig } from '@/modules/dwellers/models/dweller'

const dwellerStore = useDwellerFilterStore()
const roomStore = useRoomStore()

const now = ref(Date.now())
let intervalId: number | null = null

onMounted(() => {
  intervalId = window.setInterval(() => {
    now.value = Date.now()
  }, 1000)
})

onUnmounted(() => {
  if (intervalId) clearInterval(intervalId)
})

// Mirrors backend TrainingService.calculate_training_duration (seconds).
const TRAINING_BASE_SECONDS = 7200
const TRAINING_PER_LEVEL_SECONDS = 1800
const TIER_MULTIPLIERS: Record<number, number> = { 1: 1.0, 2: 0.75, 3: 0.6 }

const apprentices = computed(() =>
  dwellerStore.dwellers.filter((dweller) => dweller.apprentice_stat !== null)
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
  statLabel: string
  statIcon: string
  currentStat: number
  progressPercent: number
  timeRemaining: string
}

const apprenticeCards = computed<ApprenticeProgress[]>(() => {
  return apprentices.value.map((dweller) => {
    const statKey = (dweller.apprentice_stat ?? '').toLowerCase()
    const ability = getAbilityConfig(statKey)
    const room = dweller.room_id ? roomLookup.value.get(dweller.room_id) : undefined
    const currentStat = (dweller[statKey as keyof typeof dweller] as number) ?? 1

    const tierMultiplier = TIER_MULTIPLIERS[room?.tier ?? 1] ?? 1.0
    const durationSeconds =
      (TRAINING_BASE_SECONDS + currentStat * TRAINING_PER_LEVEL_SECONDS) * tierMultiplier

    const startedAt = dweller.apprentice_started_at
      ? new Date(dweller.apprentice_started_at).getTime()
      : null
    const elapsed = startedAt ? now.value - startedAt : 0
    const progressPercent = startedAt
      ? Math.min(100, Math.max(0, (elapsed / (durationSeconds * 1000)) * 100))
      : 0

    const remainingMs = durationSeconds * 1000 - elapsed
    const hours = Math.floor(remainingMs / (1000 * 60 * 60))
    const minutes = Math.floor((remainingMs % (1000 * 60 * 60)) / (1000 * 60))
    const timeRemaining =
      remainingMs <= 0 ? 'Ready!' : hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`

    return {
      id: dweller.id,
      name: `${dweller.first_name} ${dweller.last_name ?? ''}`.trim(),
      thumbnailUrl: dweller.thumbnail_url ?? null,
      roomName: room?.name ?? 'Production Room',
      statKey,
      statLabel: ability?.label ?? statKey,
      statIcon: ability?.icon ?? 'mdi:star',
      currentStat,
      progressPercent,
      timeRemaining,
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
        <h3
          class="m-0 font-mono text-xl font-bold uppercase tracking-[0.05em] text-theme-primary"
        >
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

    <div v-else class="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
      <div
        v-for="apprentice in apprenticeCards"
        :key="apprentice.id"
        class="flex flex-col gap-3 rounded-lg border-2 border-theme-primary/30 bg-black/30 p-4 transition-colors hover:border-theme-primary/50"
      >
        <div class="flex items-center gap-3">
          <DwellerPortrait
            :thumbnail-url="apprentice.thumbnailUrl"
            :alt="apprentice.name"
          />
          <div class="min-w-0 flex-1">
            <p class="m-0 truncate font-mono text-sm font-bold text-theme-primary">
              {{ apprentice.name }}
            </p>
            <p class="m-0 truncate font-mono text-xs text-theme-primary/60">
              {{ apprentice.roomName }}
            </p>
          </div>
          <span
            class="flex shrink-0 items-center gap-1.5 rounded border border-theme-primary/40 bg-theme-secondary/40 px-2 py-1 font-mono text-xs font-bold text-theme-primary"
          >
            <Icon :icon="apprentice.statIcon" class="text-sm" />
            {{ apprentice.statLabel }} {{ apprentice.currentStat }}→{{ apprentice.currentStat + 1 }}
          </span>
        </div>

        <div class="flex flex-col gap-1.5">
          <div class="flex items-center justify-between font-mono text-xs text-theme-primary/70">
            <span>Progress</span>
            <span class="font-bold text-theme-primary">{{ apprentice.timeRemaining }}</span>
          </div>
          <UProgressBar
            :model-value="apprentice.progressPercent"
            :height="6"
            color="linear-gradient(to right, var(--color-theme-primary), var(--color-theme-accent))"
            :glow="false"
          />
        </div>
      </div>
    </div>
  </section>
</template>
