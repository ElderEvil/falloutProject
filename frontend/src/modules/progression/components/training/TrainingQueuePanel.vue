<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { Icon } from '@iconify/vue'
import TerminalEmptyState from '@/core/components/common/TerminalEmptyState.vue'
import { useTrainingStore } from '@/modules/progression/stores/training'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useDwellerFilterStore } from '@/modules/dwellers/stores/dwellerFilter'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { usePolling } from '@/core/composables/usePolling'
import TrainingProgressCard from './TrainingProgressCard.vue'
import { ABILITY_CONFIG, getAbilityConfig } from '@/modules/dwellers/models/dweller'
import { Button } from '@/core/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/core/components/ui/tooltip'

const trainingStore = useTrainingStore()
const authStore = useAuthStore()
const vaultStore = useVaultStore()
const dwellerStore = useDwellerFilterStore()
const roomStore = useRoomStore()

const activeTrainings = computed(() =>
  [...trainingStore.allActiveTrainings].sort(
    (a, b) => Date.parse(a.estimated_completion_at) - Date.parse(b.estimated_completion_at)
  )
)
const roomGroups = computed(() => {
  const groups = new Map<string, typeof activeTrainings.value>()
  for (const training of activeTrainings.value) {
    if (!training.room_id) continue
    const group = groups.get(training.room_id) ?? []
    group.push(training)
    groups.set(training.room_id, group)
  }
  return [...groups].map(([roomId, trainings]) => ({ roomId, trainings }))
})
const typeGroups = computed(() => {
  const groups = new Map<string, typeof roomGroups.value>()
  for (const room of roomGroups.value) {
    const stat = room.trainings[0]!.stat_being_trained.toLowerCase()
    const rooms = groups.get(stat) ?? []
    rooms.push(room)
    groups.set(stat, rooms)
  }
  const order = Object.keys(ABILITY_CONFIG)
  return [...groups]
    .sort(([a], [b]) => order.indexOf(a) - order.indexOf(b))
    .map(([stat, rooms]) => ({
      stat,
      ability: getAbilityConfig(stat),
      rooms,
      count: rooms.reduce((sum, room) => sum + room.trainings.length, 0),
    }))
})
const continuousTraining = computed(() => !!vaultStore.activeVault?.continuous_training)

const toggleContinuousTraining = async () => {
  const vaultId = vaultStore.activeVault?.id
  const token = authStore.token
  if (!vaultId || !token) return
  await trainingStore.setContinuousTraining(vaultId, !continuousTraining.value, token)
}

const dwellerLookup = computed(() => {
  const lookup = new Map<string, { name: string; image: string | null }>()
  for (const dweller of dwellerStore.dwellers) {
    lookup.set(dweller.id, {
      name: `${dweller.first_name} ${dweller.last_name ?? ''}`.trim(),
      image: dweller.thumbnail_url ?? null,
    })
  }
  return lookup
})

const roomLookup = computed(() => {
  const lookup = new Map<string, string>()
  for (const room of roomStore.rooms) {
    lookup.set(room.id, room.name)
  }
  return lookup
})

const getDweller = (dwellerId: string) => dwellerLookup.value.get(dwellerId)

const getRoomName = (roomId: string) => roomLookup.value.get(roomId) ?? 'Training Room'

const fetchTrainings = async () => {
  if (!vaultStore.activeVault?.id || !authStore.token) return

  await Promise.all([
    trainingStore.fetchVaultTrainings(vaultStore.activeVault.id, authStore.token),
    dwellerStore.fetchDwellersByVault(vaultStore.activeVault.id, authStore.token),
    roomStore.fetchRooms(vaultStore.activeVault.id, authStore.token),
  ])
}

// Refresh trainings every 30 seconds while this panel is mounted.
usePolling(fetchTrainings, { interval: 30_000, immediate: false })

const handleCancelTraining = async (trainingId: string) => {
  if (!authStore.token) return

  await trainingStore.cancelTraining(trainingId, authStore.token)
  await fetchTrainings()
}

const handleCompleteTraining = async (trainingId: string) => {
  if (!authStore.token) return

  await trainingStore.completeTraining(trainingId, authStore.token)
  await fetchTrainings()
}

const handleGoal = async (trainingId: string, goal: number) => {
  if (!authStore.token) return
  await trainingStore.setTrainingGoal(trainingId, goal, authStore.token)
  await fetchTrainings()
}

onMounted(() => {
  // Fetch when vault becomes available (handles page reload where vault loads async)
  watch(
    () => vaultStore.activeVault?.id,
    (newId) => {
      if (newId && authStore.token) {
        fetchTrainings()
      }
    },
    { immediate: true }
  )
})
</script>

<template>
  <div class="training-queue-panel flex h-full flex-col gap-4 bg-transparent">
    <div class="training-queue-header flex flex-wrap items-center justify-between gap-4">
      <div class="flex items-center gap-3">
        <Icon
          icon="mdi:dumbbell"
          class="text-2xl text-theme-primary [filter:drop-shadow(0_0_4px_var(--color-theme-glow))]"
        />
        <h3 class="m-0 font-mono text-xl font-bold uppercase tracking-[0.05em] text-theme-primary">
          Training Queue
        </h3>
      </div>
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger as-child>
            <Button
              :variant="continuousTraining ? 'default' : 'outline'"
              size="sm"
              aria-label="Repeat training"
              :aria-pressed="continuousTraining"
              :disabled="
                !vaultStore.activeVault ||
                !authStore.token ||
                trainingStore.isSettingContinuousTraining
              "
              @click="toggleContinuousTraining"
            >
              <Icon :icon="continuousTraining ? 'mdi:repeat' : 'mdi:repeat-off'" />
              Repeat training
            </Button>
          </TooltipTrigger>
          <TooltipContent>{{
            continuousTraining
              ? 'Repeat to individual goals. Click to stop after this round.'
              : 'Repeat training rounds to each dweller’s goal.'
          }}</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>

    <div class="training-queue-content flex-1">
      <!-- Empty State -->
      <TerminalEmptyState
        v-if="activeTrainings.length === 0"
        compact
        icon="mdi:sleep"
        title="No dwellers currently training"
        description="Open a training room above to assign dwellers."
      />

      <div v-else class="flex flex-col gap-5">
        <details
          v-for="type in typeGroups"
          :key="type.stat"
          open
          class="group rounded-lg border-2 border-theme-primary p-4 shadow-[0_0_10px_var(--color-theme-glow)]"
        >
          <summary
            class="flex cursor-pointer list-none items-center gap-2 rounded py-2 font-mono text-sm font-bold text-theme-primary focus-visible:outline-2 focus-visible:outline-theme-primary [&::-webkit-details-marker]:hidden"
          >
            <Icon
              icon="mdi:chevron-right"
              class="size-4 transition-transform group-open:rotate-90"
            />
            <Icon :icon="type.ability?.icon ?? 'mdi:dumbbell'" class="size-4" />
            {{ type.ability?.label ?? type.stat }}
            <span class="text-xs font-normal text-muted-foreground"
              >{{ type.count }} training · {{ type.rooms.length }}
              {{ type.rooms.length === 1 ? 'room' : 'rooms' }}</span
            >
          </summary>
          <div class="flex flex-col gap-4 pt-2">
            <section
              v-for="group in type.rooms"
              :key="group.roomId"
              :id="`training-room-${group.roomId}`"
              :aria-label="getRoomName(group.roomId)"
              class="flex flex-col gap-2"
            >
              <h5 class="flex items-center gap-2 font-mono text-sm font-bold text-theme-primary">
                <Icon icon="mdi:dumbbell" class="size-4" />
                {{ getRoomName(group.roomId) }}
                <span class="text-xs font-normal text-muted-foreground">{{
                  group.trainings.length
                }}</span>
              </h5>
              <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <TrainingProgressCard
                  class="min-w-0"
                  v-for="training in group.trainings"
                  :key="training.id"
                  :training="training"
                  :dweller-name="getDweller(training.dweller_id)?.name"
                  :dweller-image="getDweller(training.dweller_id)?.image"
                  :is-saving-goal="trainingStore.savingGoals.has(training.id)"
                  @goal="handleGoal"
                  @cancel="handleCancelTraining"
                  @complete="handleCompleteTraining"
                />
              </div>
            </section>
          </div>
        </details>
      </div>
    </div>
  </div>
</template>
