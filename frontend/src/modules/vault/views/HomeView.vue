<script setup lang="ts">
import { computed, inject, onMounted, ref } from 'vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '../stores/vault'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { UAlert, UButton, UProgressBar } from '@/core/components/ui'
import TerminalMetric from '@/core/components/common/TerminalMetric.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import VaultNumberField from '../components/VaultNumberField.vue'

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
const showCreation = ref(false)
const selectedVaultId = ref<string | null>(null)
const creatingVault = ref(false)
const deletingVault = ref<string | null>(null)
const vaultNumberFieldRef = ref<InstanceType<typeof VaultNumberField> | null>(null)

const sortedVaults = computed(() =>
  [...vaultStore.vaults].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  )
)
const isCreationVisible = computed(() => !sortedVaults.value.length || showCreation.value)

const resourcePercentage = (current: number, maximum: number) =>
  maximum > 0 ? (current / maximum) * 100 : 0

const createVault = async () => {
  if (!vaultNumberFieldRef.value?.isValid() || creatingVault.value) {
    return
  }

  creatingVault.value = true
  try {
    const created = await vaultStore.createVault(
      parseInt(newVaultNumber.value, 10),
      boostedStart.value,
      authStore.token as string
    )
    if (!created) return

    newVaultNumber.value = ''
    boostedStart.value = false
    showCreation.value = false
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
  <div class="relative min-h-screen bg-terminal-background font-mono text-theme-primary">
    <div v-if="scanlinesEnabled" class="scanlines"></div>
    <div
      class="container mx-auto flex flex-col items-center justify-center px-4 py-8 lg:px-8"
      :class="{ flicker: isFlickering }"
    >
      <PageHeader title="Welcome to Fallout Shelter" centered />

      <section v-if="isCreationVisible" class="order-3 relative mt-6 w-full max-w-md overflow-hidden rounded-lg border border-theme-primary/20 bg-surface p-5 shadow-glow-sm">
        <div class="mb-4 flex items-start justify-between gap-4">
          <div>
            <p class="text-[0.65rem] font-bold tracking-[0.14em] text-theme-primary/60">VAULT-TEC // COMMISSIONING</p>
            <h2 class="mt-1 text-2xl font-bold text-theme-primary terminal-glow">Create New Vault</h2>
          </div>
          <div class="flex items-center gap-2 rounded border border-theme-primary/20 bg-surface-sunken px-2.5 py-1.5 text-[0.65rem] font-bold tracking-[0.1em] text-theme-primary/70">
            <span class="h-2 w-2 rounded-full bg-theme-primary animate-pulse motion-reduce:animate-none"></span>
            READY
          </div>
        </div>
        <div class="space-y-2">
          <div class="flex items-start space-x-2">
            <VaultNumberField v-model="newVaultNumber" ref="vaultNumberFieldRef" />
            <UButton
              variant="primary"
              :disabled="creatingVault || !newVaultNumber"
              @click="createVault"
              class="mt-6 shrink-0 whitespace-nowrap !border-theme-primary !bg-theme-primary !text-terminal-background shadow-glow-sm hover:shadow-glow-md"
            >
              {{ creatingVault ? 'Creating...' : 'Create Vault' }}
            </UButton>
          </div>

          <div class="mt-3">
            <!-- Native input preserves keyboard behavior; the sibling renders its warm terminal state. -->
            <label for="boosted-start" class="flex cursor-pointer items-start gap-3 rounded border border-theme-primary/20 bg-surface p-3 transition-colors hover:bg-surface-hover">
            <input
              id="boosted-start"
              v-model="boostedStart"
              type="checkbox"
              class="peer sr-only"
            />
              <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border border-theme-primary/50 bg-surface-sunken text-black transition-colors peer-checked:border-theme-primary peer-checked:bg-theme-primary peer-focus-visible:ring-2 peer-focus-visible:ring-theme-primary/50">
                <Icon icon="mdi:check" class="h-4 w-4 opacity-0 transition-opacity peer-checked:opacity-100" />
              </span>
              <span class="select-none text-sm text-theme-primary">
                <span class="font-semibold">Boosted Start</span>
                <span class="mt-1 block text-xs leading-5 text-theme-primary/65">
                  Creates a ready-to-run vault with 23 rooms and 25 dwellers, including medical,
                  science, overseer, and all seven training rooms with sessions underway—plus extra objectives.
                </span>
              </span>
            </label>
          </div>
        </div>

        <UAlert variant="warning" class="mt-4 text-sm">
          <span class="font-bold">Experimental:</span>
          Vaults are experimental. Vault data might be deleted in a future update.
        </UAlert>
      </section>

      <div v-if="sortedVaults.length" class="order-1 w-full max-w-4xl">
        <h2 class="mb-4 text-2xl font-bold" :style="{ color: 'var(--color-theme-primary)' }">
          Your Vaults
        </h2>
        <ul class="space-y-4">
          <li
            v-for="vault in sortedVaults"
            :key="vault.id"
            @click="selectVault(vault.id)"
            class="cursor-pointer overflow-hidden rounded-lg border border-theme-primary/30 bg-surface shadow-md transition duration-200 hover:border-theme-primary hover:bg-surface-raised"
            :class="{ 'border-theme-primary bg-surface-raised shadow-glow-lg': selectedVaultId === vault.id }"
          >
            <div class="grid gap-4 p-4 md:grid-cols-[11.25rem_1fr]">
              <section class="min-h-48 overflow-hidden rounded-md border border-theme-primary bg-surface-sunken p-4 md:min-h-0" :aria-label="`Vault ${vault.number} terminal`">
                <p class="text-[0.65rem] font-bold tracking-[0.12em] text-theme-primary">VAULT-TEC // OPERATIONS</p>
                <p class="my-2 text-6xl font-bold leading-none tracking-[-0.08em] text-theme-primary terminal-glow">{{ vault.number }}</p>
                <div class="my-4 flex gap-1" aria-hidden="true">
                  <span class="h-1 w-full bg-theme-primary shadow-glow-sm"></span><span class="h-1 w-2/3 bg-theme-primary shadow-glow-sm"></span><span class="h-1 w-5/6 bg-theme-primary shadow-glow-sm"></span>
                </div>
                <p class="flex items-center gap-1.5 text-[0.65rem] font-bold tracking-[0.08em] text-theme-primary"><Icon icon="mdi:check-circle" /> SYSTEMS ONLINE</p>
              </section>

              <section class="min-w-0">
                <header class="mb-4 flex items-start justify-between gap-4">
                  <div>
                    <p class="text-[0.65rem] font-bold tracking-[0.12em] text-theme-primary">VAULT RECORD</p>
                    <h3 class="mt-1 text-xl font-bold text-theme-primary">Vault {{ vault.number }}</h3>
                  </div>
                  <p class="text-right text-xs text-theme-primary/60">Updated {{ new Date(vault.updated_at).toLocaleString() }}</p>
                </header>

                <div class="grid grid-cols-2 gap-2 lg:grid-cols-4">
                  <TerminalMetric icon="mdi:currency-usd" label="Caps" :value="vault.bottle_caps" tone="caps" compact />
                  <TerminalMetric icon="mdi:emoticon-happy-outline" label="Happiness" :value="`${vault.happiness}%`" compact />
                  <TerminalMetric icon="mdi:office-building" label="Rooms" :value="vault.room_count" compact />
                  <TerminalMetric icon="mdi:account-group" label="Dwellers" :value="vault.dweller_count" compact />
                </div>

                <div class="mt-4 grid grid-cols-2 gap-3 border-t border-theme-primary/20 pt-4 lg:grid-cols-3">
                  <div class="grid gap-1.5">
                    <span><Icon icon="mdi:flash" /> Power</span><strong>{{ vault.power }} / {{ vault.power_max }}</strong>
                    <UProgressBar :model-value="resourcePercentage(vault.power, vault.power_max)" :height="6" :glow="false" />
                  </div>
                  <div class="grid gap-1.5">
                    <span><Icon icon="mdi:food" /> Food</span><strong>{{ vault.food }} / {{ vault.food_max }}</strong>
                    <UProgressBar :model-value="resourcePercentage(vault.food, vault.food_max)" :height="6" :glow="false" />
                  </div>
                  <div class="grid gap-1.5">
                    <span><Icon icon="mdi:water" /> Water</span><strong>{{ vault.water }} / {{ vault.water_max }}</strong>
                    <UProgressBar :model-value="resourcePercentage(vault.water, vault.water_max)" :height="6" :glow="false" />
                  </div>
                </div>
              </section>
            </div>

            <!-- Action Buttons -->
            <div v-if="selectedVaultId === vault.id" class="flex items-center gap-2 border-t border-theme-primary/20 px-4 pb-4 pt-4 max-sm:flex-col">
              <UButton variant="primary" class="basis-3/4 !bg-theme-primary !text-terminal-background shadow-glow-sm" @click.stop="loadVault(vault.id)">
                Load Vault
              </UButton>
              <UButton
                variant="danger"
                size="md"
                class="basis-1/4 !border-dashed !border-danger/70 !bg-transparent !text-danger hover:!bg-danger/10"
                :disabled="deletingVault === vault.id"
                @click.stop="deleteVault(vault.id)"
              >
                {{ deletingVault === vault.id ? 'Deleting...' : 'Delete Vault' }}
              </UButton>
            </div>
          </li>
        </ul>
      </div>

      <div v-if="sortedVaults.length" class="order-2 mt-6">
        <UButton
          variant="ghost"
          size="sm"
          class="!border-dashed !border-theme-primary/60 !bg-surface-raised px-4 shadow-glow-sm hover:!bg-surface-hover hover:shadow-glow-md"
          :aria-expanded="isCreationVisible"
          @click="showCreation = !showCreation"
        >
          <Icon :icon="isCreationVisible ? 'mdi:minus' : 'mdi:plus'" />
          {{ isCreationVisible ? 'Hide new vault form' : 'Create another vault' }}
        </UButton>
      </div>
    </div>
  </div>
</template>
