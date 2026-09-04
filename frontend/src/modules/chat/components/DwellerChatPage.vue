<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { UButton } from '@/core/components/ui'
import DwellerChat from './DwellerChat.vue'
import type { Dweller } from '@/modules/dwellers/models/dweller'
import { useAsyncAction } from '@/core/composables/useAsyncAction'
import PageNavigation from '@/core/components/common/PageNavigation.vue'
import TerminalLoadingState from '@/core/components/common/TerminalLoadingState.vue'

const route = useRoute()
const authStore = useAuthStore()
const { filter: dwellerStore } = useDwellerStore()
const vaultStore = useVaultStore()

const dwellerId = ref(route.params.id as string)
const dweller = ref<Dweller | null>(null)
const username = ref(authStore.user?.username || 'User')
const vaultId = computed(() => dweller.value?.vault?.id ?? null)
const breadcrumbs = computed(() => {
  if (!vaultId.value || !dweller.value) return []
  return [
    { label: 'Vault', to: `/vault/${vaultId.value}` },
    { label: 'Dwellers', to: `/vault/${vaultId.value}/dwellers` },
    { label: `${dweller.value.first_name} ${dweller.value.last_name ?? ''}`.trim(), to: `/vault/${vaultId.value}/dwellers/${dwellerId.value}` },
    { label: 'Conversation' },
  ]
})
const { run: runLoadDweller, isLoading } = useAsyncAction(
  async (currentDwellerId: string, token: string) => {
    const result = await dwellerStore.fetchDwellerDetails(currentDwellerId, token)
    if (!result) throw new Error('Failed to fetch dweller data')

    dweller.value = result
    if (result.vault?.id) {
      vaultStore.activeVaultId = result.vault.id
      await vaultStore.loadVault(result.vault.id, token)
    }
    return result
  },
  { context: 'Error fetching dweller data', showToast: false }
)

onMounted(async () => {
  if (authStore.token) await runLoadDweller(dwellerId.value, authStore.token)
})
</script>

<template>
  <div class="dweller-chat-page">
    <!-- Loading State -->
    <TerminalLoadingState v-if="isLoading" full-height message="Establishing connection to dweller..." />

    <!-- Content -->
    <template v-else-if="dweller">
      <PageNavigation
        v-if="vaultId"
        back-label="Back to Dweller"
        :back-to="`/vault/${vaultId}/dwellers/${dwellerId}`"
        :breadcrumbs="breadcrumbs"
      />
      <div class="chat-container">
        <DwellerChat
          :dweller-id="dwellerId"
          :dweller-name="dweller.first_name"
          :username="username"
          :dweller-avatar="dweller.thumbnail_url ?? undefined"
          :vault-id="vaultId"
        />
      </div>
    </template>

    <!-- Empty / No Data State -->
    <div v-else class="empty-state">
      <p>Dweller information unavailable.</p>
    </div>
  </div>
</template>

<style scoped>
.dweller-chat-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  padding: 20px;
  box-sizing: border-box;
  background-color: var(--color-surface-dark);
  color: var(--color-theme-primary);
}

.chat-container {
  flex: 1;
  display: flex;
  justify-content: center;
  max-width: 900px;
  width: 100%;
  margin: 0 auto;
}

/* Empty / No Data State */
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  padding: 2rem;
  color: var(--color-theme-primary);
  opacity: 0.6;
}

</style>
