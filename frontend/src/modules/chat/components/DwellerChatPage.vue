<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { UButton, UCard } from '@/core/components/ui'
import { Icon } from '@iconify/vue'
import DwellerChat from './DwellerChat.vue'
import type { Dweller } from '@/modules/dwellers/models/dweller'
import { normalizeImageUrl } from '@/core/utils/image'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const dwellerStore = useDwellerStore()
const vaultStore = useVaultStore()

const dwellerId = ref(route.params.id as string)
const dweller = ref<Dweller | null>(null)
const isLoading = ref(false)
const username = ref(authStore.user?.username || 'User')

onMounted(async () => {
  isLoading.value = true
  try {
    if (!authStore.token) {
      throw new Error('No authentication token available')
    }
    const result = await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token)
    if (!result) {
      throw new Error('Failed to fetch dweller data')
    }
    dweller.value = result

    // Set active vault ID from dweller's vault for navigation
    if (result.vault?.id) {
      vaultStore.activeVaultId = result.vault.id
      await vaultStore.loadVault(result.vault.id, authStore.token)
    }
  } catch (error) {
    console.error('Error fetching dweller data:', error)
    // Handle error (e.g., show error message to user, redirect to error page)
  } finally {
    isLoading.value = false
  }
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
      <div class="chat-header">
        <UButton
          v-if="dweller?.vault?.id"
          variant="ghost"
          size="sm"
          class="mr-4"
          @click="router.push(`/vault/${dweller.vault.id}/dwellers/${dwellerId}`)"
        >
          <Icon icon="mdi:arrow-left" class="h-5 w-5 mr-1" />
          Back to Dweller
        </UButton>
        <div class="dweller-info">
          <img
            :src="normalizeImageUrl(dweller.thumbnail_url)"
            alt="Dweller Thumbnail"
            class="dweller-thumbnail"
          />
          <h1>{{ dweller.first_name }} {{ dweller.last_name }}</h1>
        </div>
      </div>
      <div class="chat-container">
        <DwellerChat
          :dweller-id="dwellerId"
          :dweller-name="dweller.first_name"
          :username="username"
          :dweller-avatar="dweller.thumbnail_url ?? undefined"
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

.chat-header {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  margin-bottom: 20px;
}

.dweller-info {
  display: flex;
  align-items: center;
}

.dweller-info h1 {
  font-size: 2rem;
  text-shadow: 0 0 10px var(--color-theme-glow);
}

.dweller-thumbnail {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  margin-right: 15px;
  border: 2px solid var(--color-theme-primary);
  box-shadow: 0 0 15px var(--color-theme-glow);
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
