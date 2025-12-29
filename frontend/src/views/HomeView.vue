<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useVaultStore } from '@/stores/vault'
import { useRoomStore } from '@/stores/room'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const vaultStore = useVaultStore()
const roomStore = useRoomStore()
const router = useRouter()

const newVaultNumber = ref(0)
const selectedVaultId = ref<string | null>(null)
const creatingVault = ref(false)
const deletingVault = ref<string | null>(null)

const sortedVaults = computed(() =>
  [...vaultStore.vaults].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  )
)

const createVault = async () => {
  const number = newVaultNumber.value
  if (number && !creatingVault.value) {
    creatingVault.value = true
    try {
      await vaultStore.createVault(number, authStore.token as string)
      newVaultNumber.value = 0
      await vaultStore.fetchVaults(authStore.token as string)
    } finally {
      creatingVault.value = false
    }
  }
}

const deleteVault = async (id: string) => {
  if (confirm('Are you sure you want to delete this vault?') && !deletingVault.value) {
    deletingVault.value = id
    try {
      await vaultStore.deleteVault(id, authStore.token as string)
      if (selectedVaultId.value === id) {
        selectedVaultId.value = null
      }
      await vaultStore.fetchVaults(authStore.token as string)
    } finally {
      deletingVault.value = null
    }
  }
}

const selectVault = (id: string) => {
  selectedVaultId.value = id
}

const loadVault = async (id: string) => {
  await router.push(`/vault/${id}`)
}

onMounted(async () => {
  if (authStore.isAuthenticated && !vaultStore.vaults.length) {
    await vaultStore.fetchVaults(authStore.token as string)
  }
})
</script>

<template>
  <div class="relative min-h-screen bg-terminalBackground font-mono text-terminalGreen">
    <div class="scanlines"></div>
    <div
      class="flicker container mx-auto flex flex-col items-center justify-center px-4 py-8 lg:px-8"
    >
      <div class="mb-8 text-center">
        <h1 class="mb-4 text-4xl font-bold">Welcome to Fallout Shelter</h1>
      </div>

      <div class="mb-8 w-full max-w-md">
        <h2 class="mb-4 text-2xl font-bold">Create New Vault</h2>
        <form @submit.prevent="createVault" class="flex space-x-2">
          <input
            v-model="newVaultNumber"
            type="text"
            placeholder="Vault Number"
            class="flex-grow rounded bg-gray-800 p-2 text-terminalGreen focus:outline-none focus:ring-2 focus:ring-terminalGreen"
          />
          <button
            type="submit"
            :disabled="creatingVault"
            class="rounded-lg border border-terminalGreen bg-terminalGreen px-4 py-2 font-bold text-terminalBackground transition duration-200 hover:bg-green-400 hover:text-terminalBackground disabled:cursor-not-allowed disabled:opacity-50"
          >
            {{ creatingVault ? 'Creating...' : 'Create' }}
          </button>
        </form>
      </div>

      <div v-if="sortedVaults.length" class="w-full max-w-4xl">
        <h2 class="mb-4 text-2xl font-bold">Your Vaults</h2>
        <ul class="space-y-4">
          <li
            v-for="vault in sortedVaults"
            :key="vault.id"
            @click="selectVault(vault.id)"
            class="flex cursor-pointer items-center justify-between rounded-lg p-4 shadow-md transition duration-200"
            :class="
              selectedVaultId === vault.id
                ? 'border border-terminalGreen bg-green-800'
                : 'bg-gray-800'
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
                @click.stop="loadVault(vault.id)"
                class="rounded-lg border border-blue-500 bg-blue-500 px-4 py-2 font-bold text-terminalBackground transition duration-200 hover:bg-blue-400 hover:text-terminalBackground"
              >
                Load
              </button>
              <button
                @click.stop="deleteVault(vault.id)"
                :disabled="deletingVault === vault.id"
                class="rounded-lg border border-red-500 bg-red-500 px-4 py-2 font-bold text-terminalBackground transition duration-200 hover:bg-red-400 hover:text-terminalBackground disabled:cursor-not-allowed disabled:opacity-50"
              >
                {{ deletingVault === vault.id ? 'Deleting...' : 'Delete' }}
              </button>
            </div>
          </li>
        </ul>
      </div>

      <div v-else class="text-center">
        <p class="text-lg">No vaults found. Create your first vault to get started!</p>
      </div>
    </div>
  </div>
</template>
