<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import DwellerStateChip from './DwellerStateChip.vue'
import { useAsyncAction } from '@/core/composables/useAsyncAction'
import { contaminationTeamApi } from '@/modules/contamination-team'
import type { ContaminationTeamRead, HazardTeam } from '@/modules/contamination-team'

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

const TEAM_CONFIG: Record<
  HazardTeam,
  { label: string; icon: string; activeTitle: string; reserveTitle: string }
> = {
  fire: {
    label: 'Fire Team',
    icon: 'mdi:fire',
    activeTitle: "Active on the vault's Fire response team",
    reserveTitle: 'Reserve (bench) on the Fire response team',
  },
  radiation: {
    label: 'Radiation Team',
    icon: 'mdi:radioactive',
    activeTitle: "Active on the vault's Radiation response team",
    reserveTitle: 'Reserve (bench) on the Radiation response team',
  },
}

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
    const config = TEAM_CONFIG[team]
    if (teamRoster.active.some((m) => m.dweller_id === props.dwellerId)) {
      result.push({ label: config.label, icon: config.icon, title: config.activeTitle })
    } else if (teamRoster.reserve.some((m) => m.dweller_id === props.dwellerId)) {
      result.push({
        label: `${config.label} · Reserve`,
        icon: config.icon,
        title: config.reserveTitle,
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