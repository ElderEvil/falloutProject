<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import DwellerStateChip from './DwellerStateChip.vue'
import { useAsyncAction } from '@/core/composables/useAsyncAction'
import { contaminationTeamApi } from '@/modules/contamination-team'
import { HAZARD_TEAM_CONFIG } from '@/modules/contamination-team/models/contaminationTeam'
import type { ContaminationTeamRead } from '@/modules/contamination-team'

const props = defineProps<{ dwellerId: string; vaultId: string }>()

const authStore = useAuthStore()

const roster = ref<ContaminationTeamRead | null>(null)

const { run } = useAsyncAction(
  async (vaultId: string, token: string) => contaminationTeamApi.getRoster(vaultId, token),
  { context: 'Failed to load response teams' }
)

onMounted(async () => {
  if (!props.vaultId || !authStore.token) return
  roster.value = await run(props.vaultId, authStore.token)
})

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
