<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { UButton, UCard } from '@/core/components/ui'
import { Icon } from '@iconify/vue'
import DwellerChat from './DwellerChat.vue'
import type { Dweller } from '@/modules/dwellers/models/dweller'
import { useAsyncAction } from '@/core/composables/useAsyncAction'
import PageNavigation from '@/core/components/common/PageNavigation.vue'

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
    <div v-if="isLoading" class="loading-state">
      <UCard glow crt padding="lg">
        <div class="loading-content">
          <Icon icon="mdi:loading" class="loading-spinner" />
          <p class="loading-text">Establishing connection to dweller...</p>
          <div class="loading-bars">
            <div class="loading-bar flicker" />
            <div class="loading-bar flicker-slow" />
            <div class="loading-bar flicker-random" />
          </div>
        </div>
      </UCard>
    </div>

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

/* Loading State */
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  padding: 2rem;
}

.loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.5rem;
}

.loading-spinner {
  width: 4rem;
  height: 4rem;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 10px var(--color-theme-glow));
  animation: spin 1.5s linear infinite;
}

.loading-text {
  font-size: 1rem;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.loading-bars {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  width: 100%;
  max-width: 300px;
}

.loading-bar {
  height: 4px;
  background: var(--color-theme-primary);
  border-radius: 2px;
  opacity: 0.3;
}

.loading-bar:nth-child(1) {
  width: 100%;
}

.loading-bar:nth-child(2) {
  width: 75%;
}

.loading-bar:nth-child(3) {
  width: 50%;
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

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
