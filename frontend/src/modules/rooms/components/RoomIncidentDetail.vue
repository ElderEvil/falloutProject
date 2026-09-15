<script setup lang="ts">
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import { getIncidentIcon, type Incident } from '@/modules/combat/models/incident'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { getCombatPower } from '@/modules/dwellers/models/dweller'
import DwellerListRow from '@/modules/dwellers/components/DwellerListRow.vue'
import UButton from '@/core/components/ui/UButton.vue'
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

const send = async (dwellerIds: string[]) => {
  if (!authStore.token || !dwellerIds.length) return
  await incidentStore.assignResponders(props.vaultId, props.incident.id, dwellerIds, authStore.token)
}

const sendBestDefenders = async () => {
  if (isAssigning.value || !bestResponders.value.length) return
  isSendingBest.value = true
  try {
    await send(bestResponders.value.map((dweller) => dweller.id))
  } finally {
    isSendingBest.value = false
  }
}

const assignResponder = async (dwellerId: string) => {
  if (isAssigning.value) return
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

      <div v-if="bestResponders.length" class="mb-3 flex flex-wrap items-center gap-2">
        <UButton
          variant="primary"
          size="sm"
          :disabled="isAssigning"
          :loading="isSendingBest"
          @click="sendBestDefenders"
        >
          Send best {{ bestResponders.length }}
        </UButton>
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
            <UButton
              variant="secondary"
              size="sm"
              :disabled="isAssigning"
              :loading="assigningDwellerId === dweller.id"
              @click="assignResponder(dweller.id)"
            >
              Send
            </UButton>
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
