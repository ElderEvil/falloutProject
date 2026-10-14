<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useObjectivesStore } from '@/modules/progression/stores/objectives'
import {
  currentObjective,
  objectiveActionPath,
  type Objective,
} from '@/modules/progression/models/objective'
import { Button } from '@/core/components/ui/button'
import { getErrorMessage } from '@/core/utils/errorHandler'
import { useObjectiveClaim } from '@/modules/progression/composables/useObjectiveClaim'
import SidePanel from '@/core/components/common/SidePanel.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import PageHeader from '@/core/components/common/PageHeader.vue'
import { Icon } from '@iconify/vue'
import { Tabs, TabsList, TabsTrigger } from '@/core/components/ui/tabs'
import { ObjectiveCard } from '../components'
import ObjectiveCompleteModal from '../components/ObjectiveCompleteModal.vue'

const route = useRoute()
const objectivesStore = useObjectivesStore()
const { isCollapsed } = useSidePanel()
const activeTab = ref('daily')
const objectiveTabs = [
  { key: 'daily', label: 'Daily', icon: 'mdi:calendar-today' },
  { key: 'weekly', label: 'Weekly', icon: 'mdi:calendar-week' },
  { key: 'achievement', label: 'Achievement', icon: 'mdi:trophy' },
  { key: 'completed', label: 'Completed', icon: 'mdi:check-circle' },
]

const vaultId = computed(() => route.params.id as string)

// Claim + celebration modal (mirrors the quest claim flow)
const { claiming: isClaiming, error: claimError, claim } = useObjectiveClaim(vaultId)
const claimedObjective = ref<Objective | null>(null)
const showClaimModal = ref(false)
const loadError = ref<string | null>(null)

watch(
  vaultId,
  (id) => {
    showClaimModal.value = false
    claimedObjective.value = null
    loadError.value = null
    void objectivesStore.fetchObjectives(id).catch((err) => {
      loadError.value = getErrorMessage(err)
    })
  },
  { immediate: true }
)

const visibleObjectives = computed(() =>
  objectivesStore.objectives.filter((objective) =>
    activeTab.value === 'completed'
      ? objective.is_completed
      : objective.category === activeTab.value && !objective.is_completed
  )
)
const emptyMessage = computed(() =>
  activeTab.value === 'completed'
    ? 'No completed objectives yet'
    : `No ${activeTab.value} objectives available`
)

// The guide remains visible after the Office unlocks the regular objective tabs.
const currentStarterStep = computed(() => {
  const objective = currentObjective(objectivesStore.objectives)
  return objective?.category === 'starter' ? objective : null
})
function handleClaimObjective(objectiveId: string): void {
  void claim(objectiveId, (claimed) => {
    claimedObjective.value = claimed
    showClaimModal.value = claimed !== null
  })
}

function closeClaimModal(): void {
  showClaimModal.value = false
  claimedObjective.value = null
}
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-terminal-green">
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
            <p v-if="loadError || claimError" class="claim-error" role="alert">
              {{ loadError || claimError }}
            </p>

            <!-- Current guide step, retained until its reward is claimed -->
            <div v-if="currentStarterStep" class="next-step-hero">
              <div class="next-step-label">
                <Icon icon="mdi:map-marker-path" class="next-step-icon" />
                NEXT STEP
              </div>
              <ObjectiveCard
                :objective="currentStarterStep"
                class="next-step-card"
                :claiming="isClaiming"
                @claim="handleClaimObjective"
              />
              <Button
                v-if="currentStarterStep.progress < currentStarterStep.total"
                as-child
                class="mt-3 w-full"
                ><RouterLink :to="objectiveActionPath(currentStarterStep, vaultId)"
                  >Continue objective</RouterLink
                ></Button
              >
            </div>

            <Tabs
              v-if="!currentStarterStep || (currentStarterStep.sequence ?? 0) > 7"
              :model-value="activeTab"
              @update:model-value="activeTab = String($event)"
            >
              <TabsList>
                <TabsTrigger v-for="tab in objectiveTabs" :key="tab.key" :value="tab.key">
                  <Icon v-if="tab.icon" :icon="tab.icon" class="mr-2 inline" :ariaHidden="true" />
                  {{ tab.label }}
                </TabsTrigger>
              </TabsList>
              <div class="tab-content">
                <div v-if="visibleObjectives.length === 0" class="empty-state">
                  <p>{{ emptyMessage }}</p>
                </div>
                <div v-else class="objective-grid">
                  <ObjectiveCard
                    v-for="objective in visibleObjectives"
                    :key="objective.id"
                    :objective="objective"
                    :claiming="isClaiming"
                    @claim="handleClaimObjective"
                  />
                </div>
              </div>
            </Tabs>
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
  font-weight: 700; /* Bold font for better readability */
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

/* Next-step hero (starter arc) */
.next-step-hero {
  max-width: 560px;
  margin: 24px auto;
}

.next-step-label {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 1.1rem;
  font-weight: bold;
  color: var(--color-theme-accent);
  text-transform: uppercase;
  letter-spacing: 0.15em;
  margin-bottom: 16px;
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.next-step-icon {
  font-size: 1.4rem;
}

.next-step-card {
  border-width: 3px;
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
