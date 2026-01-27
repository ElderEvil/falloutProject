<script setup lang="ts">
import { computed, ref } from 'vue'
import { useVaultStore } from '../stores/vault'
import { useVaultOperations } from '../composables/useVaultOperations'
import { useAuthStore } from '@/modules/auth/stores/auth'

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
    <h2 class="mb-4 text-2xl font-bold" :style="{ color: 'var(--color-theme-primary)' }">
      Your Vaults
    </h2>
    <ul class="space-y-4">
      <li
        v-for="vault in sortedVaults"
        :key="vault.id"
        @click="handleSelectVault(vault.id)"
        class="vault-card flex cursor-pointer items-center justify-between rounded-lg p-4 shadow-md transition duration-200"
        :class="{ selected: selectedVaultId === vault.id }"
      >
        <div class="vault-info">
          <h3 class="text-xl font-bold" :style="{ color: 'var(--color-theme-primary)' }">
            Vault {{ vault.number }}
          </h3>
          <p :style="{ color: 'var(--color-theme-accent)' }">
            Last Updated: {{ new Date(vault.updated_at).toLocaleString() }}
          </p>
          <p :style="{ color: 'var(--color-theme-accent)' }">
            Bottle Caps: {{ vault.bottle_caps }}
          </p>
          <p :style="{ color: 'var(--color-theme-accent)' }">Happiness: {{ vault.happiness }}%</p>
          <p :style="{ color: 'var(--color-theme-accent)' }">
            Power: {{ vault.power }} / {{ vault.power_max }}
          </p>
          <p :style="{ color: 'var(--color-theme-accent)' }">
            Food: {{ vault.food }} / {{ vault.food_max }}
          </p>
          <p :style="{ color: 'var(--color-theme-accent)' }">
            Water: {{ vault.water }} / {{ vault.water_max }}
          </p>
          <p :style="{ color: 'var(--color-theme-accent)' }">Rooms: {{ vault.room_count }}</p>
          <p :style="{ color: 'var(--color-theme-accent)' }">Dwellers: {{ vault.dweller_count }}</p>
        </div>
        <div v-if="selectedVaultId === vault.id" class="flex space-x-2">
          <button @click.stop="handleLoadVault(vault.id)" class="vault-button vault-button-load">
            Load
          </button>
          <button
            @click.stop="handleDeleteVault(vault.id)"
            class="vault-button vault-button-delete"
          >
            Delete
          </button>
        </div>
      </li>
    </ul>
  </div>

  <div v-else class="text-center">
    <p class="text-lg" :style="{ color: 'var(--color-theme-primary)' }">
      No vaults found. Create your first vault to get started!
    </p>
  </div>
</template>

<style scoped>
.vault-card {
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid transparent;
}

.vault-card:hover {
  background: rgba(0, 0, 0, 0.4);
  border-color: var(--color-theme-glow);
}

.vault-card.selected {
  border-color: var(--color-theme-primary);
  background: rgba(0, 0, 0, 0.5);
  box-shadow: 0 0 20px var(--color-theme-glow);
}

.vault-button {
  padding: 0.5rem 1rem;
  font-weight: 700;
  border-radius: 0.5rem;
  transition: all 0.2s;
  border: 2px solid;
}

.vault-button-load {
  background: rgba(59, 130, 246, 0.2);
  border-color: #3b82f6;
  color: #3b82f6;
}

.vault-button-load:hover {
  background: rgba(59, 130, 246, 0.4);
  box-shadow: 0 0 10px #3b82f6;
}

.vault-button-delete {
  background: rgba(239, 68, 68, 0.2);
  border-color: #ef4444;
  color: #ef4444;
}

.vault-button-delete:hover {
  background: rgba(239, 68, 68, 0.4);
  box-shadow: 0 0 10px #ef4444;
}
</style>
