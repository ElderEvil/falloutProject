<script setup lang="ts">
import { computed, ref } from 'vue'
import { useVaultStore } from '@/stores/vault'
import { useVaultOperations } from '@/composables/useVaultOperations'
import { useAuthStore } from '@/stores/auth'

const vaultStore = useVaultStore()
const authStore = useAuthStore()
const { selectVault, loadVault, deleteVault } = useVaultOperations()

const selectedVaultId = ref<string | null>(null) // Initialize selectedVaultId within the component

const sortedVaults = computed(() =>
  [...vaultStore.vaults].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  )
)

const handleSelectVault = (id: string) => {
  selectVault(id)
  selectedVaultId.value = id
}

const handleLoadVault = async (id: string) => {
  await loadVault(id, authStore.token as string)
}

const handleDeleteVault = async (id: string) => {
  await deleteVault(id, authStore.token as string)
  if (selectedVaultId.value === id) {
    selectedVaultId.value = null
  }
}
</script>

<template>
  <div v-if="sortedVaults.length" class="w-full max-w-4xl">
    <h2 class="mb-4 text-2xl font-bold">Your Vaults</h2>
    <ul class="space-y-4">
      <li
        v-for="vault in sortedVaults"
        :key="vault.id"
        @click="handleSelectVault(vault.id)"
        class="flex cursor-pointer items-center justify-between rounded-lg p-4 shadow-md transition duration-200"
        :class="
          selectedVaultId === vault.id ? 'border border-terminalGreen bg-green-800' : 'bg-gray-800'
        "
      >
        <div>
          <h3 class="text-xl font-bold">Vault {{ vault.number }}</h3>
          <p>Last Updated: {{ new Date(vault.updated_at).toLocaleString() }}</p>
          <p>Bottle Caps: {{ vault.bottle_caps }}</p>
          <p>Happiness: {{ vault.happiness }}%</p>
          <p>Power: {{ vault.power }} / {{ vault.power_max }}</p>
          <p>Food: {{ vault.food }} / {{ vault.food_max }}</p>
          <p>Water: {{ vault.water }} / {{ vault.water_max }}</p>
          <p>Rooms: {{ vault.room_count }}</p>
          <p>Dwellers: {{ vault.dweller_count }}</p>
        </div>
        <div v-if="selectedVaultId === vault.id" class="flex space-x-2">
          <button
            @click.stop="handleLoadVault(vault.id)"
            class="rounded-lg border border-blue-500 bg-blue-500 px-4 py-2 font-bold text-terminalBackground transition duration-200 hover:bg-blue-400 hover:text-terminalBackground"
          >
            Load
          </button>
          <button
            @click.stop="handleDeleteVault(vault.id)"
            class="rounded-lg border border-red-500 bg-red-500 px-4 py-2 font-bold text-terminalBackground transition duration-200 hover:bg-red-400 hover:text-terminalBackground"
          >
            Delete
          </button>
        </div>
      </li>
    </ul>
  </div>

  <div v-else class="text-center">
    <p class="text-lg">No vaults found. Create your first vault to get started!</p>
  </div>
</template>
