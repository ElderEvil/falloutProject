<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Badge } from '@/core/components/ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/core/components/ui/tooltip'
import type { Exploration } from '@/modules/exploration/stores/exploration'
import { getStatusConfig } from '@/modules/dwellers/models/dweller'
import type { DetailedDweller, Dweller, DwellerShort } from '@/modules/dwellers/models/dweller'
import {
  getProgressPercentage,
  getTimeRemaining,
  isReadyToComplete,
} from '@/modules/exploration/composables/useExplorationProgress'

interface Props {
  exploration: Exploration
  dweller?: DetailedDweller | Dweller | DwellerShort | null
  /** Icon-only chips (list surfaces); false keeps the labeled form (detail page). */
  compact?: boolean
}

const props = defineProps<Props>()

const progress = computed(() => getProgressPercentage(props.exploration))
const isReady = computed(() => isReadyToComplete(props.exploration))
const isReturning = computed(() => props.exploration.status === 'returning')
// Persistent chip: an active run that is not yet ready is always EXPLORING.
const isExploring = computed(() => props.exploration.status === 'active' && !isReady.value)

// Low HP (<=30%) or heavy radiation (>=50% of max) based on live dweller vitals.
const isAtRisk = computed(() => {
  const d = props.dweller
  if (!d || !d.max_health) return false
  return d.health / d.max_health <= 0.3 || d.radiation / d.max_health >= 0.5
})

const riskTitle = computed(() =>
  props.dweller
    ? `Health ${props.dweller.health}/${props.dweller.max_health}, radiation ${props.dweller.radiation}`
    : ''
)

const timeRemaining = computed(() => getTimeRemaining(props.exploration))

// Reuse the dweller status visuals for the persistent EXPLORING chip.
const exploringConfig = getStatusConfig('exploring')
// Every non-alert state shares one colour treatment so the chip reads consistently.
const statusBadgeClass = [exploringConfig.color, exploringConfig.bgColor, exploringConfig.borderColor]
// Compact chips drop the text label and tighten padding, like the small icon-only dweller badges.
const compactClass = computed(() => (props.compact ? 'gap-0 px-1.5 py-0.5' : ''))

interface StatusChip {
  key: string
  icon: string
  label: string
  tooltip: string
  classes: string[] | string
  ariaLabel?: string
}

// One data-driven source for the status chips, in display order.
const chips = computed<StatusChip[]>(() => {
  const list: StatusChip[] = []
  if (isExploring.value) {
    list.push({
      key: 'exploring',
      icon: exploringConfig.icon,
      label: 'EXPLORING',
      tooltip: `Exploring — ${Math.round(progress.value)}%`,
      classes: statusBadgeClass,
    })
  }
  if (isReturning.value) {
    list.push({
      key: 'returning',
      icon: 'mdi:home-import-outline',
      label: 'RETURNING',
      tooltip: timeRemaining.value,
      classes: statusBadgeClass,
    })
  }
  if (isReady.value) {
    list.push({
      key: 'ready',
      icon: 'mdi:checkbox-marked-circle-outline',
      label: 'READY',
      tooltip: 'Expedition finished — ready to collect',
      classes: statusBadgeClass,
    })
  }
  if (isAtRisk.value) {
    list.push({
      key: 'at-risk',
      icon: 'mdi:heart-pulse',
      label: 'AT RISK',
      tooltip: riskTitle.value,
      classes: 'border-warning/50 bg-warning/10 text-warning',
      ariaLabel: 'Dweller at risk',
    })
  }
  return list
})
</script>

<template>
  <div v-if="chips.length" class="flex flex-wrap items-center gap-1.5">
    <TooltipProvider v-for="chip in chips" :key="chip.key" :delay-duration="200">
      <Tooltip>
        <TooltipTrigger as-child>
          <span :aria-label="compact ? chip.label : chip.ariaLabel">
            <Badge variant="outline" :class="[chip.classes, compactClass]">
              <Icon :icon="chip.icon" class="h-3 w-3" />
              <span v-if="!compact">{{ chip.label }}</span>
            </Badge>
          </span>
        </TooltipTrigger>
        <TooltipContent>{{ chip.tooltip }}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  </div>
</template>
