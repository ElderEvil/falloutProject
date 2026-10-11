<script setup lang="ts">
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
          <template #help>
            <section>
              <h2 class="mb-1 flex items-center gap-2 font-semibold text-theme-primary">
                <Icon icon="mdi:shield-star-outline" class="size-4 shrink-0" />
                Earn membership
              </h2>
              <p>
                Dwellers qualify by participating in three matching incidents. Fire and radiation
                teams have separate membership.
              </p>
            </section>
            <section>
              <h2 class="mb-1 flex items-center gap-2 font-semibold text-theme-primary">
                <Icon icon="mdi:alarm-light-outline" class="size-4 shrink-0" />
                Automatic response
              </h2>
              <p>
                Active members automatically answer matching hazards when available. Holding an
                active place does not guarantee a dweller is available to respond.
              </p>
            </section>
            <section>
              <h2 class="mb-1 flex items-center gap-2 font-semibold text-theme-primary">
                <Icon icon="mdi:account-group-outline" class="size-4 shrink-0" />
                Plan your crew
              </h2>
              <p>
                Reserves wait for an active place. Use Bench and Activate to change the roster, and
                open a member’s name to inspect their health and equipment.
              </p>
            </section>
          </template>
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
