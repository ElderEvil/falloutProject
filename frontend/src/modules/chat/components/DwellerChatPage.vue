<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useDwellerStore } from '@/stores/dweller'
import { useVaultStore } from '@/stores/vault'
import DwellerChat from './DwellerChat.vue'
import type { Dweller } from '@/models/dweller'

const route = useRoute()
const authStore = useAuthStore()
const dwellerStore = useDwellerStore()
const vaultStore = useVaultStore()

const dwellerId = ref(route.params.id as string)
const dweller = ref<Dweller | null>(null)
const username = ref(authStore.user?.username || 'User')

onMounted(async () => {
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
    }
  } catch (error) {
    console.error('Error fetching dweller data:', error)
    // Handle error (e.g., show error message to user, redirect to error page)
  }
})
</script>

<template>
  <div class="dweller-chat-page">
    <div class="chat-header">
      <div v-if="dweller" class="dweller-info">
        <img
          :src="`http://${dweller.thumbnail_url}`"
          alt="Dweller Thumbnail"
          class="dweller-thumbnail"
        />
        <h1>{{ dweller.first_name }} {{ dweller.last_name }}</h1>
      </div>
      <h1 v-else>Loading dweller information...</h1>
    </div>
    <div class="chat-container">
      <DwellerChat
        v-if="dweller"
        :dweller-id="dwellerId"
        :dweller-name="dweller.first_name"
        :username="username"
        :dweller-avatar="dweller.thumbnail_url ?? undefined"
      />
      <p v-else>Please wait while we set up the chat...</p>
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
  background-color: #0a0a0a;
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
</style>
