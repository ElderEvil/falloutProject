<script setup lang="ts">
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import TerminalMetric from '@/core/components/common/TerminalMetric.vue'
import type { OverseerBriefingData, ReadyActionKind } from '@/modules/vault/models/overseerBriefing'

type BriefingAction = 'incidents' | 'dwellers' | null

interface BriefingItem {
  id: string
  icon: string
  label: string
  tone: 'critical' | 'warning'
  action: BriefingAction
}

interface BriefingMetric {
  icon: string
  label: string
  value: string | number
}

const READY_ACTION_ICONS: Record<ReadyActionKind, string> = {
  incident_aftermath: 'mdi:alert-octagon',
  exploration_outcome: 'mdi:compass',
  quest_claim: 'mdi:sword-cross',
  objective_claim: 'mdi:target',
  crafting_collect: 'mdi:hammer-wrench',
  training_complete: 'mdi:dumbbell',
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
  {
    icon: 'mdi:home-city-outline',
    label: 'CAPACITY',
    value: `${Math.round(props.populationUtilization)}%`,
  },
  { icon: 'mdi:emoticon-outline', label: 'MORALE', value: `${Math.round(props.happiness)}%` },
])

const allAttentionItems = computed<BriefingItem[]>(() => {
  const items: BriefingItem[] = []

  if (props.activeIncidentCount > 0) {
    items.push({
      id: 'incidents',
      icon: 'mdi:alert-octagon',
      label:
        props.activeIncidentCount === 1
          ? '1 INCIDENT REQUIRES RESPONSE'
          : `${props.activeIncidentCount} INCIDENTS REQUIRE RESPONSE`,
      tone: 'critical',
      action: 'incidents',
    })
  }

  for (const warning of props.resourceWarnings.slice(0, 2)) {
    items.push({
      id: `resource-${warning.type}`,
      icon: 'mdi:water-alert',
      label: warning.message,
      tone: 'warning',
      action: 'dwellers',
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
      tone: 'warning',
      action: 'dwellers',
    })
  }

  if (props.populationUtilization >= 90) {
    items.push({
      id: 'capacity',
      icon: 'mdi:account-multiple-check',
      label: `POPULATION CAPACITY IS NEAR LIMIT (${Math.round(props.populationUtilization)}%)`,
      tone: 'warning',
      action: null,
    })
  }

  if (props.happiness < 50) {
    items.push({
      id: 'happiness',
      icon: 'mdi:emoticon-sad-outline',
      label: `DWELLER MORALE NEEDS ATTENTION (${Math.round(props.happiness)}%)`,
      tone: 'warning',
      action: null,
    })
  }

  return items
})

// No aggregate attention route exists, so overflow expands in place instead of inventing one.
const showAllAttention = ref(false)
const visibleAttentionItems = computed(() =>
  showAllAttention.value ? allAttentionItems.value : allAttentionItems.value.slice(0, 3)
)
const hasMoreAttention = computed(() => allAttentionItems.value.length > 3)

const statusLabel = computed(() => {
  if (props.activeIncidentCount > 0) return 'RESPONSE REQUIRED'
  if (allAttentionItems.value.length > 0) return 'WATCH LIST ACTIVE'
  return 'SYSTEMS NOMINAL'
})

const statusClass = computed(() => {
  if (props.activeIncidentCount > 0) return 'border-danger/60 bg-danger/10 text-foreground'
  if (allAttentionItems.value.length > 0) return 'border-warning/60 bg-warning/10 text-foreground'
  return 'border-terminal-green/50 bg-terminal-green/10 text-terminal-green'
})

const attentionClass = (tone: BriefingItem['tone']) =>
  tone === 'critical'
    ? 'border-danger/40 bg-danger/10 text-foreground'
    : 'border-warning/40 bg-warning/10 text-foreground'

const attentionIconClass = (tone: BriefingItem['tone']) =>
  tone === 'critical' ? 'text-danger' : 'text-warning'
</script>

<template>
  <section class="overseer-briefing border-y border-theme-primary/20 py-4">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p class="text-xs font-bold tracking-[0.2em] text-theme-accent">
          VAULT {{ vaultNumber }} / COMMAND TERMINAL
        </p>
        <h3 class="mt-1 text-base font-bold text-theme-primary">VAULT STATUS</h3>
        <p class="text-xs text-muted-foreground">{{ activeOperationCount }} active operations</p>
      </div>
      <span
        class="inline-flex items-center gap-2 rounded border px-2 py-1 text-[0.65rem] font-bold tracking-wider"
        :class="statusClass"
      >
        <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-current" aria-hidden="true"></span>
        {{ statusLabel }}
      </span>
    </div>

    <div class="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
      <TerminalMetric
        v-for="metric in metrics"
        :key="metric.label"
        class="briefing-metric"
        :icon="metric.icon"
        :label="metric.label"
        :value="metric.value"
        tone="accent"
        compact
      />
    </div>

    <div v-if="allAttentionItems.length" class="mt-4 space-y-2">
      <div
        v-for="item in visibleAttentionItems"
        :key="item.id"
        class="flex items-center gap-3 rounded border px-3 py-2"
        :class="attentionClass(item.tone)"
      >
        <Icon :icon="item.icon" class="h-5 w-5 shrink-0" :class="attentionIconClass(item.tone)" />
        <div class="min-w-0 flex-1">
          <p class="text-xs font-bold tracking-wide">{{ item.label }}</p>
        </div>
        <span v-if="item.action === 'incidents'" class="briefing-respond shrink-0">
          <Button
            variant="outline"
            size="xs"
            class="border-2 border-theme-primary bg-transparent"
            aria-label="Respond to active incidents"
            @click="emit('reviewIncidents')"
          >
            RESPOND
          </Button>
        </span>
        <router-link
          v-else-if="item.action === 'dwellers'"
          :to="dwellersPath"
          class="shrink-0 rounded border border-warning/50 px-2 py-1 text-[0.65rem] font-bold hover:bg-warning/10"
        >
          REVIEW
        </router-link>
      </div>

      <Button
        v-if="hasMoreAttention"
        variant="ghost"
        size="xs"
        class="w-full justify-center text-[0.65rem] font-bold tracking-widest text-theme-primary"
        v-bind="{ 'data-testid': 'attention-overflow-toggle' }"
        @click="showAllAttention = !showAllAttention"
      >
        {{ showAllAttention ? 'SHOW LESS' : `VIEW ALL (${allAttentionItems.length})` }}
      </Button>
    </div>

    <div
      v-if="readyActions.length"
      class="mt-4 space-y-2"
      v-bind="{ 'data-testid': 'ready-actions' }"
    >
      <p class="text-[0.65rem] font-bold tracking-[0.2em] text-muted-foreground">READY ACTIONS</p>
      <RouterLink
        v-for="action in readyActions"
        :key="action.kind"
        :to="action.route"
        v-bind="{ 'data-testid': `ready-action-${action.kind}` }"
        class="flex items-center gap-3 rounded border border-theme-primary/20 bg-surface px-3 py-2 transition-colors hover:bg-surface-warm-hover"
      >
        <Icon :icon="READY_ACTION_ICONS[action.kind]" class="h-5 w-5 shrink-0 text-theme-primary" />
        <p class="min-w-0 flex-1 text-xs font-bold tracking-wide text-theme-primary">
          {{ action.label }}
        </p>
        <span
          class="shrink-0 rounded border border-theme-primary/30 px-1.5 py-0.5 text-[0.65rem] font-bold text-theme-primary"
        >
          {{ action.count }}
        </span>
        <Icon
          icon="mdi:chevron-right"
          class="h-4 w-4 shrink-0 text-muted-foreground"
          :ariaHidden="true"
        />
      </RouterLink>
    </div>

    <p
      v-if="!allAttentionItems.length && !readyActions.length"
      class="mt-4 text-center text-xs tracking-wider text-terminal-green/80"
    >
      All clear.
    </p>
  </section>
</template>
