<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useVaultStore } from '@/stores/vault'

const authStore = useAuthStore()
const vaultStore = useVaultStore()
const newVaultName = ref('')

const sortedVaults = computed(() => {
  return [...vaultStore.vaults].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
})

const createVault = async () => {
  if (newVaultName.value.trim()) {
    await vaultStore.createVault(newVaultName.value.trim(), authStore.token as string)
    newVaultName.value = ''
  }
}

const deleteVault = async (id: string) => {
  if (confirm('Are you sure you want to delete this vault?')) {
    await vaultStore.deleteVault(id, authStore.token as string)
  }
}

onMounted(async () => {
  if (authStore.isAuthenticated && !vaultStore.vaults.length) {
    await vaultStore.fetchVaults(authStore.token as string)
  }
})
</script>

<template>
  <div class="min-h-screen flex flex-col bg-gray-900 text-white">
    <!-- Main Content -->
    <div class="flex-grow flex flex-col items-center justify-center p-4">
      <div class="text-center mb-8">
        <h1 class="text-4xl font-bold text-green-500 mb-4">Welcome to Fallout Shelter</h1>
        <p class="text-lg">You are logged in as:</p>
        <p class="text-lg font-bold">{{ authStore.user?.email }}</p>
      </div>
      <div class="mb-8 w-full max-w-md">
        <h2 class="text-2xl font-bold mb-4">Create New Vault</h2>
        <form @submit.prevent="createVault" class="flex space-x-2">
          <input v-model="newVaultName" type="text" placeholder="Vault Name" class="p-2 rounded bg-gray-700 text-white flex-grow focus:outline-none focus:ring-2 focus:ring-green-500">
          <button type="submit" class="py-2 px-4 bg-green-500 hover:bg-green-400 text-white font-bold rounded">Create</button>
        </form>
      </div>
      <div v-if="sortedVaults.length" class="w-full max-w-4xl">
        <h2 class="text-2xl font-bold mb-4">Your Vaults</h2>
        <ul class="space-y-4">
          <li v-for="vault in sortedVaults" :key="vault.id" class="p-4 bg-gray-800 rounded-lg shadow-md flex justify-between items-center">
            <div>
              <h3 class="text-xl font-bold">Vault {{ vault.name }}</h3>
              <p>Last Updated: {{ new Date(vault.updated_at).toLocaleString() }}</p>
              <p>Bottle Caps: {{ vault.bottle_caps }}</p>
              <p>Happiness: {{ vault.happiness }}%</p>
              <p>Power: {{ vault.power }} / {{ vault.power_max }}</p>
              <p>Food: {{ vault.food }} / {{ vault.food_max }}</p>
              <p>Water: {{ vault.water }} / {{ vault.water_max }}</p>
            </div>
            <button @click="deleteVault(vault.id)" class="py-2 px-4 bg-red-500 hover:bg-red-400 text-white font-bold rounded">Delete</button>
          </li>
        </ul>
      </div>
      <div v-else class="text-center">
        <p class="text-lg">No vaults found. Create your first vault to get started!</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Scoped styles here if needed */
</style>
