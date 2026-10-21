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
    const group = groups.get(training.room_id) ?? []
    group.push(training)
    groups.set(training.room_id, group)
  }
  return [...groups].map(([roomId, trainings]) => ({ roomId, trainings }))
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

    <div
      class="training-queue-content flex flex-1 flex-col gap-6 overflow-y-auto rounded-lg border-2 border-theme-primary p-4 shadow-[0_0_10px_var(--color-theme-glow)]"
    >
      <!-- Empty State -->
      <TerminalEmptyState
        v-if="activeTrainings.length === 0"
        compact
        icon="mdi:sleep"
        title="No dwellers currently training"
        description="Assign dwellers to training rooms to improve their SPECIAL stats."
      />

      <div v-else class="flex flex-col gap-5">
        <section
          v-for="group in roomGroups"
          :key="group.roomId"
          :id="`training-room-${group.roomId}`"
          :aria-label="getRoomName(group.roomId)"
          class="flex flex-col gap-2"
        >
          <h4 class="flex items-center gap-2 font-mono text-sm font-bold text-theme-primary">
            <Icon icon="mdi:dumbbell" class="size-4" />
            {{ getRoomName(group.roomId) }}
            <span class="text-xs font-normal text-muted-foreground">{{
              group.trainings.length
            }}</span>
          </h4>
          <div class="flex flex-wrap gap-3">
            <TrainingProgressCard
              class="w-80 max-w-full min-w-0"
              v-for="training in group.trainings"
              :key="training.id"
              :training="training"
              :dweller-name="getDweller(training.dweller_id)?.name"
              :dweller-image="getDweller(training.dweller_id)?.image"
              :continuous-training="continuousTraining"
              :is-saving-goal="trainingStore.savingGoals.has(training.id)"
              @goal="handleGoal"
              @cancel="handleCancelTraining"
              @complete="handleCompleteTraining"
            />
          </div>
        </section>
      </div>
    </div>
  </div>
</template>
