<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/core/components/ui/tooltip'
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
import { ABILITY_CONFIG, getAbilityConfig } from '@/modules/dwellers/models/dweller'
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

const roomsByStat = computed(() => {
  const groups = new Map<string, typeof trainingRooms.value>()
  for (const room of trainingRooms.value) {
    const stat = room.ability?.toLowerCase() ?? 'other'
    const rooms = groups.get(stat) ?? []
    rooms.push(room)
    groups.set(stat, rooms)
  }
  const order = [...Object.keys(ABILITY_CONFIG), 'other']
  return [...groups]
    .sort(([a], [b]) => order.indexOf(a) - order.indexOf(b))
    .map(([stat, rooms]) => ({ stat, ability: getAbilityConfig(stat), rooms }))
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
              <p>Adult dwellers gain one SPECIAL point per round.</p>
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
                Open a room to assign dwellers. Set their goals, then enable Repeat training.
                Turning repeat off lets the current round finish.
              </p>
            </section>
          </template>
          <template #actions>
            <PageHeaderMetric
              icon="mdi:account-multiple"
              :value="activeTrainings.length"
              label="Training"
              tooltip="Dwellers currently in training sessions"
            />
            <PageHeaderMetric
              icon="mdi:progress-clock"
              :value="`${roomsInUse} / ${trainingRooms.length}`"
              label="Rooms in use"
              tooltip="Training rooms with active sessions out of the total"
            />
          </template>
        </PageHeader>

        <section class="flex w-full flex-col gap-4">
          <div class="flex flex-wrap items-center justify-between gap-4">
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
              v-if="trainingRooms.length > 0"
              class="ml-auto flex items-center gap-3 font-mono text-xs text-theme-primary"
              role="group"
              aria-label="Overall training capacity"
            >
              <span class="uppercase opacity-70">Overall Capacity</span>
              <span class="font-bold tabular-nums"
                >{{ activeTrainings.length }} / {{ totalCapacity }}</span
              >
            </div>
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

          <div
            v-else
            class="grid min-w-0 grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-7"
            role="region"
            aria-label="Training rooms by SPECIAL stat"
          >
            <section
              v-for="group in roomsByStat"
              :key="group.stat"
              :aria-label="`${group.ability?.label ?? 'Other'} training rooms`"
              class="flex min-w-0 flex-col gap-2"
            >
              <h4
                class="flex min-w-0 items-center gap-1.5 font-mono text-xs font-bold text-theme-primary"
              >
                <Icon :icon="group.ability?.icon ?? 'mdi:star'" class="size-4 shrink-0" />
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <span
                        tabindex="0"
                        class="truncate rounded-sm focus-visible:outline-2 focus-visible:outline-theme-primary"
                        >{{ group.ability?.label ?? 'Other' }}</span
                      >
                    </TooltipTrigger>
                    <TooltipContent>{{ group.ability?.label ?? 'Other' }}</TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </h4>
              <div class="flex flex-col gap-3">
                <TrainingRoomCard
                  v-for="room in group.rooms"
                  :key="room.id"
                  class="min-w-0"
                  :room="room"
                  :vault-id="vaultId"
                  :active-count="getRoomActiveCount(room.id)"
                />
              </div>
            </section>
          </div>
        </section>

        <div class="w-full">
          <TrainingQueuePanel />
        </div>

        <ApprenticeSection />
      </PageContentRail>
    </VaultPageShell>
  </div>
</template>
