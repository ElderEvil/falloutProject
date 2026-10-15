<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { HAZARD_TEAM_CONFIG } from '../models/contaminationTeam'
import type { HazardTeam, HazardTeamMemberRead } from '../models/contaminationTeam'

const props = defineProps<{
  member: HazardTeamMemberRead
  team: HazardTeam
  active: boolean
  disabled: boolean
}>()
defineEmits<{
  'view-dweller': [dwellerId: string]
  'set-place': [active: boolean]
}>()

const config = computed(() => HAZARD_TEAM_CONFIG[props.team])
const serviceCount = computed(() => props.member.service_count ?? 0)
const serviceLabel = computed(() =>
  serviceCount.value === 1 ? '1 incident served' : `${serviceCount.value} incidents served`
)
const resistPercent = computed(() => Math.round((props.member.hazard_resist ?? 0) * 100))

// A missing matching suit is not zero protection: the read always carries the
// share of this hazard the worn outfit removes, and the row states it verbatim.
const gearShortLabel = computed(
  () =>
    `${props.member.has_matching_gear ? 'Matching suit' : 'No matching suit'} · protection ${resistPercent.value}%`
)
const gearAccessibleLabel = computed(() => {
  const hazard = config.value.label.toLowerCase()
  const equipped = props.member.has_matching_gear
    ? `Matching ${config.value.suitName} equipped`
    : `No matching ${config.value.suitName} equipped`
  return `${equipped}. Worn gear removes ${resistPercent.value} percent of ${hazard} hazard damage.`
})
</script>

<template>
  <li
    class="flex items-center justify-between gap-2 rounded border-l-[3px] border-theme-primary/50 bg-terminal-background px-2.5 py-1.5"
  >
    <div class="flex min-w-0 flex-1 flex-col">
      <Button
        variant="link"
        class="h-auto min-w-0 justify-start whitespace-normal p-0 text-left text-sm"
        @click="$emit('view-dweller', member.dweller_id)"
      >
        <span class="break-words">{{ member.name || 'Unknown dweller' }}</span>
        <Icon icon="mdi:open-in-new" class="size-3 shrink-0" :ariaHidden="true" />
      </Button>
      <div
        class="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs leading-relaxed text-theme-primary/70"
      >
        <span>{{ serviceLabel }}</span>
        <span aria-hidden="true">·</span>
        <span class="inline-flex min-w-0 items-center gap-1">
          <Icon
            :icon="member.has_matching_gear ? 'mdi:shield-check' : 'mdi:shield-outline'"
            class="size-3.5 shrink-0"
            :ariaHidden="true"
          />
          <span class="sr-only">{{ gearAccessibleLabel }}</span>
          <span aria-hidden="true" class="truncate">{{ gearShortLabel }}</span>
        </span>
      </div>
    </div>
    <span class="flex shrink-0 items-center gap-2 text-xs">
      <span class="text-theme-primary/70">LVL {{ member.level }}</span>
      <Button variant="outline" size="xs" :disabled="disabled" @click="$emit('set-place', !active)">
        {{ active ? 'Bench' : 'Activate' }}
      </Button>
    </span>
  </li>
</template>
