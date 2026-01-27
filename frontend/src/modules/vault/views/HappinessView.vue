<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useVaultStore } from '../stores/vault'
import { useDwellerStore } from '@/stores/dweller'
import { useIncidentStore } from '@/stores/incident'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useSidePanel } from '@/core/composables/useSidePanel'
import SidePanel from '@/core/components/common/SidePanel.vue'
import HappinessDashboard from '../components/HappinessDashboard.vue'
import { happinessService } from '@/services/happinessService'
import { Icon } from '@iconify/vue'

const { isCollapsed } = useSidePanel()
const route = useRoute()
const router = useRouter()
const vaultStore = useVaultStore()
const dwellerStore = useDwellerStore()
const incidentStore = useIncidentStore()
const authStore = useAuthStore()

const vaultId = computed(() => route.params.id as string)
const currentVault = computed(() => (vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null))
const isLoading = ref(true)
const errorMessage = ref<string | null>(null)

const happinessDashboardData = computed(() => {
  if (!currentVault.value) return null

  const allDwellers = dwellerStore.dwellers
  const distribution = happinessService.calculateDistribution(allDwellers)
  const activeIncidents = incidentStore.activeIncidents

  // Count idle dwellers
  const idleDwellers = allDwellers.filter((d) => d.status === 'idle')

  // Count low resource types
  const lowResourceCount = [
    currentVault.value.power / currentVault.value.power_max < 0.3,
    currentVault.value.food / currentVault.value.food_max < 0.3,
    currentVault.value.water / currentVault.value.water_max < 0.3,
  ].filter(Boolean).length

  return {
    vaultHappiness: currentVault.value.happiness || 0,
    dwellerCount: currentVault.value.dweller_count || 0,
    distribution,
    idleDwellerCount: idleDwellers.length,
    activeIncidentCount: activeIncidents.length,
    lowResourceCount,
    radioHappinessMode: currentVault.value.radio_mode === 'happiness',
  }
})

const loadData = async () => {
  if (!vaultId.value || !authStore.token) {
    errorMessage.value = 'No vault ID or authentication token'
    isLoading.value = false
    return
  }

  try {
    isLoading.value = true
    errorMessage.value = null

    // Load vault data
    await vaultStore.refreshVault(vaultId.value, authStore.token)

    // Load dwellers for this specific vault
    await dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token)

    // Load incidents
    await incidentStore.fetchIncidents(vaultId.value, authStore.token)
  } catch (error) {
    console.error('Failed to load happiness data:', error)
    errorMessage.value = 'Failed to load vault happiness data'
  } finally {
    isLoading.value = false
  }
}

const handleAssignIdle = () => {
  router.push(`/vault/${vaultId.value}/dwellers?filter=idle`)
}

const handleActivateRadio = () => {
  router.push(`/vault/${vaultId.value}/radio`)
}

const handleViewLowHappiness = () => {
  router.push(`/vault/${vaultId.value}/dwellers?sortBy=happiness&order=asc`)
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="happiness-view">
    <!-- Side Panel -->
    <SidePanel />

    <!-- Main Content -->
    <div class="main-content" :class="{ collapsed: isCollapsed }">
      <div class="container mx-auto px-4 py-6">
        <!-- Header -->
        <div class="header-section">
          <h1 class="page-title" :style="{ color: 'var(--color-theme-primary)' }">
            <Icon icon="mdi:emoticon-happy-outline" class="title-icon" />
            VAULT HAPPINESS
          </h1>
        </div>

        <!-- Loading State -->
        <div v-if="isLoading" class="loading-state">
          <Icon icon="mdi:loading" class="loading-icon animate-spin" />
          <p class="loading-text">Loading happiness data...</p>
        </div>

        <!-- Error State -->
        <div v-else-if="errorMessage" class="error-state">
          <Icon icon="mdi:alert-circle" class="error-icon" />
          <h3 class="error-title">Error Loading Data</h3>
          <p class="error-message">{{ errorMessage }}</p>
          <button @click="loadData" class="retry-button">
            <Icon icon="mdi:refresh" class="mr-2" />
            Retry
          </button>
        </div>

        <!-- Dashboard -->
        <div v-else-if="happinessDashboardData" class="dashboard-container">
          <HappinessDashboard
            :vaultHappiness="happinessDashboardData.vaultHappiness"
            :dwellerCount="happinessDashboardData.dwellerCount"
            :distribution="happinessDashboardData.distribution"
            :idleDwellerCount="happinessDashboardData.idleDwellerCount"
            :activeIncidentCount="happinessDashboardData.activeIncidentCount"
            :lowResourceCount="happinessDashboardData.lowResourceCount"
            :radioHappinessMode="happinessDashboardData.radioHappinessMode"
            @assign-idle="handleAssignIdle"
            @activate-radio="handleActivateRadio"
            @view-low-happiness="handleViewLowHappiness"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.happiness-view {
  display: flex;
  min-height: 100vh;
  background: var(--color-terminal-background, #0a0a0a);
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
}

.main-content {
  flex: 1;
  margin-left: 240px; /* Width of expanded side panel */
  transition: margin-left 0.3s ease;
}

.main-content.collapsed {
  margin-left: 64px;
}

.container {
  max-width: 1200px;
}

/* Header */
.header-section {
  margin-bottom: 1.5rem;
  text-align: center;
}

.page-title {
  font-size: 1.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  text-shadow: 0 0 20px var(--color-theme-glow);
}

.title-icon {
  font-size: 2rem;
  filter: drop-shadow(0 0 10px var(--color-theme-glow));
}

/* Loading State */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem;
  gap: 1rem;
}

.loading-icon {
  font-size: 4rem;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 10px var(--color-theme-glow));
}

.loading-text {
  font-size: 1.25rem;
  color: var(--color-theme-primary);
}

/* Error State */
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem;
  background: rgba(239, 68, 68, 0.1);
  border: 2px solid #ef4444;
  border-radius: 0.5rem;
  gap: 1rem;
}

.error-icon {
  font-size: 4rem;
  color: #ef4444;
}

.error-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: #ef4444;
  text-transform: uppercase;
}

.error-message {
  color: #fca5a5;
}

.retry-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 1rem;
  padding: 0.75rem 1.5rem;
  background: transparent;
  border: 2px solid var(--color-theme-primary);
  border-radius: 0.25rem;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
  font-weight: 600;
  text-transform: uppercase;
  cursor: pointer;
  transition: all 0.2s;
}

.retry-button:hover {
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.2);
  box-shadow: 0 0 15px var(--color-theme-glow);
}

/* Dashboard */
.dashboard-container {
  max-height: calc(100vh - 200px);
  overflow-y: auto;
}

/* Responsive */
@media (max-width: 768px) {
  .page-title {
    font-size: 1.75rem;
  }

  .title-icon {
    font-size: 2rem;
  }

  .dashboard-container {
    gap: 1.5rem;
  }
}
</style>
