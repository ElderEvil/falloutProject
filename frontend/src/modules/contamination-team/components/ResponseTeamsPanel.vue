<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { Card, CardHeader, CardTitle, CardContent } from '@/core/components/ui/card'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import TerminalEmptyState from '@/core/components/common/TerminalEmptyState.vue'
import TerminalLoadingState from '@/core/components/common/TerminalLoadingState.vue'
import { HAZARD_TEAM_SIZE, HAZARD_TEAM_CONFIG } from '../models/contaminationTeam'
import ResponseTeamMemberRow from './ResponseTeamMemberRow.vue'
import type {
  ContaminationTeamRead,
  HazardTeam,
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
  'view-dweller': [dwellerId: string]
  refresh: []
}>()

const teamSections = (team: HazardTeamRosterRead) => [
  { label: 'Active', members: team.active, isActive: true },
  { label: 'Reserve', members: team.reserve, isActive: false },
]

const isBusy = () => props.busyDwellerIds.length > 0
</script>

<template>
  <TerminalLoadingState v-if="loading" message="Loading response teams..." />

  <TerminalEmptyState
    v-else-if="error"
    icon="mdi:alert-circle-outline"
    title="Failed to load response teams"
    :description="error"
    compact
  >
    <template #actions
      ><Button variant="outline" size="sm" @click="emit('refresh')">Retry</Button></template
    >
  </TerminalEmptyState>

  <TerminalEmptyState
    v-else-if="!roster || roster.teams.length === 0"
    icon="mdi:shield-off-outline"
    title="No response teams yet"
    description="Dwellers earn a place on a team by fighting incidents."
    compact
  />

  <div v-else class="space-y-4">
    <p
      class="rounded border border-theme-primary/20 bg-surface-sunken p-3 text-sm leading-relaxed text-theme-primary/70"
    >
      Membership is earned through incident participation. Active members automatically answer
      matching hazards when available; reserves wait for an active place. Inspect a member to check
      their health and equipment.
    </p>
    <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card
        v-for="team in roster.teams"
        :key="team.team"
        class="min-w-0 border border-theme-primary/30"
      >
        <CardHeader class="gap-2">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <CardTitle class="flex items-center gap-2 text-base text-theme-primary">
              <Icon :icon="HAZARD_TEAM_CONFIG[team.team].icon" class="h-4 w-4" />
              {{ HAZARD_TEAM_CONFIG[team.team].label }} Team
            </CardTitle>
            <Badge variant="outline" class="border-theme-primary/40 text-theme-primary/80">
              {{ team.active.length }} / {{ HAZARD_TEAM_SIZE }} active places
            </Badge>
          </div>
          <p class="text-xs leading-relaxed text-theme-primary/65">
            {{ HAZARD_TEAM_CONFIG[team.team].description }}
          </p>
        </CardHeader>

        <CardContent class="flex flex-col gap-4">
          <div v-for="section in teamSections(team)" :key="section.label">
            <h4 class="mb-1.5 text-xs font-semibold uppercase tracking-wider text-theme-primary/60">
              {{ section.label }} · {{ section.members.length }}
            </h4>
            <ul v-if="section.members.length > 0" class="flex flex-col gap-1.5">
              <ResponseTeamMemberRow
                v-for="member in section.members"
                :key="member.dweller_id"
                :member="member"
                :active="section.isActive"
                :disabled="
                  isBusy() || (!section.isActive && team.active.length >= HAZARD_TEAM_SIZE)
                "
                @view-dweller="emit('view-dweller', $event)"
                @set-place="emit('set-place', team.team, member.dweller_id, $event)"
              />
            </ul>
            <p
              v-else
              class="rounded border border-dashed border-theme-primary/20 p-3 text-xs leading-relaxed text-theme-primary/60"
            >
              No {{ section.label.toLowerCase() }} members<span v-if="section.isActive">
                — qualified dwellers can hold an active place.</span
              ><span v-else> — additional qualifiers join the reserve.</span>
            </p>
            <p
              v-if="section.isActive && team.active.length < HAZARD_TEAM_SIZE"
              class="mt-2 text-xs text-theme-primary/60"
            >
              {{ HAZARD_TEAM_SIZE - team.active.length }} open places<span
                v-if="team.reserve.length"
              >
                — activate a reserve member to fill one.</span
              >
            </p>
            <p
              v-else-if="
                !section.isActive && team.reserve.length && team.active.length >= HAZARD_TEAM_SIZE
              "
              class="mt-2 text-xs text-theme-primary/60"
            >
              Active roster is full. Bench a member before activating a reserve.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>
