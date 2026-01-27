<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { useRelationshipStore } from '../stores/relationship'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useToast } from '@/core/composables/useToast'
import SidePanel from '@/core/components/common/SidePanel.vue'
import RelationshipList from '../components/relationships/RelationshipList.vue'
import PregnancyTracker from '../components/pregnancy/PregnancyTracker.vue'
import PregnancyDebugPanel from '../components/pregnancy/PregnancyDebugPanel.vue'
import ChildrenList from '../components/relationships/ChildrenList.vue'
import UButton from '@/core/components/ui/UButton.vue'

const route = useRoute()
const { isCollapsed } = useSidePanel()
const relationshipStore = useRelationshipStore()
const dwellerStore = useDwellerStore()
const authStore = useAuthStore()
const toast = useToast()

const vaultId = computed(() => route.params.id as string)
const isLoading = ref(false)
const isProcessing = ref(false)
const activeStage = ref<'forming' | 'partners' | 'pregnancies' | 'children'>('forming')

// Stats
const totalRelationships = computed(() => relationshipStore.relationships.length)
const partnersCount = computed(
  () => relationshipStore.relationships.filter((r) => r.relationship_type === 'partner').length
)
const pregnanciesCount = computed(() => relationshipStore.pregnancies.length)
const childrenCount = computed(
  () => dwellerStore.dwellers.filter((d) => d.age_group === 'child').length
)

// Stages configuration
const stages = computed(() => [
  {
    id: 'forming',
    label: 'Forming',
    icon: 'mdi:account-group',
    count: relationshipStore.relationships.filter((r) => r.relationship_type !== 'partner').length,
  },
  {
    id: 'partners',
    label: 'Partners',
    icon: 'mdi:human-male-female',
    count: partnersCount.value,
  },
  {
    id: 'pregnancies',
    label: 'Pregnancies',
    icon: 'mdi:baby-carriage',
    count: pregnanciesCount.value,
  },
  {
    id: 'children',
    label: 'Children',
    icon: 'mdi:human-child',
    count: childrenCount.value,
  },
])

async function handleQuickPair() {
  if (!vaultId.value) return

  isLoading.value = true
  const result = await relationshipStore.quickPair(vaultId.value)
  isLoading.value = false

  if (result) {
    // Refresh relationships list
    await relationshipStore.fetchVaultRelationships(vaultId.value)
  }
}

async function handleProcessBreeding() {
  if (!vaultId.value) return

  isProcessing.value = true
  try {
    const result = await relationshipStore.processVaultBreeding(vaultId.value)

    if (result) {
      // Show results toast
      const stats = result.stats
      const messages = []
      if (stats.relationships_updated > 0)
        messages.push(`${stats.relationships_updated} relationships updated`)
      if (stats.conceptions > 0) messages.push(`${stats.conceptions} new pregnancy!`)
      if (stats.births > 0) messages.push(`${stats.births} baby born!`)
      if (stats.children_aged > 0) messages.push(`${stats.children_aged} children became adults!`)

      if (messages.length > 0) {
        toast.success(`Processed: ${messages.join(', ')}`)
      } else {
        toast.info('No changes this cycle')
      }

      // Refresh all data
      await Promise.all([
        relationshipStore.fetchVaultRelationships(vaultId.value),
        relationshipStore.fetchVaultPregnancies(vaultId.value),
        dwellerStore.fetchDwellersByVault(vaultId.value, relationshipStore.token!),
      ])
    }
  } catch (error) {
    console.error('Error processing breeding:', error)
  } finally {
    isProcessing.value = false
  }
}

onMounted(async () => {
  if (vaultId.value && authStore.token) {
    await Promise.all([
      relationshipStore.fetchVaultRelationships(vaultId.value),
      relationshipStore.fetchVaultPregnancies(vaultId.value),
      dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token),
    ])
  }
})
</script>

<template>
  <div class="relative min-h-screen bg-terminalBackground font-mono text-terminalGreen">
    <div class="scanlines"></div>

    <!-- Main View -->
    <div class="vault-layout">
      <!-- Side Panel -->
      <SidePanel />

      <!-- Main Content Area -->
      <div class="main-content flicker" :class="{ collapsed: isCollapsed }">
        <div class="container mx-auto px-4 py-8 lg:px-8">
          <div class="max-w-7xl mx-auto">
            <!-- Header -->
            <div class="mb-8">
              <div class="flex items-center justify-between mb-2">
                <h1
                  class="text-4xl font-bold flex items-center gap-3"
                  :style="{ color: 'var(--color-theme-primary)' }"
                >
                  <Icon icon="mdi:heart-multiple" class="text-5xl" />
                  Relationships & Family
                </h1>
                <div class="flex gap-2">
                  <UButton
                    v-if="authStore.isSuperuser"
                    @click="handleProcessBreeding"
                    :disabled="isProcessing"
                    variant="secondary"
                    size="sm"
                  >
                    <Icon
                      icon="mdi:refresh"
                      class="mr-2"
                      :class="{ 'animate-spin': isProcessing }"
                    />
                    {{ isProcessing ? 'Processing...' : 'Process Now' }}
                  </UButton>
                  <UButton
                    v-if="authStore.isSuperuser"
                    @click="handleQuickPair"
                    :disabled="isLoading"
                    variant="primary"
                    size="sm"
                  >
                    <Icon icon="mdi:radioactive" class="mr-2" />
                    {{ isLoading ? 'Matchmaking...' : 'Vault-Tec Matchmaker' }}
                  </UButton>
                </div>
              </div>
              <p class="text-gray-400">
                Manage relationships, pregnancies, and family growth in your vault
              </p>
            </div>

            <!-- Stats Overview -->
            <div class="stats-grid mb-8">
              <div class="stat-card">
                <Icon icon="mdi:heart-multiple" class="stat-icon" />
                <div class="stat-content">
                  <div class="stat-value">{{ totalRelationships }}</div>
                  <div class="stat-label">Total Relationships</div>
                </div>
              </div>
              <div class="stat-card">
                <Icon icon="mdi:human-male-female" class="stat-icon" />
                <div class="stat-content">
                  <div class="stat-value">{{ partnersCount }}</div>
                  <div class="stat-label">Partner Couples</div>
                </div>
              </div>
              <div class="stat-card">
                <Icon icon="mdi:baby-carriage" class="stat-icon" />
                <div class="stat-content">
                  <div class="stat-value">{{ pregnanciesCount }}</div>
                  <div class="stat-label">Active Pregnancies</div>
                </div>
              </div>
              <div class="stat-card">
                <Icon icon="mdi:human-child" class="stat-icon" />
                <div class="stat-content">
                  <div class="stat-value">{{ childrenCount }}</div>
                  <div class="stat-label">Growing Children</div>
                </div>
              </div>
            </div>

            <!-- Stage Tabs -->
            <div class="stages-tabs mb-6">
              <button
                v-for="stage in stages"
                :key="stage.id"
                @click="
                  activeStage = stage.id as 'forming' | 'partners' | 'pregnancies' | 'children'
                "
                :class="['stage-tab', { active: activeStage === stage.id }]"
              >
                <Icon :icon="stage.icon" class="mr-2" />
                {{ stage.label }}
                <span class="stage-count">{{ stage.count }}</span>
              </button>
            </div>

            <!-- Stage Content -->
            <div class="stage-content">
              <!-- Stage 1: All Dwellers / Forming Relationships -->
              <div v-if="activeStage === 'forming'" class="stage-panel">
                <div class="stage-header">
                  <h2 class="text-2xl font-bold">
                    <Icon icon="mdi:account-group" class="inline mr-2" />
                    Forming Relationships
                  </h2>
                  <p class="text-gray-400 mt-1">
                    Dwellers in the same room will gradually increase their affinity. Romance can
                    begin at 70+ affinity.
                  </p>
                </div>
                <RelationshipList v-if="vaultId" :vaultId="vaultId" stageFilter="forming" />
              </div>

              <!-- Stage 2: Partners -->
              <div v-if="activeStage === 'partners'" class="stage-panel">
                <div class="stage-header">
                  <h2 class="text-2xl font-bold">
                    <Icon icon="mdi:human-male-female" class="inline mr-2" />
                    Partner Couples
                  </h2>
                  <p class="text-gray-400 mt-1">
                    Committed partners in living quarters have a chance to conceive (configurable
                    via game settings).
                  </p>
                </div>
                <RelationshipList v-if="vaultId" :vaultId="vaultId" stageFilter="partners" />
              </div>

              <!-- Stage 3: Pregnancies -->
              <div v-if="activeStage === 'pregnancies'" class="stage-panel">
                <div class="stage-header">
                  <h2 class="text-2xl font-bold">
                    <Icon icon="mdi:baby-carriage" class="inline mr-2" />
                    Active Pregnancies
                  </h2>
                  <p class="text-gray-400 mt-1">
                    Pregnancies last 3 hours. Babies inherit traits from both parents.
                  </p>
                </div>
                <PregnancyDebugPanel v-if="vaultId" :vaultId="vaultId" class="mb-6" />
                <PregnancyTracker v-if="vaultId" :vaultId="vaultId" :autoRefresh="true" />
              </div>

              <!-- Stage 4: Children -->
              <div v-if="activeStage === 'children'" class="stage-panel">
                <div class="stage-header">
                  <h2 class="text-2xl font-bold">
                    <Icon icon="mdi:human-child" class="inline mr-2" />
                    Growing Children
                  </h2>
                  <p class="text-gray-400 mt-1">
                    Children grow to adults after 3 hours. They consume resources but cannot work
                    until grown.
                  </p>
                </div>
                <ChildrenList v-if="vaultId" :vaultId="vaultId" />
              </div>
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
}

.main-content.collapsed {
  margin-left: 60px;
}

.scanlines {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(to bottom, rgba(255, 255, 255, 0) 50%, rgba(0, 255, 0, 0.02) 50%);
  background-size: 100% 4px;
  pointer-events: none;
  z-index: 1000;
}

.flicker {
  animation: flicker 0.15s infinite;
}

@keyframes flicker {
  0% {
    opacity: 0.98;
  }
  50% {
    opacity: 1;
  }
  100% {
    opacity: 0.98;
  }
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.5rem;
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid var(--color-theme-glow);
  border-radius: 8px;
  box-shadow: 0 0 10px var(--color-theme-glow);
}

.stat-icon {
  font-size: 2.5rem;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 8px var(--color-theme-glow));
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 8px var(--color-theme-glow);
  line-height: 1;
}

.stat-label {
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
  margin-top: 0.25rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* Stage Tabs */
.stages-tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--color-theme-glow);
  margin-bottom: 1.5rem;
}

.stage-tab {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 1.5rem;
  background: transparent;
  border: none;
  border-bottom: 3px solid transparent;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
  font-weight: 600;
  font-size: 1rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  cursor: pointer;
  transition: all 0.2s;
  opacity: 0.6;
}

.stage-tab:hover:not(.active) {
  opacity: 0.8;
  background: rgba(0, 0, 0, 0.2);
}

.stage-tab.active {
  opacity: 1;
  border-bottom-color: var(--color-theme-primary);
  background: var(--color-theme-glow);
}

.stage-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.5rem;
  height: 1.5rem;
  padding: 0 0.5rem;
  background: var(--color-theme-primary);
  color: black;
  font-size: 0.75rem;
  font-weight: 700;
  margin-left: 0.5rem;
}

/* Stage Content */
.stage-content {
  padding: 2rem 0;
}

.stage-panel {
  animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.stage-header {
  margin-bottom: 2rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--color-theme-glow);
}

.stage-header h2 {
  color: var(--color-theme-primary);
  text-shadow: 0 0 10px var(--color-theme-glow);
}
</style>
