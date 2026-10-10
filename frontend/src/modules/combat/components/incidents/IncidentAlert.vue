<template>
  <button
    type="button"
    class="incident-alert flex w-full items-center gap-4 overflow-hidden rounded border-2 border-danger px-4 text-left"
    :class="{ 'badge-live': hasActiveIncidents }"
    :disabled="!primaryIncident"
    :aria-label="primaryIncident ? `Open ${incidentTitle} incident` : 'No active incidents'"
    @click="incidents[0]?.id && $emit('click', incidents[0].id)"
  >
    <span
      class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-danger bg-danger/20"
    >
      <Icon :icon="incidentIcon" class="h-6 w-6 text-danger" />
    </span>

    <span class="flex flex-1 flex-col gap-1">
      <span class="text-base font-bold tracking-wide text-danger">{{ incidentTitle }}</span>
      <span class="text-xs text-danger">{{ incidentSubtitle }}</span>
    </span>

    <span class="shrink-0 text-xl font-bold tracking-widest text-danger">{{ elapsedTime }}</span>

    <span
      v-if="primaryIncident && incidentStore.hasLoadedIncidentTeam(primaryIncident.id)"
      class="badge-info shrink-0 rounded-full border border-danger/40 px-3 py-1 text-xs font-semibold text-danger"
      :aria-label="responderStatusLabel"
    >
      <Icon icon="mdi:account-group" class="mr-1 inline h-3.5 w-3.5" />
      {{ responderStatusText }}
    </span>

    <span
      v-if="incidents.length > 1"
      class="shrink-0 rounded-full bg-danger px-3 py-1 text-xs font-bold text-gray-100"
    >
      {{ incidents.length }} ACTIVE
    </span>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useNow } from '@/core/composables/useNow'
import { parseUtcMs } from '@/core/utils/time'
import type { Incident } from '../../models/incident'
import { getIncidentIcon } from '../../models/incident'
import { useIncidentStore } from '../../stores/incident'
import { formatClock, threatName } from '@/core/utils/format'

interface Props {
  incidents: Incident[]
}

const props = defineProps<Props>()

const incidentStore = useIncidentStore()

defineEmits<{
  click: [incidentId: string]
}>()

// Timer for elapsed time updates
const currentTime = useNow(1000)

// Computed
const hasActiveIncidents = computed(() => props.incidents.length > 0)

const primaryIncident = computed(() => props.incidents[0])

const incidentIcon = computed(() => (primaryIncident.value ? getIncidentIcon(primaryIncident.value.type) : 'mdi:alert-octagon'))

const incidentTitle = computed(() => {
  if (!primaryIncident.value) return 'INCIDENT ALERT'

  return threatName(primaryIncident.value.type)
})

const incidentSubtitle = computed(() => {
  if (!primaryIncident.value) return ''

  const difficulty = primaryIncident.value.difficulty
  const stars = '★'.repeat(difficulty)

  return `DIFFICULTY: ${stars} (${difficulty}/10)`
})

const elapsedTime = computed(() => {
  if (!primaryIncident.value) return '00:00'

  const startMs = parseUtcMs(primaryIncident.value.start_time)
  const elapsed = Math.floor((currentTime.value - startMs) / 1000)
  return formatClock(elapsed, { showHours: false })
})

// The designated responder roster is a fact about the incident: informational
// chip, shown only once the team has loaded so a missing fetch never reads as 0.
const primaryResponderCount = computed(() =>
  primaryIncident.value ? incidentStore.getIncidentTeam(primaryIncident.value.id).length : 0
)

const responderStatusText = computed(() =>
  primaryResponderCount.value > 0 ? `${primaryResponderCount.value} on scene` : 'No responders'
)

const responderStatusLabel = computed(() =>
  primaryResponderCount.value > 0
    ? `${primaryResponderCount.value} responder${primaryResponderCount.value === 1 ? '' : 's'} on scene`
    : 'No responders on scene'
)
</script>

<style scoped>
.incident-alert {
  height: 60px;
  color: var(--color-danger);
  cursor: pointer;
  transition-duration: var(--transition-base);
}

.incident-alert:disabled {
  cursor: default;
}

/* Live status rides --glow-3 via .badge-live; hovering promotes it to the
   interactive tier because this banner is also the entry point to the room. */
.incident-alert:hover:not(:disabled) {
  --glow: var(--glow-2);
}
</style>
