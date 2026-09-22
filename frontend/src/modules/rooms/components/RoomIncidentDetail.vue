<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import { getIncidentIcon, type Incident, type IncidentTeamMember } from '@/modules/combat/models/incident'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { getCombatPower } from '@/modules/dwellers/models/dweller'
import DwellerListRow from '@/modules/dwellers/components/DwellerListRow.vue'
import { Button } from '@/core/components/ui/button'
import { useToast } from '@/core/composables/useToast'
import IncidentScene from './IncidentScene.vue'
import IncidentBattleLog from './IncidentBattleLog.vue'

interface Props {
  incident: Incident
  vaultId: string
  dwellers: DwellerShort[]
  roomImageUrl?: string | null
}

const props = defineProps<Props>()

const authStore = useAuthStore()
const incidentStore = useIncidentStore()
const { warning: showWarning } = useToast()
const assigningDwellerId = ref<string | null>(null)
const isSendingBest = ref(false)
// One assignment at a time: both handlers post to the same endpoint, so a second
// in-flight request would race the first.
const isAssigning = computed(() => assigningDwellerId.value !== null || isSendingBest.value)

const threatName = computed(() => props.incident.type.replace(/_/g, ' ').toUpperCase())
const icon = computed(() => getIncidentIcon(props.incident.type))
const progress = computed(() => props.incident.progress)

const availableResponders = computed(() =>
  props.dwellers.filter(
    (dweller) =>
      dweller.is_adult &&
      dweller.health > 0 &&
      dweller.room_id !== props.incident.room_id &&
      !['exploring', 'questing', 'dead'].includes(dweller.status)
  )
)

const bestResponders = computed(() =>
  availableResponders.value
    .slice()
    .sort((a, b) => getCombatPower(b) - getCombatPower(a))
    .slice(0, 3)
)

interface TeamMemberEntry {
  member: IncidentTeamMember
  dweller: DwellerShort | undefined
}

const teamMembers = computed<TeamMemberEntry[]>(() =>
  incidentStore
    .getIncidentTeam(props.incident.id)
    .map((member) => ({
      member,
      dweller: props.dwellers.find((dweller) => dweller.id === member.dweller_id),
    }))
)

const teamMemberLabel = (entry: TeamMemberEntry): string =>
  entry.dweller?.first_name ?? entry.member.dweller_id.slice(0, 8)

const teamLoaded = ref(false)

const loadTeam = async (): Promise<void> => {
  teamLoaded.value = false
  if (!authStore.token) {
    teamLoaded.value = true
    return
  }
  const incidentId = props.incident.id
  await incidentStore.fetchIncidentTeam(props.vaultId, incidentId, authStore.token)
  if (props.incident.id === incidentId) {
    teamLoaded.value = true
  }
}

onMounted(loadTeam)
watch(() => props.incident.id, loadTeam)

// The POST appends (deduped) to the roster and rejects a roster over 6, so the
// UI sends only the newly chosen dwellers and never a doomed over-cap request.
const MAX_TEAM_SIZE = 6

const currentTeamIds = computed(() =>
  incidentStore.getIncidentTeam(props.incident.id).map((member) => member.dweller_id)
)

const fitWithinRosterCap = (newIds: string[]): string[] => {
  const freshIds = newIds.filter((id) => !currentTeamIds.value.includes(id))
  const fits = Math.max(MAX_TEAM_SIZE - currentTeamIds.value.length, 0)
  if (freshIds.length > fits) {
    showWarning(
      `Incident team is full (${MAX_TEAM_SIZE}) — ${freshIds.length - fits} responder(s) not sent.`
    )
    return freshIds.slice(0, fits)
  }
  return freshIds
}

const send = async (dwellerIds: string[]) => {
  if (!authStore.token || !dwellerIds.length) return
  await incidentStore.assignResponders(props.vaultId, props.incident.id, dwellerIds, authStore.token)
}

const sendBestDefenders = async () => {
  if (isAssigning.value || !teamLoaded.value || !bestResponders.value.length) return
  isSendingBest.value = true
  try {
    await send(fitWithinRosterCap(bestResponders.value.map((dweller) => dweller.id)))
  } finally {
    isSendingBest.value = false
  }
}

const assignResponder = async (dwellerId: string) => {
  if (isAssigning.value || !teamLoaded.value) return
  assigningDwellerId.value = dwellerId
  try {
    await send(fitWithinRosterCap([dwellerId]))
  } finally {
    assigningDwellerId.value = null
  }
}
</script>

<template>
  <section class="flex flex-col gap-3">
    <header class="flex items-center gap-3">
      <Icon :icon="icon" class="h-8 w-8 shrink-0 text-danger" />
      <div>
        <h3 class="text-base font-semibold text-terminal-green">{{ threatName }}</h3>
        <p class="text-xs text-terminal-green-dim">
          {{ incident.family.toUpperCase() }} · {{ incident.objective.toUpperCase() }} ·
          {{ progress.label.toUpperCase() }} {{ progress.current }} / {{ progress.target }}
        </p>
      </div>
    </header>

    <IncidentScene
      :incident="incident"
      :dwellers="dwellers"
      :room-image-url="roomImageUrl ?? null"
    />

    <IncidentBattleLog :events="incident.events" />

    <div>
      <h4 class="mb-2 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-terminal-green-dim">
        <Icon icon="mdi:account-group" class="h-4 w-4" />
        {{ incident.response.label }}
      </h4>

      <div v-if="teamMembers.length" class="mb-3">
        <h4 class="mb-2 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-terminal-green-dim">
          <Icon icon="mdi:shield-account" class="h-4 w-4" />
          On scene
        </h4>
        <ul class="flex flex-col gap-1.5">
          <li
            v-for="entry in teamMembers"
            :key="entry.member.id"
            class="flex items-center gap-2 rounded border border-theme-primary/20 bg-surface-canvas px-3 py-1.5 text-xs"
          >
            <Icon icon="mdi:account" class="h-4 w-4 shrink-0 text-terminal-green" />
            <span class="truncate text-terminal-green">{{ teamMemberLabel(entry) }}</span>
            <span class="ml-auto flex items-center gap-1 text-terminal-green-dim">
              <Icon icon="mdi:sword" class="h-3.5 w-3.5" />
              POW {{ entry.dweller ? getCombatPower(entry.dweller) : '—' }}
            </span>
          </li>
        </ul>
      </div>

      <div v-if="bestResponders.length" class="mb-3 flex flex-wrap items-center gap-2">
        <Button
          variant="default"
          size="sm"
          :disabled="isAssigning || !teamLoaded"
          @click="sendBestDefenders"
        >
          <Icon v-if="isSendingBest" icon="mdi:loading" class="mr-1 animate-spin" />
          Send best {{ bestResponders.length }}
        </Button>
        <span class="text-xs text-terminal-green-dim">
          {{ bestResponders.map((d) => d.first_name).join(', ') }}
        </span>
      </div>

      <ul v-if="availableResponders.length" class="flex flex-col gap-2">
        <DwellerListRow
          v-for="dweller in availableResponders"
          :key="dweller.id"
          :dweller="dweller"
          :clickable="false"
        >
          <template #middle>
            <div class="flex items-center gap-3 text-xs text-terminal-green-dim">
              <span class="flex items-center gap-1">
                <Icon icon="mdi:heart" class="h-3.5 w-3.5 text-danger" />
                {{ dweller.health }}/{{ dweller.max_health }}
              </span>
              <span class="flex items-center gap-1">
                <Icon icon="mdi:sword" class="h-3.5 w-3.5" />
                POW {{ getCombatPower(dweller) }}
              </span>
            </div>
          </template>
          <template #actions>
            <Button
              variant="secondary"
              size="sm"
              :disabled="isAssigning || !teamLoaded"
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
      <p v-else class="text-xs text-terminal-green-dim">
        All available adults are already defending or away.
      </p>
    </div>

    <p class="flex items-center gap-1.5 text-xs text-terminal-green-dim">
      <Icon icon="mdi:lock" class="h-4 w-4" />
      Room management is locked while this incident is live.
    </p>
  </section>
</template>
