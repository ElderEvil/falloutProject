<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/core/components/ui/tooltip'
import { useDwellerDetailContext } from './DwellerDetailContext'
import { ABILITY_CONFIG, getHighestSpecial, isMature } from '../models/dweller'

const ctx = useDwellerDetailContext()

const dweller = computed(() => ctx.dweller.value)
const bestStat = computed(() => (dweller.value ? getHighestSpecial(dweller.value) : null))
const bestLabel = computed(() => (bestStat.value ? ABILITY_CONFIG[bestStat.value].label : ''))

// Youth are apprenticed to the room's ability by construction, so the match is
// only informative for adults who were assigned as workers.
const applies = computed(
  () => !!dweller.value && !!dweller.value.room?.ability && isMature(dweller.value)
)
const matched = computed(() => dweller.value?.room?.ability === bestStat.value)
const tooltip = computed(() =>
  matched.value
    ? `${bestLabel.value} is their strongest stat, and this room trains it.`
    : `Their strongest stat is ${bestLabel.value} — a ${bestLabel.value} room would use it.`
)
</script>

<template>
  <TooltipProvider v-if="applies" :delay-duration="200">
    <Tooltip>
      <TooltipTrigger as-child>
        <span class="role-match" :class="matched ? 'role-match-ok' : 'role-match-off'">
          <Icon :icon="matched ? 'mdi:check-circle-outline' : 'mdi:alert-circle-outline'" class="role-match-icon" />
          {{ matched ? 'Matched' : 'Mismatch' }}
        </span>
      </TooltipTrigger>
      <TooltipContent side="top">{{ tooltip }}</TooltipContent>
    </Tooltip>
  </TooltipProvider>
</template>

<style scoped>
.role-match {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.1rem 0.5rem;
  border: 1px solid currentColor;
  border-radius: var(--border-radius-base);
  font-size: 0.7rem;
  white-space: nowrap;
}

.role-match-ok {
  color: var(--color-theme-primary);
  opacity: 0.75;
}

.role-match-off {
  color: var(--color-warning);
}

.role-match-icon {
  width: 0.85rem;
  height: 0.85rem;
  flex-shrink: 0;
}
</style>
