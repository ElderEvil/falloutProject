<script setup lang="ts">
import { computed, inject, onMounted, ref } from 'vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '../stores/vault'
import { useRoomStore } from '@/stores/room'
import { useRouter } from 'vue-router'
import { vaultNumberSchema } from '../schemas/vault'
import { Icon } from '@iconify/vue'

const authStore = useAuthStore()
const vaultStore = useVaultStore()
const roomStore = useRoomStore()
const router = useRouter()

// Inject visual effects
const scanlinesEnabled = inject('scanlines', ref(true))
const isFlickering = inject('isFlickering', ref(true))
const glowClass = inject('glowClass', ref('terminal-glow'))

const newVaultNumber = ref('')
const boostedStart = ref(false)
const selectedVaultId = ref<string | null>(null)
const creatingVault = ref(false)
const deletingVault = ref<string | null>(null)
const vaultNumberError = ref<string | null>(null)

const sortedVaults = computed(() =>
  [...vaultStore.vaults].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  )
)

const validateVaultNumber = () => {
  vaultNumberError.value = null
  if (!newVaultNumber.value) {
    return false
  }

  try {
    const parsed = parseInt(newVaultNumber.value, 10)
    vaultNumberSchema.parse({ number: parsed, boosted: boostedStart.value })
    return true
  } catch (error: any) {
    vaultNumberError.value = error.errors?.[0]?.message || 'Invalid vault number'
    return false
  }
}

const createVault = async () => {
  if (!validateVaultNumber() || creatingVault.value) {
    return
  }

  creatingVault.value = true
  try {
    const number = parseInt(newVaultNumber.value, 10)
    await vaultStore.createVault(number, boostedStart.value, authStore.token as string)
    newVaultNumber.value = ''
    boostedStart.value = false
    vaultNumberError.value = null
    await vaultStore.fetchVaults(authStore.token as string)
  } finally {
    creatingVault.value = false
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
  <div
    class="relative min-h-screen bg-terminalBackground font-mono"
    :style="{ color: 'var(--color-theme-primary)' }"
  >
    <div v-if="scanlinesEnabled" class="scanlines"></div>
    <div
      class="container mx-auto flex flex-col items-center justify-center px-4 py-8 lg:px-8"
      :class="{ flicker: isFlickering }"
    >
      <div class="mb-8 text-center">
        <h1
          class="mb-4 text-4xl font-bold"
          :class="glowClass"
          :style="{ color: 'var(--color-theme-primary)' }"
        >
          Welcome to Fallout Shelter
        </h1>
      </div>

      <div class="mb-8 w-full max-w-md">
        <h2 class="mb-4 text-2xl font-bold" :style="{ color: 'var(--color-theme-primary)' }">
          Create New Vault
        </h2>
        <form @submit.prevent="createVault" class="space-y-2">
          <div class="flex space-x-2">
            <input
              v-model="newVaultNumber"
              type="number"
              placeholder="Vault Number (1-999)"
              min="1"
              max="999"
              @input="validateVaultNumber"
              class="vault-input flex-grow rounded p-2 focus:outline-none focus:ring-2"
              :style="{ color: 'var(--color-theme-primary)' }"
              :class="{ 'ring-2 ring-red-500': vaultNumberError }"
            />
            <button
              type="submit"
              :disabled="creatingVault || !!vaultNumberError"
              class="create-button"
            >
              {{ creatingVault ? 'Creating...' : 'Create' }}
            </button>
          </div>
          <p v-if="vaultNumberError" class="text-sm text-red-500">{{ vaultNumberError }}</p>

          <!-- Boosted Start Option -->
          <div class="mt-3 flex items-start space-x-2">
            <input
              id="boosted-start"
              v-model="boostedStart"
              type="checkbox"
              class="mt-1 h-4 w-4 cursor-pointer"
            />
            <label for="boosted-start" class="cursor-pointer select-none text-sm">
              <span class="font-semibold">Boosted Start</span>
              <p class="mt-1 text-xs text-gray-400">
                Start with extra rooms/dwellers and auto-training. Does not grant admin powers.
              </p>
            </label>
          </div>
        </form>

        <!-- Experimental Warning -->
        <div
          class="mt-4 rounded border border-yellow-600 bg-yellow-900/30 p-3 text-sm"
          :style="{ color: 'var(--color-theme-accent)' }"
        >
          <span class="font-bold text-yellow-500">⚠️ Experimental:</span>
          Vaults are experimental. Vault data might be deleted soon in a future update.
        </div>
      </div>

      <div v-if="sortedVaults.length" class="w-full max-w-4xl">
        <!-- Experimental Warning -->
        <div
          class="mb-4 rounded border border-yellow-600 bg-yellow-900/30 p-3 text-sm"
          :style="{ color: 'var(--color-theme-accent)' }"
        >
          <span class="font-bold text-yellow-500">⚠️ Experimental:</span>
          Vaults are experimental. Vault data might be deleted soon in a future update.
        </div>

        <h2 class="mb-4 text-2xl font-bold" :style="{ color: 'var(--color-theme-primary)' }">
          Your Vaults
        </h2>
        <ul class="space-y-4">
          <li
            v-for="vault in sortedVaults"
            :key="vault.id"
            @click="selectVault(vault.id)"
            class="vault-card rounded-lg shadow-md transition duration-200"
            :class="{ selected: selectedVaultId === vault.id }"
          >
            <div class="vault-content">
              <!-- Screenshot Placeholder -->
              <div class="vault-screenshot">
                <div class="screenshot-placeholder">
                  <Icon icon="mdi:image-outline" class="placeholder-icon" />
                  <span class="placeholder-text">Vault Screenshot</span>
                </div>
              </div>

              <!-- Vault Info -->
              <div class="vault-info">
                <h3 class="text-xl font-bold mb-2" :style="{ color: 'var(--color-theme-primary)' }">
                  Vault {{ vault.number }}
                </h3>
                <div class="vault-stats">
                  <p :style="{ color: 'var(--color-theme-accent)' }">
                    Last Updated: {{ new Date(vault.updated_at).toLocaleString() }}
                  </p>
                  <p :style="{ color: 'var(--color-theme-accent)' }">
                    Bottle Caps: {{ vault.bottle_caps }}
                  </p>
                  <p :style="{ color: 'var(--color-theme-accent)' }">
                    Happiness: {{ vault.happiness }}%
                  </p>
                  <p :style="{ color: 'var(--color-theme-accent)' }">
                    Power: {{ vault.power }} / {{ vault.power_max }}
                  </p>
                  <p :style="{ color: 'var(--color-theme-accent)' }">
                    Food: {{ vault.food }} / {{ vault.food_max }}
                  </p>
                  <p :style="{ color: 'var(--color-theme-accent)' }">
                    Water: {{ vault.water }} / {{ vault.water_max }}
                  </p>
                  <p :style="{ color: 'var(--color-theme-accent)' }">
                    Rooms: {{ vault.room_count }}
                  </p>
                  <p :style="{ color: 'var(--color-theme-accent)' }">
                    Dwellers: {{ vault.dweller_count }}
                  </p>
                </div>
              </div>
            </div>

            <!-- Action Buttons -->
            <div v-if="selectedVaultId === vault.id" class="vault-actions">
              <button @click.stop="loadVault(vault.id)" class="vault-button vault-button-load">
                Load
              </button>
              <button
                @click.stop="deleteVault(vault.id)"
                :disabled="deletingVault === vault.id"
                class="vault-button vault-button-delete"
              >
                {{ deletingVault === vault.id ? 'Deleting...' : 'Delete' }}
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
    </div>
  </div>
</template>

<style scoped>
.vault-input {
  background: rgba(30, 30, 30, 0.8);
  border: 2px solid rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}

.vault-input:focus {
  border-color: var(--color-theme-primary);
  background: rgba(40, 40, 40, 0.9);
  box-shadow: 0 0 10px var(--color-theme-glow);
}

.vault-input::placeholder {
  color: rgba(163, 163, 163, 0.5);
}

.create-button {
  padding: 0.5rem 1rem;
  font-weight: 700;
  border-radius: 0.5rem;
  transition: all 0.2s;
  border: 2px solid var(--color-theme-primary);
  background: rgba(0, 0, 0, 0.8);
  color: var(--color-theme-primary);
}

.create-button:hover:not(:disabled) {
  background: rgba(0, 0, 0, 0.6);
  box-shadow: 0 0 15px var(--color-theme-glow);
}

.create-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.vault-card {
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid transparent;
  cursor: pointer;
  overflow: hidden;
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

.vault-content {
  display: flex;
  gap: 1rem;
  padding: 1rem;
}

.vault-screenshot {
  flex-shrink: 0;
  width: 200px;
  height: 150px;
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  overflow: hidden;
}

.screenshot-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  color: var(--color-theme-accent);
  opacity: 0.5;
}

.placeholder-icon {
  font-size: 3rem;
}

.placeholder-text {
  font-size: 0.75rem;
  text-transform: uppercase;
}

.vault-info {
  flex: 1;
  min-width: 0;
}

.vault-stats {
  font-size: 0.875rem;
}

.vault-stats p {
  margin-bottom: 0.25rem;
}

.vault-actions {
  display: flex;
  gap: 0.5rem;
  padding: 0 1rem 1rem 1rem;
  border-top: 1px solid var(--color-theme-glow);
  padding-top: 1rem;
  margin-top: 0;
}

.vault-button {
  flex: 1;
  padding: 0.75rem 1rem;
  font-weight: 700;
  border-radius: 0.5rem;
  transition: all 0.2s;
  border: 2px solid;
  font-size: 1rem;
}

.vault-button-load {
  background: rgba(0, 0, 0, 0.3);
  border-color: var(--color-theme-primary);
  color: var(--color-theme-primary);
}

.vault-button-load:hover {
  background: rgba(0, 0, 0, 0.5);
  box-shadow: 0 0 10px var(--color-theme-glow);
}

.vault-button-delete {
  background: rgba(239, 68, 68, 0.2);
  border-color: #ef4444;
  color: #ef4444;
}

.vault-button-delete:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.4);
  box-shadow: 0 0 10px #ef4444;
}

.vault-button-delete:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .vault-content {
    flex-direction: column;
  }

  .vault-screenshot {
    width: 100%;
    height: 120px;
  }

  .vault-actions {
    flex-direction: column;
  }
}
</style>
