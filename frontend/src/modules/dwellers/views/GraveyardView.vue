<script setup lang="ts">
/**
 * GraveyardView - Display permanently dead dwellers
 * @component
 */
import { computed, inject, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useDwellerStore } from '../stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useSidePanel } from '@/core/composables/useSidePanel'
import SidePanel from '@/core/components/common/SidePanel.vue'
import { UButton, UCard } from '@/core/components/ui'
import { DeadDwellerCard } from '../components/death'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const dwellerStore = useDwellerStore()
const vaultStore = useVaultStore()
const { isCollapsed } = useSidePanel()
const scanlinesEnabled = inject('scanlines', ref(true))

const vaultId = computed(() => route.params.id as string)
const currentVault = computed(() => vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null)

onMounted(async () => {
  if (authStore.isAuthenticated && vaultId.value) {
    await dwellerStore.fetchGraveyard(vaultId.value, authStore.token as string)
  }
})

const goBack = () => {
  router.push(`/vault/${vaultId.value}/dwellers`)
}

const viewDwellerDetails = (dwellerId: string) => {
  router.push(`/vault/${vaultId.value}/dwellers/${dwellerId}`)
}
</script>

<template>
  <div class="relative min-h-screen bg-terminalBackground font-mono text-terminalGreen">
    <div v-if="scanlinesEnabled" class="scanlines"></div>

    <div class="vault-layout">
      <!-- Side Panel -->
      <SidePanel />

      <!-- Main Content Area -->
      <div class="main-content flicker" :class="{ collapsed: isCollapsed }">
        <div class="container mx-auto flex flex-col items-center justify-center px-4 py-8 lg:px-8">
          <!-- Header -->
          <div class="w-full mb-8">
            <UButton @click="goBack" variant="ghost" size="sm" class="mb-4">
              <Icon icon="mdi:arrow-left" class="h-5 w-5 mr-2" />
              Back to Dwellers
            </UButton>

            <div class="flex items-center gap-4">
              <Icon icon="mdi:grave-stone" class="h-10 w-10 text-gray-500" />
              <div>
                <h1 class="text-4xl font-bold text-theme-primary">
                  {{ currentVault ? `Vault ${currentVault.number}` : '' }} Graveyard
                </h1>
                <p class="text-gray-400 mt-1">Memorial for permanently deceased dwellers</p>
              </div>
            </div>
          </div>

          <!-- Loading State -->
          <div v-if="dwellerStore.isDeadLoading" class="w-full text-center py-12">
            <Icon icon="mdi:loading" class="h-12 w-12 animate-spin text-theme-primary mx-auto" />
            <p class="mt-4 text-theme-primary/60">Loading graveyard records...</p>
          </div>

          <!-- Empty State -->
          <UCard
            v-else-if="dwellerStore.graveyardDwellers.length === 0"
            class="w-full max-w-lg text-center"
            glow
            crt
          >
            <div class="py-8 px-4">
              <Icon icon="mdi:emoticon-happy" class="h-16 w-16 text-theme-primary/40 mx-auto mb-4" />
              <h3 class="text-xl font-bold text-theme-primary mb-2">No Permanent Casualties</h3>
              <p class="text-theme-primary/60 text-sm">
                The graveyard is empty. All deceased dwellers are still within the revival window.
              </p>
            </div>
          </UCard>

          <!-- Graveyard Grid -->
          <div v-else class="w-full graveyard-grid">
            <DeadDwellerCard
              v-for="dweller in dwellerStore.graveyardDwellers"
              :key="dweller.id"
              :dweller="dweller"
              @view-details="viewDwellerDetails"
            />
          </div>

          <!-- Summary Footer -->
          <div v-if="dwellerStore.graveyardDwellers.length > 0" class="w-full mt-8 text-center">
            <p class="text-xs text-gray-500 font-mono">
              {{ dwellerStore.graveyardDwellers.length }} soul{{ dwellerStore.graveyardDwellers.length !== 1 ? 's' : '' }} laid to rest
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.vault-layout {
  display: flex;
  min-height: 100vh;
}

.main-content {
  flex: 1;
  margin-left: 240px;
  transition: margin-left 0.3s ease;
  font-weight: 600;
  letter-spacing: 0.025em;
  line-height: 1.6;
}

.main-content.collapsed {
  margin-left: 64px;
}

.main-content h1,
.main-content h2,
.main-content h3 {
  font-weight: 700;
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.graveyard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1.5rem;
  width: 100%;
}

@media (max-width: 640px) {
  .graveyard-grid {
    grid-template-columns: 1fr;
    gap: 1rem;
  }
}

.scanlines {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0.1) 50%, transparent 50%);
  background-size: 100% 2px;
  pointer-events: none;
}
</style>
