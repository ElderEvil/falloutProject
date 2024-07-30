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
    <h1 v-if="dweller">Chat with {{ dweller.first_name }} {{ dweller.last_name }}</h1>
    <h1 v-else>Loading dweller information...</h1>
    <DwellerChat v-if="dweller" :dweller-id="dwellerId" />
    <p v-else>Please wait while we set up the chat...</p>
  </div>
</template>

<style scoped>
.dweller-chat-page {
  padding: 20px;
}

h1 {
  margin-bottom: 20px;
}
</style>
