<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Badge } from '@/core/components/ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/core/components/ui/tooltip'
import type { Exploration } from '@/modules/exploration/stores/exploration'
import { getStatusConfig } from '@/modules/dwellers/models/dweller'
import type { DetailedDweller, Dweller } from '@/modules/dwellers/models/dweller'
import {
  getProgressPercentage,
  getTimeRemaining,
  isReadyToComplete,
} from '@/modules/exploration/composables/useExplorationProgress'

interface Props {
  exploration: Exploration
  dweller?: DetailedDweller | Dweller | null
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
</script>

<template>
  <div v-if="isExploring || isReturning || isReady || isAtRisk" class="flex flex-wrap items-center gap-1.5">
    <TooltipProvider v-if="isExploring" :delay-duration="200">
      <Tooltip>
        <TooltipTrigger as-child>
          <span>
            <Badge
              variant="outline"
              :class="[exploringConfig.color, exploringConfig.bgColor, exploringConfig.borderColor]"
            >
              <Icon :icon="exploringConfig.icon" class="h-3 w-3" />
              EXPLORING
            </Badge>
          </span>
        </TooltipTrigger>
        <TooltipContent>Exploring — {{ Math.round(progress) }}%</TooltipContent>
      </Tooltip>
    </TooltipProvider>

    <TooltipProvider v-if="isReturning" :delay-duration="200">
      <Tooltip>
        <TooltipTrigger as-child>
          <span><Badge variant="secondary">RETURNING</Badge></span>
        </TooltipTrigger>
        <TooltipContent>{{ timeRemaining }}</TooltipContent>
      </Tooltip>
    </TooltipProvider>

    <TooltipProvider v-if="isReady" :delay-duration="200">
      <Tooltip>
        <TooltipTrigger as-child>
          <span><Badge variant="default">READY</Badge></span>
        </TooltipTrigger>
        <TooltipContent>Expedition finished — ready to collect</TooltipContent>
      </Tooltip>
    </TooltipProvider>

    <TooltipProvider v-if="isAtRisk" :delay-duration="200">
      <Tooltip>
        <TooltipTrigger as-child>
          <span aria-label="Dweller at risk">
            <Badge variant="outline" class="border-warning/50 bg-warning/10 text-warning">
              <Icon icon="mdi:heart-pulse" class="h-3 w-3" />
              AT RISK
            </Badge>
          </span>
        </TooltipTrigger>
        <TooltipContent>{{ riskTitle }}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  </div>
</template>
