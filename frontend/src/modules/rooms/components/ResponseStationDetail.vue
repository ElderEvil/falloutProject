<script setup lang="ts">
import { computed, onUnmounted, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { Badge } from '@/core/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/core/components/ui/card'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { HAZARD_TEAM_SIZE } from '@/modules/contamination-team/models/contaminationTeam'
import type { HazardTeam } from '@/modules/contamination-team/models/contaminationTeam'
import ResponseTeamsPanel from '@/modules/contamination-team/components/ResponseTeamsPanel.vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import type { Room } from '../models/room'
import { useResponseStationStore } from '../stores/responseStation'

const props = defineProps<{
  room: Room
  vaultId: string
  assignedDwellers: DwellerShort[]
  dwellerCapacity: number
}>()

const emit = defineEmits<{
  viewDweller: [dwellerId: string]
}>()

const authStore = useAuthStore()
const stationStore = useResponseStationStore()

const token = computed(() => (typeof authStore.token === 'string' ? authStore.token : ''))
const currentSize = computed(() => props.room.size ?? props.room.size_min)

const activeTotal = computed(
  () => stationStore.roster?.teams.reduce((sum, team) => sum + team.active.length, 0) ?? 0
)
const reserveTotal = computed(
  () => stationStore.roster?.teams.reduce((sum, team) => sum + team.reserve.length, 0) ?? 0
)

function loadRoster(): void {
  void stationStore.loadRoster(props.vaultId, token.value)
}

watch(
  [() => props.room.id, () => props.vaultId, token],
  () => {
    stationStore.reset()
    if (props.vaultId && token.value) loadRoster()
  },
  { immediate: true }
)

onUnmounted(() => stationStore.reset())

function handleSetPlace(team: HazardTeam, dwellerId: string, active: boolean): void {
  void stationStore.setPlace(props.vaultId, team, dwellerId, active, token.value)
}
</script>

<template>
  <section class="response-station flex flex-col gap-4" aria-label="Response Station management">
    <Card class="border border-theme-primary/30">
      <CardHeader class="gap-2">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <CardTitle class="flex items-center gap-2 text-base text-theme-primary">
            <Icon icon="mdi:shield-account" class="h-4 w-4" :ariaHidden="true" />
            Station Management
          </CardTitle>
          <Badge variant="outline" class="border-theme-primary/40 text-theme-primary/80">
            {{ assignedDwellers.length }} / {{ dwellerCapacity }} stationed
          </Badge>
        </div>
        <p class="text-xs leading-relaxed text-theme-primary/65">
          Dwellers earn a place by fighting three matching incidents, and teams only form while the
          station stands. Active members answer matching hazards automatically; reserves wait for a
          free place.
        </p>
      </CardHeader>

      <CardContent class="flex flex-col gap-4">
        <dl class="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div
            class="flex flex-col gap-0.5 rounded border border-theme-primary/20 bg-terminal-background px-3 py-2"
          >
            <dt class="text-[0.65rem] tracking-wider text-theme-primary/60 uppercase">Stationed</dt>
            <dd class="text-lg font-bold text-theme-primary">
              {{ assignedDwellers.length }} / {{ dwellerCapacity }}
            </dd>
          </div>
          <div
            class="flex flex-col gap-0.5 rounded border border-theme-primary/20 bg-terminal-background px-3 py-2"
          >
            <dt class="text-[0.65rem] tracking-wider text-theme-primary/60 uppercase">Footprint</dt>
            <dd class="text-lg font-bold text-theme-primary">
              {{ currentSize }} / {{ room.size_max }} cells
            </dd>
          </div>
          <div
            class="flex flex-col gap-0.5 rounded border border-theme-primary/20 bg-terminal-background px-3 py-2"
          >
            <dt class="text-[0.65rem] tracking-wider text-theme-primary/60 uppercase">
              Active crew
            </dt>
            <dd class="text-lg font-bold text-theme-primary">
              {{ activeTotal }} / {{ HAZARD_TEAM_SIZE * 2 }}
            </dd>
          </div>
          <div
            class="flex flex-col gap-0.5 rounded border border-theme-primary/20 bg-terminal-background px-3 py-2"
          >
            <dt class="text-[0.65rem] tracking-wider text-theme-primary/60 uppercase">Reserve</dt>
            <dd class="text-lg font-bold text-theme-primary">{{ reserveTotal }}</dd>
          </div>
        </dl>
      </CardContent>
    </Card>

    <ResponseTeamsPanel
      :roster="stationStore.roster"
      :loading="stationStore.isLoading"
      :error="stationStore.error"
      :busy-dweller-ids="stationStore.busyDwellerIds"
      @set-place="handleSetPlace"
      @refresh="loadRoster"
      @view-dweller="emit('viewDweller', $event)"
    />
  </section>
</template>
