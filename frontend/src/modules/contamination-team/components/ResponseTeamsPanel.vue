<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import TerminalEmptyState from '@/core/components/common/TerminalEmptyState.vue'
import TerminalLoadingState from '@/core/components/common/TerminalLoadingState.vue'
import { HAZARD_TEAM_SIZE } from '../models/contaminationTeam'
import type {
  ContaminationTeamRead,
  HazardTeam,
  HazardTeamMemberRead,
  HazardTeamRosterRead,
} from '../models/contaminationTeam'

const props = withDefaults(
  defineProps<{
    roster: ContaminationTeamRead | null
    loading: boolean
    error: string | null
    busyDwellerIds?: string[]
  }>(),
  { busyDwellerIds: () => [] }
)

const emit = defineEmits<{
  'set-place': [team: HazardTeam, dwellerId: string, active: boolean]
}>()

const TEAM_CONFIG: Record<HazardTeam, { label: string; icon: string }> = {
  fire: { label: 'Fire', icon: 'mdi:fire' },
  radiation: { label: 'Radiation', icon: 'mdi:radioactive' },
}

const memberName = (member: HazardTeamMemberRead) => member.name || 'Unknown dweller'

const teamSections = (team: HazardTeamRosterRead) => [
  { label: 'Active', members: team.active, isActive: true },
  { label: 'Reserve', members: team.reserve, isActive: false },
]

const isBusy = (dwellerId: string) => props.busyDwellerIds.includes(dwellerId)
</script>

<template>
  <TerminalLoadingState v-if="loading" message="Loading response teams..." />

  <TerminalEmptyState
    v-else-if="error"
    icon="mdi:alert-circle-outline"
    title="Failed to load response teams"
    :description="error"
    compact
  />

  <TerminalEmptyState
    v-else-if="!roster || roster.teams.length === 0"
    icon="mdi:shield-off-outline"
    title="No response teams yet"
    description="Dwellers earn a place on a team by fighting incidents."
    compact
  />

  <div v-else class="grid grid-cols-1 gap-4 md:grid-cols-2">
    <section
      v-for="team in roster.teams"
      :key="team.team"
      class="rounded-lg border border-theme-primary/30 bg-surface p-3"
    >
      <header class="mb-3 flex items-center justify-between gap-2">
        <h3 class="flex items-center gap-2 text-sm font-bold text-theme-primary">
          <Icon :icon="TEAM_CONFIG[team.team].icon" class="h-4 w-4" />
          {{ TEAM_CONFIG[team.team].label }} Team
        </h3>
        <Badge variant="outline" class="border-theme-primary/40 text-theme-primary/80">
          {{ team.active.length }} active · {{ team.reserve.length }} reserve
        </Badge>
      </header>

      <div class="flex flex-col gap-3">
        <div v-for="section in teamSections(team)" :key="section.label">
          <h4
            class="mb-1.5 text-xs font-semibold uppercase tracking-wider text-theme-primary/60"
          >
            {{ section.label }}
          </h4>
          <ul v-if="section.members.length > 0" class="flex flex-col gap-1.5">
            <li
              v-for="member in section.members"
              :key="member.dweller_id"
              class="flex items-center justify-between gap-2 rounded border-l-[3px] border-theme-primary/50 bg-terminal-background px-2.5 py-1.5"
            >
              <span class="truncate text-sm font-semibold text-terminal-green">
                {{ memberName(member) }}
              </span>
              <span class="flex shrink-0 items-center gap-2 text-xs">
                <span class="text-theme-primary/70">
                  LVL {{ member.level }}
                </span>
                <Button
                  v-if="section.isActive"
                  variant="outline"
                  size="xs"
                  :disabled="isBusy(member.dweller_id)"
                  @click="emit('set-place', team.team, member.dweller_id, false)"
                >
                  Bench
                </Button>
                <Button
                  v-else
                  variant="outline"
                  size="xs"
                  :disabled="
                    isBusy(member.dweller_id) || team.active.length >= HAZARD_TEAM_SIZE
                  "
                  @click="emit('set-place', team.team, member.dweller_id, true)"
                >
                  Activate
                </Button>
              </span>
            </li>
          </ul>
          <p v-else class="text-xs italic text-theme-primary/40">
            No {{ section.label.toLowerCase() }} members
          </p>
        </div>
      </div>
    </section>
  </div>
</template>
