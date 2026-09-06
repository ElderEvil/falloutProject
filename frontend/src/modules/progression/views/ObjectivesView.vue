<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useObjectivesStore } from '@/modules/progression/stores/objectives'
import { useVaultStore } from '@/modules/vault/stores/vault'
import type { Objective } from '@/modules/progression/models/objective'
import SidePanel from '@/core/components/common/SidePanel.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import PageHeader from '@/core/components/common/PageHeader.vue'
import { Icon } from '@iconify/vue'
import UTabs from '@/core/components/ui/UTabs.vue'
import { ObjectiveCard } from '../components'
import ObjectiveCompleteModal from '../components/ObjectiveCompleteModal.vue'

const route = useRoute()
const objectivesStore = useObjectivesStore()
const vaultStore = useVaultStore()
const { isCollapsed } = useSidePanel()
const activeTab = ref('daily')
const objectiveTabs = [
  { key: 'daily', label: 'Daily', icon: 'mdi:calendar-today' },
  { key: 'weekly', label: 'Weekly', icon: 'mdi:calendar-week' },
  { key: 'achievement', label: 'Achievement', icon: 'mdi:trophy' },
  { key: 'completed', label: 'Completed', icon: 'mdi:check-circle' },
]

const vaultId = computed(() => route.params.id as string)
const currentVault = computed(() => (vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null))

onMounted(() => {
  if (vaultId.value) {
    objectivesStore.fetchObjectives(vaultId.value)
  }
})

const completedObjectives = computed(() =>
  objectivesStore.objectives.filter((objective) => objective.is_completed === true)
)
const dailyObjectives = computed(() =>
  objectivesStore.objectives.filter((obj) => obj.category === 'daily' && !obj.is_completed)
)

const weeklyObjectives = computed(() =>
  objectivesStore.objectives.filter((obj) => obj.category === 'weekly' && !obj.is_completed)
)

const achievementObjectives = computed(() =>
  objectivesStore.objectives.filter((obj) => obj.category === 'achievement' && !obj.is_completed)
)

// Claim + celebration modal (mirrors the quest claim flow)
const claimedObjective = ref<Objective | null>(null)
const showClaimModal = ref(false)
const claimError = ref<string | null>(null)

async function handleClaimObjective(objectiveId: string): Promise<void> {
  claimError.value = null
  if (!vaultId.value) return
  try {
    claimedObjective.value = await objectivesStore.completeObjective(vaultId.value, objectiveId)
    showClaimModal.value = claimedObjective.value !== null
  } catch (err) {
    claimError.value = err instanceof Error ? err.message : 'Failed to claim objective reward'
  }
}

function closeClaimModal(): void {
  showClaimModal.value = false
  claimedObjective.value = null
}
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-terminal-green">
    <div class="scanlines"></div>

    <div class="vault-layout">
      <!-- Side Panel -->
      <SidePanel />

      <!-- Main Content Area -->
      <div class="main-content flicker" :class="{ collapsed: isCollapsed }">
        <PageContentRail>
          <div class="objectives-container">
            <PageHeader
              title="Objectives"
              icon="mdi:target"
              subtitle="Complete Vault-Tec directives to earn rewards."
            />
            <p v-if="claimError" class="claim-error" role="alert">{{ claimError }}</p>
            <UTabs v-model="activeTab" :tabs="objectiveTabs">
              <template #default>
                <div v-if="activeTab === 'daily'" class="tab-content">
                  <div v-if="dailyObjectives.length === 0" class="empty-state">
                    <p>No daily objectives available</p>
                  </div>
                  <div v-else class="objective-grid">
                    <ObjectiveCard
                      v-for="objective in dailyObjectives"
                      :key="objective.id"
                      :objective="objective"
                      @claim="handleClaimObjective"
                    />
                  </div>
                </div>

                <div v-if="activeTab === 'weekly'" class="tab-content">
                  <div v-if="weeklyObjectives.length === 0" class="empty-state">
                    <p>No weekly objectives available</p>
                  </div>
                  <div v-else class="objective-grid">
                    <ObjectiveCard
                      v-for="objective in weeklyObjectives"
                      :key="objective.id"
                      :objective="objective"
                      @claim="handleClaimObjective"
                    />
                  </div>
                </div>

                <div v-if="activeTab === 'achievement'" class="tab-content">
                  <div v-if="achievementObjectives.length === 0" class="empty-state">
                    <p>No achievement objectives available</p>
                  </div>
                  <div v-else class="objective-grid">
                    <ObjectiveCard
                      v-for="objective in achievementObjectives"
                      :key="objective.id"
                      :objective="objective"
                      @claim="handleClaimObjective"
                    />
                  </div>
                </div>

                <div v-if="activeTab === 'completed'" class="tab-content">
                  <div v-if="completedObjectives.length === 0" class="empty-state">
                    <p>No completed objectives yet</p>
                  </div>
                  <div v-else class="objective-grid">
                    <ObjectiveCard
                      v-for="objective in completedObjectives"
                      :key="objective.id"
                      :objective="objective"
                    />
                  </div>
                </div>
              </template>
            </UTabs>
          </div>
        </PageContentRail>
      </div>
    </div>

    <ObjectiveCompleteModal
      :objective="claimedObjective"
      :show="showClaimModal"
      @close="closeClaimModal"
      @confirm="closeClaimModal"
    />
  </div>
</template>

<style scoped>
.vault-layout {
  display: flex;
  min-height: 100vh;
}

.main-content {
  flex: 1;
  margin-left: 240px; /* Width of expanded side panel */
  transition: margin-left 0.3s ease;
  font-weight: 600; /* Bold font for better readability */
  letter-spacing: 0.025em; /* Slight letter spacing for clarity */
  line-height: 1.6; /* Better line height for readability */
}

.main-content.collapsed {
  margin-left: 64px;
}

/* Enhanced text styles */
.main-content h1,
.main-content h2,
.main-content h3 {
  font-weight: 700;
}

.main-content p,
.main-content span,
.main-content div {
  text-shadow: 0 0 2px var(--color-theme-glow);
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

.objectives-container {
  width: 100%;
}

.claim-error {
  margin: 12px 0;
  padding: 10px 14px;
  border: 1px solid var(--color-danger, #ff5555);
  border-radius: 4px;
  color: var(--color-danger, #ff5555);
  font-size: 0.9rem;
}

.objective-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 16px;
}

.empty-state {
  text-align: center;
  padding: 48px 24px;
  color: var(--color-gray-500);
  font-size: 1.25rem;
}
</style>
