<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useDwellerStore } from '@/stores/dweller'
import DwellerChat from '@/components/chat/DwellerChat.vue'

const route = useRoute()
const authStore = useAuthStore()
const dwellerStore = useDwellerStore()

const dwellerId = ref(route.params.id as string)
const dweller = ref<Dweller | null>(null)
const username = ref(authStore.user?.username || 'User')

onMounted(async () => {
  try {
    if (!authStore.token) {
      throw new Error('No authentication token available')
    }
    dweller.value = await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token)
    if (!dweller.value) {
      throw new Error('Failed to fetch dweller data')
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
      />
      <p v-else>Please wait while we set up the chat...</p>
    </div>
  </div>
</template>

<style scoped>
.dweller-chat-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding: 20px;
  box-sizing: border-box;
  background-color: #0a0a0a;
  color: #33ff00;
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

.dweller-thumbnail {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  margin-right: 15px;
  border: 2px solid #33ff00;
}

h1 {
  margin: 0;
  font-family: 'VT323', monospace;
}

/* Ensure DwellerChat component takes full height of its container */
:deep(.chat-interface) {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* Style adjustments for Fallout theme */
:deep(*) {
  font-family: 'VT323', monospace;
}

:deep(input),
:deep(button) {
  background-color: #1a1a1a;
  color: #33ff00;
  border: 1px solid #33ff00;
}

:deep(button:hover) {
  background-color: #33ff00;
  color: #0a0a0a;
}
</style>
