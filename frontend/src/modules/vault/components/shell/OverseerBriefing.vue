<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { UButton } from '@/core/components/ui'
import type { OverseerBriefingData } from '@/modules/vault/models/overseerBriefing'

type BriefingAction = 'incidents' | 'dwellers' | null

interface BriefingItem {
  id: string
  icon: string
  label: string
  detail: string
  tone: 'critical' | 'warning'
  action: BriefingAction
}

interface BriefingMetric {
  icon: string
  label: string
  value: string | number
}

const props = defineProps<OverseerBriefingData>()

const emit = defineEmits<{
  reviewIncidents: []
}>()

const activeOperationCount = computed(
  () => props.activeExplorationCount + props.trainingCount + props.questingCount
)
const metrics = computed<BriefingMetric[]>(() => [
  { icon: 'mdi:compass', label: 'EXPEDITIONS', value: props.activeExplorationCount },
  { icon: 'mdi:dumbbell', label: 'TRAINING', value: props.trainingCount },
  { icon: 'mdi:sword-cross', label: 'QUESTS', value: props.questingCount },
  { icon: 'mdi:account-alert', label: 'UNASSIGNED', value: props.unassignedCount },
  { icon: 'mdi:home-city-outline', label: 'CAPACITY', value: `${Math.round(props.populationUtilization)}%` },
  { icon: 'mdi:emoticon-outline', label: 'MORALE', value: `${Math.round(props.happiness)}%` },
])

const attentionItems = computed<BriefingItem[]>(() => {
  const items: BriefingItem[] = []

  if (props.activeIncidentCount > 0) {
    items.push({
      id: 'incidents',
      icon: 'mdi:alert-octagon',
      label:
        props.activeIncidentCount === 1
          ? '1 INCIDENT REQUIRES RESPONSE'
          : `${props.activeIncidentCount} INCIDENTS REQUIRE RESPONSE`,
      detail: 'Threats are active inside the vault.',
      tone: 'critical',
      action: 'incidents',
    })
  }

  for (const warning of props.resourceWarnings.slice(0, 2)) {
    items.push({
      id: `resource-${warning.type}`,
      icon: 'mdi:water-alert',
      label: 'RESOURCE ALERT',
      detail: warning.message,
      tone: 'warning',
      action: null,
    })
  }

  if (props.unassignedCount > 0) {
    items.push({
      id: 'dwellers',
      icon: 'mdi:account-alert',
      label:
        props.unassignedCount === 1
          ? '1 DWELLER AWAITS ASSIGNMENT'
          : `${props.unassignedCount} DWELLERS AWAIT ASSIGNMENT`,
      detail: 'Assign them to a room or review their status.',
      tone: 'warning',
      action: 'dwellers',
    })
  }

  if (props.populationUtilization >= 90) {
    items.push({
      id: 'capacity',
      icon: 'mdi:account-multiple-check',
      label: 'POPULATION CAPACITY IS NEAR LIMIT',
      detail: `${Math.round(props.populationUtilization)}% of living space is occupied.`,
      tone: 'warning',
      action: null,
    })
  }

  if (props.happiness < 50) {
    items.push({
      id: 'happiness',
      icon: 'mdi:emoticon-sad-outline',
      label: 'DWELLER MORALE NEEDS ATTENTION',
      detail: `Vault happiness is ${Math.round(props.happiness)}%.`,
      tone: 'warning',
      action: null,
    })
  }

  return items.slice(0, 3)
})

const statusLabel = computed(() => {
  if (props.activeIncidentCount > 0) return 'RESPONSE REQUIRED'
  if (attentionItems.value.length > 0) return 'WATCH LIST ACTIVE'
  return 'SYSTEMS NOMINAL'
})

const statusClass = computed(() => {
  if (props.activeIncidentCount > 0) return 'border-red-500/60 bg-red-950/40 text-red-300'
  if (attentionItems.value.length > 0) return 'border-yellow-500/60 bg-yellow-950/40 text-yellow-300'
  return 'border-terminal-green/50 bg-terminal-green/10 text-terminal-green'
})

const attentionClass = (tone: BriefingItem['tone']) =>
  tone === 'critical'
    ? 'border-red-500/40 bg-red-950/20 text-red-200'
    : 'border-yellow-500/40 bg-yellow-950/20 text-yellow-200'

const attentionIconClass = (tone: BriefingItem['tone']) =>
  tone === 'critical' ? 'text-red-400' : 'text-yellow-400'
</script>

<template>
  <section class="overseer-briefing border-y border-theme-primary/20 py-4">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p class="text-xs font-bold tracking-[0.2em] text-theme-accent">VAULT {{ vaultNumber }} / COMMAND TERMINAL</p>
        <h3 class="mt-1 text-base font-bold text-theme-primary">VAULT STATUS</h3>
        <p class="text-xs text-gray-400">{{ activeOperationCount }} active operations</p>
      </div>
      <span class="inline-flex items-center gap-2 rounded border px-2 py-1 text-[0.65rem] font-bold tracking-wider" :class="statusClass">
        <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-current" aria-hidden="true"></span>
        {{ statusLabel }}
      </span>
    </div>

    <div class="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
      <div
        v-for="metric in metrics"
        :key="metric.label"
        class="briefing-metric flex min-w-0 items-center gap-2 rounded border border-theme-primary/20 bg-black/30 px-2.5 py-2"
      >
        <Icon :icon="metric.icon" class="h-4 w-4 shrink-0 text-theme-accent" />
        <div class="min-w-0">
          <p class="text-[0.6rem] font-bold tracking-[0.12em] text-theme-primary/60">{{ metric.label }}</p>
          <p class="mt-0.5 text-sm font-bold tabular-nums text-theme-primary">{{ metric.value }}</p>
        </div>
      </div>
    </div>

    <div v-if="attentionItems.length" class="mt-4 space-y-2">
      <div
        v-for="item in attentionItems"
        :key="item.id"
        class="flex items-center gap-3 rounded border px-3 py-2"
        :class="attentionClass(item.tone)"
      >
        <Icon :icon="item.icon" class="h-5 w-5 shrink-0" :class="attentionIconClass(item.tone)" />
        <div class="min-w-0 flex-1">
          <p class="text-xs font-bold tracking-wide">{{ item.label }}</p>
          <p class="truncate text-xs opacity-80">{{ item.detail }}</p>
        </div>
        <span v-if="item.action === 'incidents'" class="briefing-respond shrink-0">
          <UButton
            variant="danger"
            size="xs"
            aria-label="Respond to active incidents"
            @click="emit('reviewIncidents')"
          >
            RESPOND
          </UButton>
        </span>
        <router-link
          v-else-if="item.action === 'dwellers'"
          :to="dwellersPath"
          class="shrink-0 rounded border border-yellow-300/50 px-2 py-1 text-[0.65rem] font-bold hover:bg-yellow-300/10"
        >
          REVIEW
        </router-link>
      </div>
    </div>
    <p v-else class="mt-4 text-center text-xs tracking-wider text-terminal-green/80">
      No immediate action queued. The vault is holding steady.
    </p>
  </section>
</template>
