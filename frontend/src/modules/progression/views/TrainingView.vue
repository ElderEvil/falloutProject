<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import { Progress } from '@/core/components/ui/progress'
import TrainingQueuePanel from '@/modules/progression/components/training/TrainingQueuePanel.vue'
import TrainingRoomCard from '@/modules/progression/components/training/TrainingRoomCard.vue'
import ApprenticeSection from '@/modules/progression/components/training/ApprenticeSection.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import VaultPageShell from '@/core/components/common/VaultPageShell.vue'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useTrainingStore } from '@/modules/progression/stores/training'
import PageHeader from '@/core/components/common/PageHeader.vue'
import PageHeaderMetric from '@/core/components/common/PageHeaderMetric.vue'
import { getTrainingRoomCapacity } from '@/modules/rooms/utils/room'

const route = useRoute()
const vaultStore = useVaultStore()
const authStore = useAuthStore()
const roomStore = useRoomStore()
const trainingStore = useTrainingStore()

const vaultId = route.params.id as string

const trainingRooms = computed(() => {
  return roomStore.rooms.filter((room) => room.category === 'training')
})

const activeTrainings = computed(() => trainingStore.allActiveTrainings)

const getRoomActiveCount = (roomId: string) => {
  return activeTrainings.value.filter((training) => training.room_id === roomId).length
}

const roomsInUse = computed(() => {
  const roomIds = new Set(activeTrainings.value.map((training) => training.room_id))
  return trainingRooms.value.filter((room) => roomIds.has(room.id)).length
})

const totalCapacity = computed(() => {
  return trainingRooms.value.reduce((sum, room) => sum + getTrainingRoomCapacity(room), 0)
})

const capacityPercent = computed(() => {
  if (totalCapacity.value <= 0) return 0
  return Math.min(100, Math.round((activeTrainings.value.length / totalCapacity.value) * 100))
})

onMounted(async () => {
  if (authStore.token && vaultId) {
    // Ensure vault is loaded - the shared action is idempotent, so this is
    // safe to call alongside the shell's own hydration on every route entry
    await vaultStore.ensureVaultLoaded(vaultId, authStore.token)
    await roomStore.fetchRooms(vaultId, authStore.token)
    await trainingStore.fetchVaultTrainings(vaultId, authStore.token)
  }
})
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-terminal-green">
    <VaultPageShell flicker>
      <PageContentRail class="flex flex-col gap-6">
        <PageHeader
          title="Training Center"
          icon="mdi:dumbbell"
          subtitle="Monitor and manage SPECIAL stat training across your vault"
        >
          <template #help>
            <section>
              <h2 class="mb-1 flex items-center gap-2 font-semibold text-theme-primary">
                <Icon icon="mdi:dumbbell" class="size-4 shrink-0" />
                Improve SPECIAL stats
              </h2>
              <p>
                Assign dwellers to dedicated training rooms to improve the matching stat, up to its
                maximum.
              </p>
              <ul class="mt-2 list-disc space-y-1 pl-5">
                <li>Strength — Weight Room</li>
                <li>Perception — Armory</li>
                <li>Endurance — Fitness Room</li>
                <li>Charisma — Lounge</li>
                <li>Intelligence — Classroom</li>
                <li>Agility — Athletics Room</li>
                <li>Luck — Game Room</li>
              </ul>
            </section>
            <section>
              <h2 class="mb-1 flex items-center gap-2 font-semibold text-theme-primary">
                <Icon icon="mdi:clock-outline" class="size-4 shrink-0" />
                Training Duration
              </h2>
              <p>
                Higher current stats take longer to train. Room upgrades and training-speed pets
                shorten the duration. Check the session estimate before starting.
              </p>
            </section>
            <section>
              <h2 class="mb-1 flex items-center gap-2 font-semibold text-theme-primary">
                <Icon icon="mdi:clipboard-list-outline" class="size-4 shrink-0" />
                Plan your training
              </h2>
              <p>
                Room capacity limits simultaneous trainees. Monitor progress in the queue, cancel
                when needed, and reassign dwellers after they finish training.
              </p>
            </section>
          </template>
          <template #actions>
            <PageHeaderMetric
              icon="mdi:account-multiple"
              :value="activeTrainings.length"
              label="Training"
            />
            <PageHeaderMetric
              icon="mdi:progress-clock"
              :value="`${roomsInUse} / ${trainingRooms.length}`"
              label="Rooms in use"
            />
          </template>
        </PageHeader>

        <section class="flex w-full flex-col gap-4">
          <div class="flex items-center gap-3">
            <Icon
              icon="mdi:office-building"
              class="text-2xl text-theme-primary [filter:drop-shadow(0_0_4px_var(--color-theme-glow))]"
            />
            <h3
              class="m-0 font-mono text-xl font-bold uppercase tracking-[0.05em] text-theme-primary"
            >
              Training Rooms
            </h3>
          </div>

          <div
            v-if="trainingRooms.length === 0"
            class="flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-theme-glow p-8 text-center"
          >
            <Icon icon="mdi:hammer-wrench" class="text-5xl text-theme-primary opacity-30" />
            <p class="m-0 font-mono text-sm text-theme-primary opacity-70">
              No training rooms built yet
            </p>
            <p class="m-0 font-mono text-xs text-theme-primary opacity-50">
              Build training rooms in the vault to train dwellers
            </p>
          </div>

          <div v-else class="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-3">
            <TrainingRoomCard
              v-for="room in trainingRooms"
              :key="room.id"
              :room="room"
              :active-count="getRoomActiveCount(room.id)"
            />
          </div>

          <div
            v-if="trainingRooms.length > 0"
            class="flex flex-col gap-1.5 rounded-md border border-theme-glow bg-black/30 px-4 py-3"
          >
            <div class="flex items-center justify-between">
              <span class="font-mono text-xs uppercase text-theme-primary opacity-70"
                >Overall Capacity</span
              >
              <span class="font-mono text-xs font-bold text-theme-primary"
                >{{ activeTrainings.length }} / {{ totalCapacity }}</span
              >
            </div>
            <Progress
              class="h-2"
              :fill="'linear-gradient(to right, var(--color-theme-primary), var(--color-theme-accent))'"
              :model-value="capacityPercent"
            />
          </div>
        </section>

        <ApprenticeSection />

        <div class="w-full">
          <TrainingQueuePanel />
        </div>
      </PageContentRail>
    </VaultPageShell>
  </div>
</template>
