<script setup lang="ts">
import { Button } from '@/core/components/ui/button'
import { Icon } from '@iconify/vue'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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
const router = useRouter()
const authStore = useAuthStore()
const vaultId = computed(() => route.params.id as string)

const roster = ref<ContaminationTeamRead | null>(null)

const { run, error: fetchError } = useAsyncAction(
  async (vaultId: string, token: string) => contaminationTeamApi.getRoster(vaultId, token),
  { context: 'Failed to load response teams', showToast: false }
)

const isLoading = ref(false)
const error = ref<string | null>(null)
let loadVersion = 0
async function loadRoster() {
  const id = vaultId.value
  const token = authStore.token
  const version = ++loadVersion
  error.value = null
  if (!id || !token) return
  isLoading.value = true
  const updated = await run(id, token)
  if (version !== loadVersion || id !== vaultId.value || token !== authStore.token) return
  roster.value = updated?.vault_id === id ? updated : null
  error.value = updated ? null : fetchError.value
  isLoading.value = false
}

watch(
  [vaultId, () => authStore.token],
  () => {
    roster.value = null
    isLoading.value = false
    loadRoster()
  },
  { immediate: true }
)

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
  const id = vaultId.value
  const token = authStore.token
  if (!id || !token || isLoading.value || busyDwellerIds.value.size > 0) return
  const version = loadVersion
  busyDwellerIds.value.add(dwellerId)
  try {
    const updated = await runSetPlace(id, team, dwellerId, active, token)
    if (updated && version === loadVersion && id === vaultId.value && token === authStore.token)
      roster.value = updated
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
          subtitle="Plan your standing hazard crews and inspect the dwellers who respond."
        >
          <template #actions>
            <template v-if="roster">
              <PageHeaderMetric
                icon="mdi:account-hard-hat"
                :value="activeTotal"
                label="Active places"
              />
              <PageHeaderMetric
                icon="mdi:account-clock-outline"
                :value="reserveTotal"
                label="Reserve"
              />
            </template>
            <Button
              variant="outline"
              size="sm"
              :disabled="isLoading || busyDwellerIds.size > 0"
              @click="loadRoster"
            >
              <Icon icon="mdi:refresh" class="size-4" />Refresh
            </Button>
            <Button variant="outline" size="sm" @click="router.push(`/vault/${vaultId}`)"
              >View vault incidents</Button
            >
          </template>
        </PageHeader>

        <p v-if="busyDwellerIds.size" role="status" class="text-sm text-theme-primary/70">
          Updating response roster…
        </p>
        <ResponseTeamsPanel
          :roster="roster"
          :loading="isLoading"
          :error="error"
          :busy-dweller-ids="busyDwellerIdsArray"
          @set-place="handleSetPlace"
          @refresh="loadRoster"
          @view-dweller="
            router.push({ name: 'dwellerDetail', params: { id: vaultId, dwellerId: $event } })
          "
        />
      </PageContentRail>
    </VaultPageShell>
  </div>
</template>
