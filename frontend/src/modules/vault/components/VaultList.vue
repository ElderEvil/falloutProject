<script setup lang="ts">
import { computed, ref } from 'vue'
import { useVaultStore } from '../stores/vault'
import { useVaultOperations } from '../composables/useVaultOperations'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { Button } from '@/core/components/ui/button'

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
    <h2 class="mb-4 text-2xl font-bold text-theme-primary">
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
          <h3 class="text-xl font-bold text-theme-primary">
            Vault {{ vault.number }}
          </h3>
          <p class="text-theme-accent">
            Last Updated: {{ new Date(vault.updated_at).toLocaleString() }}
          </p>
          <p class="text-theme-accent">
            Bottle Caps: {{ vault.bottle_caps }}
          </p>
          <p class="text-theme-accent">Happiness: {{ vault.happiness }}%</p>
          <p class="text-theme-accent">
            Power: {{ vault.power }} / {{ vault.power_max }}
          </p>
          <p class="text-theme-accent">
            Food: {{ vault.food }} / {{ vault.food_max }}
          </p>
          <p class="text-theme-accent">
            Water: {{ vault.water }} / {{ vault.water_max }}
          </p>
          <p class="text-theme-accent">Rooms: {{ vault.room_count }}</p>
          <p class="text-theme-accent">Dwellers: {{ vault.dweller_count }}</p>
        </div>
        <div v-if="selectedVaultId === vault.id" class="flex space-x-2">
          <Button
            variant="outline"
            size="sm"
            class="border-2 border-info bg-info/20 text-info hover:bg-info/40 hover:text-info"
            @click.stop="handleLoadVault(vault.id)"
          >
            Load
          </Button>
          <Button
            variant="outline"
            size="sm"
            class="border-2 border-danger bg-danger/20 text-danger hover:bg-danger/40 hover:text-danger"
            @click.stop="handleDeleteVault(vault.id)"
          >
            Delete
          </Button>
        </div>
      </li>
    </ul>
  </div>

  <div v-else class="text-center">
    <p class="text-lg text-theme-primary">
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
</style>
