<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useObjectivesStore } from '@/modules/progression/stores/objectives'
import {
  currentObjective,
  isObjectiveClaimable,
  isOfficeObjective,
  isRetiredStarter,
  objectiveActionPath,
  type Objective,
} from '@/modules/progression/models/objective'
import { getErrorMessage } from '@/core/utils/errorHandler'
import { useObjectiveClaim } from '@/modules/progression/composables/useObjectiveClaim'
import SidePanel from '@/core/components/common/SidePanel.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import PageHeader from '@/core/components/common/PageHeader.vue'
import PageHeaderMetric from '@/core/components/common/PageHeaderMetric.vue'
import { Icon } from '@iconify/vue'
import { Tabs, TabsList, TabsTrigger } from '@/core/components/ui/tabs'
import { Badge } from '@/core/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/core/components/ui/tooltip'
import { ObjectiveCard } from '../components'
import ObjectiveCompleteModal from '../components/ObjectiveCompleteModal.vue'

const route = useRoute()
const objectivesStore = useObjectivesStore()
const { isCollapsed } = useSidePanel()
const activeTab = ref('daily')
const objectiveTabs = [
  { key: 'starter', label: 'Starter', icon: 'mdi:map-marker-path' },
  { key: 'daily', label: 'Daily', icon: 'mdi:calendar-today' },
  { key: 'weekly', label: 'Weekly', icon: 'mdi:calendar-week' },
  { key: 'achievement', label: 'Achievement', icon: 'mdi:trophy' },
  { key: 'completed', label: 'Completed', icon: 'mdi:check-circle' },
]
const STARTER_TAB = 'starter'

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

// The Starter tab is the permanent claim surface; the rest open on the Office unlock.
const currentStarter = computed(() => {
  const objective = currentObjective(objectivesStore.objectives)
  return objective?.category === 'starter' ? objective : null
})
const officeCompleted = computed(() =>
  objectivesStore.objectives.some(
    (objective) => isOfficeObjective(objective) && objective.is_completed
  )
)
const objectivesUnlocked = computed(() => !currentStarter.value || officeCompleted.value)
const hasOpenStarter = computed(() =>
  objectivesStore.objectives.some(
    (objective) =>
      objective.category === STARTER_TAB &&
      !objective.is_completed &&
      (!isRetiredStarter(objective) || isObjectiveClaimable(objective))
  )
)
const visibleTabs = computed(() => {
  const tabs = objectivesUnlocked.value
    ? objectiveTabs
    : objectiveTabs.filter((tab) => tab.key === STARTER_TAB)
  return tabs.filter((tab) => tab.key !== STARTER_TAB || hasOpenStarter.value)
})
const effectiveTab = computed(() =>
  visibleTabs.value.some((tab) => tab.key === activeTab.value)
    ? activeTab.value
    : (visibleTabs.value[0]?.key ?? STARTER_TAB)
)
const visibleObjectives = computed(() =>
  objectivesStore.objectives.filter((objective) =>
    effectiveTab.value === 'completed'
      ? objective.is_completed
      : objective.category === effectiveTab.value && !objective.is_completed
  )
)
const emptyMessage = computed(() =>
  effectiveTab.value === 'completed'
    ? 'No completed objectives yet'
    : `No ${effectiveTab.value} objectives available`
)

/** Claimable rewards per category, so a tab shows its pending claims at a glance. */
const claimableCounts = computed(() => {
  const counts: Record<string, number> = {}
  for (const objective of objectivesStore.objectives) {
    if (!visibleTabs.value.some((tab) => tab.key === objective.category)) continue
    if (isObjectiveClaimable(objective)) counts[objective.category] = (counts[objective.category] ?? 0) + 1
  }
  return counts
})
const claimableTotal = computed(() =>
  Object.values(claimableCounts.value).reduce((total, count) => total + count, 0)
)
const openObjectivesCount = computed(
  () => objectivesStore.objectives.filter((objective) => !objective.is_completed).length
)
function claimTooltip(count: number): string {
  return `${count} reward${count === 1 ? '' : 's'} ready to claim`
}

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
            >
              <template #help>
                <section>
                  <h2 class="mb-1 flex items-center gap-2 font-semibold text-theme-primary">
                    <Icon icon="mdi:map-marker-path" class="size-4 shrink-0" />
                    Follow the starter arc
                  </h2>
                  <p>
                    The starter steps guide the early vault. Claim the Overseer's Office objective
                    to unlock daily, weekly and achievement objectives.
                  </p>
                </section>
                <section>
                  <h2 class="mb-1 flex items-center gap-2 font-semibold text-theme-primary">
                    <Icon icon="mdi:gift" class="size-4 shrink-0" />
                    Claim finished objectives
                  </h2>
                  <p>
                    Tabs with a count badge hold rewards ready to claim. Claimed objectives move to
                    the Completed tab.
                  </p>
                </section>
              </template>
              <template #actions>
                <PageHeaderMetric
                  icon="mdi:target"
                  :value="openObjectivesCount"
                  label="Open objectives"
                  tooltip="Objectives still waiting to be finished"
                />
                <PageHeaderMetric
                  icon="mdi:treasure-chest"
                  :value="claimableTotal"
                  label="Rewards ready"
                  tooltip="Finished objectives with rewards ready to claim"
                />
              </template>
            </PageHeader>
            <p v-if="loadError || claimError" class="claim-error" role="alert">
              {{ loadError || claimError }}
            </p>

            <div v-if="currentStarter" class="current-step">
              <span class="current-step-label">Next step: {{ currentStarter.challenge }}</span>
              <RouterLink
                class="current-step-action"
                :to="objectiveActionPath(currentStarter, vaultId)"
              >
                Open
              </RouterLink>
            </div>

            <Tabs :model-value="effectiveTab" @update:model-value="activeTab = String($event)">
              <TabsList>
                <template v-for="tab in visibleTabs" :key="tab.key">
                  <TooltipProvider :delay-duration="200">
                    <Tooltip>
                      <TooltipTrigger as-child>
                        <TabsTrigger :value="tab.key">
                          <Icon
                            v-if="tab.icon"
                            :icon="tab.icon"
                            class="mr-2 inline"
                            :ariaHidden="true"
                          />
                          {{ tab.label }}
                          <span
                            v-if="claimableCounts[tab.key]"
                            :aria-label="claimTooltip(claimableCounts[tab.key] ?? 0)"
                          >
                            <Badge
                              variant="outline"
                              class="ml-2 border-0 bg-terminal-background text-theme-primary"
                            >
                              {{ claimableCounts[tab.key] }}
                              <span class="sr-only">claimable</span>
                            </Badge>
                          </span>
                        </TabsTrigger>
                      </TooltipTrigger>
                      <TooltipContent v-if="claimableCounts[tab.key]" side="bottom">
                        {{ claimTooltip(claimableCounts[tab.key] ?? 0) }}
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </template>
              </TabsList>
              <p v-if="!objectivesUnlocked" class="unlock-hint">
                Daily, weekly and achievement objectives unlock once you claim the Overseer's Office
                objective. Rewards already earned stay saved until then.
              </p>
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

.current-step {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 12px 0;
  padding: 10px 14px;
  border: 1px solid var(--color-theme-primary);
  border-radius: 4px;
  font-size: 0.9rem;
}

.current-step-action {
  flex-shrink: 0;
  color: var(--color-theme-primary);
  text-decoration: underline;
  text-underline-offset: 4px;
}

.unlock-hint {
  margin: 16px 0;
  padding: 12px 16px;
  border: 1px dashed var(--color-theme-accent);
  border-radius: 4px;
  color: var(--color-gray-500);
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
