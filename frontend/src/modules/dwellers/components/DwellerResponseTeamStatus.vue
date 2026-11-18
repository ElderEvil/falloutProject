<script setup lang="ts">
import { computed, watch } from 'vue'
import DwellerStateChip from './DwellerStateChip.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useResponseStationStore } from '@/modules/rooms/stores/responseStation'
import { HAZARD_TEAM_CONFIG } from '@/modules/contamination-team/models/contaminationTeam'

const props = defineProps<{ dwellerId: string; vaultId: string }>()

const authStore = useAuthStore()
const stationStore = useResponseStationStore()
const roster = computed(() =>
  stationStore.roster?.vault_id === props.vaultId ? stationStore.roster : null
)

watch(
  [() => props.vaultId, () => authStore.sessionGeneration],
  () => {
    if (props.vaultId && !roster.value) void stationStore.loadRoster(props.vaultId)
  },
  { immediate: true }
)

interface TeamChip {
  label: string
  icon: string
  title: string
}

const chips = computed<TeamChip[]>(() => {
  if (!roster.value) return []
  const result: TeamChip[] = []
  for (const team of ['fire', 'radiation'] as const) {
    const teamRoster = roster.value.teams.find((t) => t.team === team)
    if (!teamRoster) continue
    const config = HAZARD_TEAM_CONFIG[team]
    if (teamRoster.active.some((m) => m.dweller_id === props.dwellerId)) {
      result.push({
        label: `${config.label} Team`,
        icon: config.icon,
        title: `Active on the vault's ${config.label} response team`,
      })
    } else if (teamRoster.reserve.some((m) => m.dweller_id === props.dwellerId)) {
      result.push({
        label: `${config.label} Team · Reserve`,
        icon: config.icon,
        title: `Reserve (bench) on the ${config.label} response team`,
      })
    }
  }
  return result
})
</script>

<template>
  <DwellerStateChip
    v-for="chip in chips"
    :key="chip.label"
    :icon="chip.icon"
    :label="chip.label"
    :title="chip.title"
    size="large"
    class="border-theme-primary/50 bg-terminal-background text-theme-primary terminal-glow"
  />
</template>
