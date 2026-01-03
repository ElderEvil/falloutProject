<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDwellerStore } from '@/stores/dweller'
import { useAuthStore } from '@/stores/auth'
import { useVaultStore } from '@/stores/vault'
import { Icon } from '@iconify/vue'
import SidePanel from '@/components/common/SidePanel.vue'
import DwellerCard from '@/components/dwellers/DwellerCard.vue'
import DwellerPanel from '@/components/dwellers/DwellerPanel.vue'
import DwellerStatusBadge from '@/components/dwellers/DwellerStatusBadge.vue'
import UButton from '@/components/ui/UButton.vue'
import { useSidePanel } from '@/composables/useSidePanel'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const dwellerStore = useDwellerStore()
const vaultStore = useVaultStore()
const { isCollapsed } = useSidePanel()

const dwellerId = computed(() => route.params.dwellerId as string)
const vaultId = computed(() => route.params.id as string)
const currentVault = computed(() => vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null)

const loading = ref(false)
const generatingAI = ref(false)

const dweller = computed(() => dwellerStore.detailedDwellers[dwellerId.value])

onMounted(async () => {
  if (authStore.isAuthenticated && dwellerId.value) {
    loading.value = true
    await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token as string)
    loading.value = false
  }
})

const goBack = () => {
  router.push(`/vault/${vaultId.value}/dwellers`)
}

const navigateToChatPage = () => {
  router.push(`/dweller/${dwellerId.value}/chat`)
}

const handleAssign = () => {
  // TODO: Implement assign to room modal
  console.log('Assign to room - coming soon')
}

const handleRecall = () => {
  // TODO: Implement recall from exploration
  console.log('Recall from exploration - coming soon')
}

const generateDwellerInfo = async () => {
  generatingAI.value = true
  try {
    const result = await dwellerStore.generateDwellerInfo(dwellerId.value, authStore.token as string)
    if (result) {
      // Force refresh the detailed dweller data
      await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token as string, true)
    }
  } catch (error) {
    console.error('Error generating info with AI:', error)
  } finally {
    generatingAI.value = false
  }
}

const handleRefresh = async () => {
  await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token as string, true)
}

const usingStimpack = ref(false)
const usingRadaway = ref(false)

const handleUseStimpack = async () => {
  if (!dweller.value || usingStimpack.value) return

  usingStimpack.value = true
  try {
    await dwellerStore.useStimpack(dwellerId.value, authStore.token as string)
    await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token as string, true)
  } catch (error) {
    console.error('Error using stimpack:', error)
  } finally {
    usingStimpack.value = false
  }
}

const handleUseRadaway = async () => {
  if (!dweller.value || usingRadaway.value) return

  usingRadaway.value = true
  try {
    await dwellerStore.useRadaway(dwellerId.value, authStore.token as string)
    await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token as string, true)
  } catch (error) {
    console.error('Error using radaway:', error)
  } finally {
    usingRadaway.value = false
  }
}
</script>

<template>
  <div class="relative min-h-screen bg-terminalBackground font-mono text-terminalGreen">
    <div class="scanlines"></div>

    <div class="vault-layout">
      <!-- Side Panel -->
      <SidePanel />

      <!-- Main Content Area -->
      <div class="main-content flicker" :class="{ collapsed: isCollapsed }">
        <div class="container mx-auto px-4 py-8">
          <!-- Loading State -->
          <div v-if="loading" class="loading-container">
            <Icon icon="mdi:loading" class="loading-icon animate-spin" />
            <p class="loading-text">Loading dweller details...</p>
          </div>

          <!-- Error State -->
          <div v-else-if="!dweller" class="error-container">
            <Icon icon="mdi:alert-circle" class="error-icon" />
            <p class="error-text">Dweller not found</p>
            <UButton @click="goBack" variant="secondary">
              <Icon icon="mdi:arrow-left" class="mr-2" />
              Back to Dwellers
            </UButton>
          </div>

          <!-- Dweller Detail -->
          <div v-else class="dweller-detail">
            <!-- Header -->
            <div class="detail-header">
              <UButton @click="goBack" variant="ghost" size="sm">
                <Icon icon="mdi:arrow-left" class="h-5 w-5 mr-2" />
                Back to Dwellers
              </UButton>

              <div class="header-info">
                <h1 class="dweller-name">
                  {{ dweller.first_name }} {{ dweller.last_name }}
                </h1>
                <DwellerStatusBadge :status="dweller.status" :show-label="true" size="large" />
              </div>
            </div>

            <!-- Two-Column Layout -->
            <div class="detail-layout">
              <!-- Left Column: Dweller Card -->
              <DwellerCard
                :dweller="dweller"
                :image-url="dweller.image_url"
                :loading="generatingAI || usingStimpack || usingRadaway"
                @chat="navigateToChatPage"
                @assign="handleAssign"
                @recall="handleRecall"
                @generate-ai="generateDwellerInfo"
                @use-stimpack="handleUseStimpack"
                @use-radaway="handleUseRadaway"
              />

              <!-- Right Column: Dweller Panel -->
              <DwellerPanel :dweller="dweller" @refresh="handleRefresh" />
            </div>
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
  text-shadow: 0 0 8px rgba(0, 255, 0, 0.5);
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

.loading-container,
.error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  min-height: 400px;
}

.loading-icon,
.error-icon {
  width: 4rem;
  height: 4rem;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 10px var(--color-theme-glow));
}

.loading-text,
.error-text {
  font-size: 1.25rem;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.dweller-detail {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.detail-header {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.header-info {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.dweller-name {
  font-size: 2rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 10px var(--color-theme-glow);
}

.detail-layout {
  display: grid;
  grid-template-columns: 350px 1fr;
  gap: 2rem;
  align-items: start;
}

@media (max-width: 1024px) {
  .detail-layout {
    grid-template-columns: 1fr;
  }
}
</style>
