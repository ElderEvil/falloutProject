<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import { getIncidentIcon, type Incident } from '@/modules/combat/models/incident'
import type { Room } from '../models/room'
import { UNITS_PER_ROOM } from '../models/grid'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import {
  getCombatPower,
  getDwellerDisplayName,
  getStatusConfig,
  isMature,
} from '@/modules/dwellers/models/dweller'
import DwellerListRow from '@/modules/dwellers/components/DwellerListRow.vue'
import { Button } from '@/core/components/ui/button'
import { threatName } from '@/core/utils/format'
import IncidentScene from './IncidentScene.vue'
import IncidentBattleLog from './IncidentBattleLog.vue'

interface Props {
  incident: Incident
  vaultId: string
  dwellers: DwellerShort[]
  roomImageUrl?: string | null
  fallbackImageUrl?: string | null
  rooms?: Room[]
  finishing?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{ playbackComplete: [incidentId: string] }>()

const authStore = useAuthStore()
const incidentStore = useIncidentStore()
const assigningDwellerId = ref<string | null>(null)
const isSendingBest = ref(false)
// One assignment at a time: both handlers post to the same endpoint, so a second
// in-flight request would race the first.
const isAssigning = computed(
  () => props.finishing || assigningDwellerId.value !== null || isSendingBest.value
)

const threatLabel = computed(() => threatName(props.incident.type))
const icon = computed(() => getIncidentIcon(props.incident.type))

// Six arriving helpers are allowed in addition to the room residents.
const MAX_TEAM_SIZE = 6
const currentTeamIds = computed(() =>
  incidentStore.getIncidentTeam(props.incident.id).map((member) => member.dweller_id)
)
const remainingRosterSlots = computed(() =>
  Math.max(MAX_TEAM_SIZE - currentTeamIds.value.length, 0)
)
const otherActiveIncidents = computed(() =>
  incidentStore.activeIncidents.filter(
    (incident) => incident.id !== props.incident.id && incident.vault_id === props.vaultId
  )
)
const responderTeamsLoaded = computed(
  () =>
    teamLoaded.value &&
    otherActiveIncidents.value.every((incident) => incidentStore.hasLoadedIncidentTeam(incident.id))
)
const unavailableResponderIds = computed(
  () =>
    new Set([
      ...currentTeamIds.value,
      ...otherActiveIncidents.value.flatMap((incident) =>
        incidentStore
          .getIncidentTeam(incident.id)
          .filter((member) => ['assigned', 'dispatched'].includes(member.status))
          .map((member) => member.dweller_id)
      ),
    ])
)

const availableResponders = computed(() => {
  if (!responderTeamsLoaded.value) return []
  return props.dwellers
    .filter(
      (dweller) =>
        isMature(dweller) &&
        dweller.health > 0 &&
        !unavailableResponderIds.value.has(dweller.id) &&
        dweller.room_id !== props.incident.room_id &&
        !['exploring', 'questing', 'dead', 'fighting'].includes(dweller.status) &&
        !otherActiveIncidents.value.some((incident) => incident.room_id === dweller.room_id)
    )
    .sort((a, b) => {
      const nearA = distanceFromIncident(a),
        nearB = distanceFromIncident(b)
      if (nearA !== nearB) return nearA - nearB
      return Number(b.status === 'idle') - Number(a.status === 'idle') || comparePower(a, b)
    })
})

const roomsById = computed(() => new Map((props.rooms ?? []).map((room) => [room.id, room])))
const comparePower = (a: DwellerShort, b: DwellerShort) =>
  (b.combat_power ?? getCombatPower(b)) - (a.combat_power ?? getCombatPower(a)) ||
  getDwellerDisplayName(a).localeCompare(getDwellerDisplayName(b)) ||
  a.id.localeCompare(b.id)

// Estimate proximity from the vault grid; this is selection priority, not an ETA.
const distanceFromIncident = (dweller: DwellerShort): number => {
  const source = dweller.room_id ? roomsById.value.get(dweller.room_id) : undefined
  const target = roomsById.value.get(props.incident.room_id)
  if (
    source?.coordinate_x == null ||
    source.coordinate_y == null ||
    target?.coordinate_x == null ||
    target.coordinate_y == null
  )
    return Infinity
  const sourceCenter = source.coordinate_x + (source.size ?? source.size_min) / 2
  const targetCenter = target.coordinate_x + (target.size ?? target.size_min) / 2
  return (
    Math.abs(sourceCenter - targetCenter) / UNITS_PER_ROOM +
    Math.abs(source.coordinate_y - target.coordinate_y)
  )
}
const posting = (dweller: DwellerShort) =>
  dweller.room_id ? (roomsById.value.get(dweller.room_id)?.name ?? 'Assigned room') : 'Unassigned'
const proximity = (dweller: DwellerShort) => {
  const source = dweller.room_id ? roomsById.value.get(dweller.room_id) : undefined
  const target = roomsById.value.get(props.incident.room_id)
  if (!Number.isFinite(distanceFromIncident(dweller))) return null
  const floors = Math.abs(source!.coordinate_y! - target!.coordinate_y!)
  return floors === 0 ? 'Same floor' : `${floors} floor${floors === 1 ? '' : 's'} away`
}
const helperBatchSize = computed(() => Math.min(3, remainingRosterSlots.value))
const bestResponders = computed(() =>
  [...availableResponders.value].sort(comparePower).slice(0, helperBatchSize.value)
)
const nearbyResponders = computed(() =>
  availableResponders.value
    .filter((dweller) => Number.isFinite(distanceFromIncident(dweller)))
    .slice(0, helperBatchSize.value)
)
// Rounds run on the vault tick, so the journal starts empty by design; the
// overlay explains whether the next tick will fight or whether help is needed.
const roomResidentCount = computed(
  () =>
    props.dwellers.filter(
      (dweller) =>
        dweller.room_id === props.incident.room_id &&
        isMature(dweller) &&
        dweller.health > 0 &&
        dweller.status !== 'dead'
    ).length
)
const awaitingLabel = computed(() => {
  const fought = props.incident.events.some((event) =>
    ['turn', 'round', 'containment'].includes(event.kind)
  )
  if (fought) return null
  return roomResidentCount.value > 0 || currentTeamIds.value.length > 0
    ? 'First round runs on the next vault tick.'
    : 'No responders in the room — send help to start the fight.'
})

const teamFetchSettled = ref(false)
const teamLoaded = computed(
  () => teamFetchSettled.value && incidentStore.hasLoadedIncidentTeam(props.incident.id)
)

const loadTeam = async (): Promise<void> => {
  teamFetchSettled.value = false
  if (!authStore.token) {
    teamFetchSettled.value = true
    return
  }
  const incidentId = props.incident.id
  await incidentStore.fetchIncidentTeam(props.vaultId, incidentId, authStore.token)
  if (props.incident.id === incidentId) {
    teamFetchSettled.value = true
  }
}

onMounted(loadTeam)
watch(() => props.incident.id, loadTeam)

const send = async (dwellerIds: string[]) => {
  if (!authStore.token || !dwellerIds.length) return
  await incidentStore.assignResponders(
    props.vaultId,
    props.incident.id,
    dwellerIds,
    authStore.token
  )
}

const sendGroup = async (candidates: DwellerShort[]) => {
  if (isAssigning.value || !responderTeamsLoaded.value || !candidates.length) return
  isSendingBest.value = true
  try {
    await send(candidates.map((dweller) => dweller.id))
  } finally {
    isSendingBest.value = false
  }
}
const sendBestDefenders = () => sendGroup(bestResponders.value)
const sendNearbyDefenders = () => sendGroup(nearbyResponders.value)

const assignResponder = async (dwellerId: string) => {
  if (isAssigning.value || !responderTeamsLoaded.value || !remainingRosterSlots.value) return
  assigningDwellerId.value = dwellerId
  try {
    await send([dwellerId])
  } finally {
    assigningDwellerId.value = null
  }
}
</script>

<template>
  <section class="flex flex-col gap-3">
    <header class="flex items-center gap-2">
      <Icon :icon="icon" class="h-6 w-6 shrink-0 text-danger" />
      <h3 class="text-base font-semibold text-terminal-green">{{ threatLabel }}</h3>
    </header>

    <IncidentScene
      :incident="incident"
      :dwellers="dwellers"
      :room-image-url="roomImageUrl ?? null"
      :fallback-image-url="fallbackImageUrl ?? null"
      :team="teamLoaded ? incidentStore.getIncidentTeam(incident.id) : undefined"
      @playback-complete="emit('playbackComplete', $event)"
    />

    <IncidentBattleLog :events="incident.events" />
    <p v-if="awaitingLabel" class="text-xs text-terminal-green-dim">{{ awaitingLabel }}</p>

    <div v-if="bestResponders.length" class="flex flex-wrap items-center gap-2">
      <Button
        v-if="nearbyResponders.length"
        variant="default"
        size="sm"
        :disabled="isAssigning || !responderTeamsLoaded"
        @click="sendNearbyDefenders"
      >
        Send nearby {{ nearbyResponders.length }}
      </Button>
      <Button
        variant="outline"
        size="sm"
        :disabled="isAssigning || !responderTeamsLoaded"
        @click="sendBestDefenders"
      >
        <Icon v-if="isSendingBest" icon="mdi:loading" class="mr-1 animate-spin" />
        Send strongest {{ bestResponders.length }}
      </Button>
      <span class="text-xs text-muted-foreground"
        >{{ remainingRosterSlots }} helper slots available</span
      >
    </div>

    <details v-if="availableResponders.length" class="border-t border-border pt-2">
      <summary class="cursor-pointer text-xs text-muted-foreground">
        Add helper · {{ availableResponders.length }} available
      </summary>
      <ul class="mt-2 flex flex-col gap-2">
        <DwellerListRow
          v-for="dweller in availableResponders"
          :key="dweller.id"
          :dweller="dweller"
          :clickable="false"
          class="flex-wrap gap-2 [&_.dweller-identity]:w-auto [&_.dweller-identity]:flex-1"
        >
          <template #middle>
            <div
              class="order-last flex w-full flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground"
            >
              <span class="flex items-center gap-1" :class="getStatusConfig(dweller.status).color">
                <Icon :icon="getStatusConfig(dweller.status).icon" class="size-3.5" />
                {{ getStatusConfig(dweller.status).label }}
              </span>
              <span>{{ posting(dweller) }}</span>
              <span v-if="proximity(dweller)">{{ proximity(dweller) }}</span>
              <span class="flex items-center gap-1">
                <Icon icon="mdi:heart" class="h-3.5 w-3.5 text-danger" />
                {{ dweller.health }}/{{ dweller.max_health }}
              </span>
              <span class="flex items-center gap-1">
                <Icon icon="mdi:sword" class="h-3.5 w-3.5" />
                POW {{ getCombatPower(dweller) }}
              </span>
              <span class="tabular-nums">· Lv {{ dweller.level }}</span>
            </div>
          </template>
          <template #actions>
            <Button
              variant="secondary"
              size="sm"
              :disabled="isAssigning || !responderTeamsLoaded || !remainingRosterSlots"
              @click="assignResponder(dweller.id)"
            >
              <Icon
                v-if="assigningDwellerId === dweller.id"
                icon="mdi:loading"
                class="mr-1 animate-spin"
              />
              Send
            </Button>
          </template>
        </DwellerListRow>
      </ul>
    </details>
    <p v-else-if="!responderTeamsLoaded" role="status" class="text-xs text-terminal-green-dim">
      Waiting for incident teams to load before choosing responders.
    </p>
    <p v-else class="text-xs text-terminal-green-dim">
      All available adults are already defending or away.
    </p>
  </section>
</template>
