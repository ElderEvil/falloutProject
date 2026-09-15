<script setup lang="ts">
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import { getIncidentIcon, type Incident } from '@/modules/combat/models/incident'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { getCombatPower } from '@/modules/dwellers/models/dweller'
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
  if (isSendingBest.value || !bestResponders.value.length) return
  isSendingBest.value = true
  try {
    await send(bestResponders.value.map((dweller) => dweller.id))
  } finally {
    isSendingBest.value = false
  }
}

const assignResponder = async (dwellerId: string) => {
  if (assigningDwellerId.value) return
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
      <div v-if="bestResponders.length" class="flex flex-wrap items-center gap-2">
        <UButton variant="primary" size="sm" :loading="isSendingBest" @click="sendBestDefenders">
          {{ incident.response.label.toUpperCase() }}: {{ bestResponders.length }} BEST
        </UButton>
        <span class="text-xs text-terminal-green-dim">
          {{ bestResponders.map((d) => d.first_name).join(', ') }}
        </span>
      </div>

      <ul v-if="availableResponders.length" class="mt-2 flex flex-col gap-1">
        <li
          v-for="dweller in availableResponders"
          :key="dweller.id"
          class="flex items-center justify-between gap-2 text-xs text-terminal-green"
        >
          <span>
            {{ dweller.first_name }}
            <span class="text-terminal-green-dim">
              Lv. {{ dweller.level }} · {{ dweller.health }}/{{ dweller.max_health }} HP · POW
              {{ getCombatPower(dweller) }}
            </span>
          </span>
          <UButton
            variant="secondary"
            size="sm"
            :disabled="assigningDwellerId === dweller.id"
            @click="assignResponder(dweller.id)"
          >
            SEND
          </UButton>
        </li>
      </ul>
      <p v-else class="mt-2 text-xs text-terminal-green-dim">
        All available adults are already defending or away.
      </p>
    </div>

    <p class="flex items-center gap-1.5 text-xs text-terminal-green-dim">
      <Icon icon="mdi:lock" class="h-4 w-4" />
      Room management is locked while this incident is live.
    </p>
  </section>
</template>
