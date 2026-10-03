<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import PageHeaderMetric from '@/core/components/common/PageHeaderMetric.vue'
import VaultPageShell from '@/core/components/common/VaultPageShell.vue'
import { useAsyncAction } from '@/core/composables/useAsyncAction'
import { contaminationTeamApi } from '../api'
import type { ContaminationTeamRead, HazardTeam } from '../models/contaminationTeam'
import ResponseTeamsPanel from '../components/ResponseTeamsPanel.vue'

const route = useRoute()
const authStore = useAuthStore()
const vaultId = computed(() => route.params.id as string)

const roster = ref<ContaminationTeamRead | null>(null)

const { run, isLoading, error } = useAsyncAction(
  async (vaultId: string, token: string) => contaminationTeamApi.getRoster(vaultId, token),
  { context: 'Failed to load response teams' }
)

onMounted(async () => {
  if (!vaultId.value || !authStore.token) return
  roster.value = await run(vaultId.value, authStore.token)
})

const activeTotal = computed(
  () => roster.value?.teams.reduce((sum, team) => sum + team.active.length, 0) ?? 0
)
const reserveTotal = computed(
  () => roster.value?.teams.reduce((sum, team) => sum + team.reserve.length, 0) ?? 0
)

const busyDwellerIds = ref<Set<string>>(new Set())
const busyDwellerIdsArray = computed(() => [...busyDwellerIds.value])

const { run: runSetPlace } = useAsyncAction(
  async (vaultId: string, team: HazardTeam, dwellerId: string, active: boolean, token: string) =>
    contaminationTeamApi.setPlace(vaultId, team, dwellerId, active, token),
  { context: 'Failed to update response team' }
)

const handleSetPlace = async (team: HazardTeam, dwellerId: string, active: boolean) => {
  if (!vaultId.value || !authStore.token) return
  busyDwellerIds.value.add(dwellerId)
  try {
    const updated = await runSetPlace(vaultId.value, team, dwellerId, active, authStore.token)
    if (updated) roster.value = updated
  } finally {
    busyDwellerIds.value.delete(dwellerId)
  }
}
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-terminal-green">
    <VaultPageShell flicker>
      <PageContentRail class="flex flex-col gap-6">
        <PageHeader
          title="Response Teams"
          icon="mdi:account-hard-hat"
          subtitle="Standing fire and radiation crews — who holds a place and who waits on the bench"
        >
          <template #actions>
            <template v-if="roster">
              <PageHeaderMetric icon="mdi:account-hard-hat" :value="activeTotal" label="Active" />
              <PageHeaderMetric
                icon="mdi:account-clock-outline"
                :value="reserveTotal"
                label="Reserve"
              />
            </template>
          </template>
        </PageHeader>

        <ResponseTeamsPanel
          :roster="roster"
          :loading="isLoading"
          :error="error"
          :busy-dweller-ids="busyDwellerIdsArray"
          @set-place="handleSetPlace"
        />
      </PageContentRail>
    </VaultPageShell>
  </div>
</template>
