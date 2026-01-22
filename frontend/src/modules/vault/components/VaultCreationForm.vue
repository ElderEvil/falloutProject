<script setup lang="ts">
import { ref } from 'vue'
import { useVaultOperations } from '../composables/useVaultOperations'
import { useAuthStore } from '@/modules/auth/stores/auth'

const authStore = useAuthStore()
const { createVault } = useVaultOperations()

const newVaultNumber = ref(0)

const handleCreateVault = async () => {
  if (newVaultNumber.value) {
    await createVault(newVaultNumber.value, authStore.token as string)
    newVaultNumber.value = 0
  }
}
</script>

<template>
  <div class="mb-8 w-full max-w-md">
    <h2 class="mb-4 text-2xl font-bold">Create New Vault</h2>
    <form @submit.prevent="handleCreateVault" class="flex space-x-2">
      <input
        v-model="newVaultNumber"
        type="text"
        placeholder="Vault Number"
        class="flex-grow rounded bg-gray-800 p-2 text-terminalGreen focus:outline-none focus:ring-2 focus:ring-terminalGreen"
      />
      <button
        type="submit"
        class="rounded-lg border border-terminalGreen bg-terminalGreen px-4 py-2 font-bold text-terminalBackground transition duration-200 hover:bg-green-400 hover:text-terminalBackground"
      >
        Create
      </button>
    </form>
  </div>
</template>
