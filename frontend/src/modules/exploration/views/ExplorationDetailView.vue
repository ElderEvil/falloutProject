<script setup lang="ts">
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { usePolling } from '@/core/composables/usePolling'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { useToast } from '@/core/composables/useToast'
import PageNavigation from '@/core/components/common/PageNavigation.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import SidePanel from '@/core/components/common/SidePanel.vue'
import { useExplorationStore } from '../stores/exploration'
import { useExplorationProgress } from '../composables/useExplorationProgress'
import { useExplorationHealthJourney } from '../composables/useExplorationHealthJourney'
import ExplorationRewardsModal from '../components/ExplorationRewardsModal.vue'
import ExplorerNavbar from '../components/ExplorerNavbar.vue'
import ExplorerSummaryCard from '../components/ExplorerSummaryCard.vue'
import ExplorerStatsGrid from '../components/ExplorerStatsGrid.vue'
import ExplorationEventLog from '../components/ExplorationEventLog.vue'
import ExplorationLootList from '../components/ExplorationLootList.vue'
import ExplorerEquipmentSlots from '../components/ExplorerEquipmentSlots.vue'
import ExplorerActions from '../components/ExplorerActions.vue'
import type { RewardsSummary } from '../stores/exploration'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { filter: dwellerStore } = useDwellerStore()
const explorationStore = useExplorationStore()
const vaultStore = useVaultStore()
const toast = useToast()
const { isCollapsed } = useSidePanel()

const vaultId = computed(() => route.params.id as string)
const explorationId = computed(() => route.params.explorationId as string)
const breadcrumbs = computed(() => [
  { label: 'Vault', to: `/vault/${vaultId.value}` },
  { label: 'Exploration', to: `/vault/${vaultId.value}/exploration` },
  { label: 'Expedition' },
])

const showRewardsModal = ref(false)
const completedExplorationRewards = ref<RewardsSummary | null>(null)
const completedDwellerName = ref('')

const exploration = computed(() => {
  return (
    explorationStore.activeExplorations[explorationId.value] ??
    explorationStore.explorations.find((item) => item.id === explorationId.value)
  )
})

const dweller = computed(() => {
  if (!exploration.value) return null
  return (
    dwellerStore.dwellers.find((d) => d.id === exploration.value!.dweller_id) ??
    dwellerStore.detailedDwellers[exploration.value.dweller_id] ??
    null
  )
})

const detailedDweller = computed(() => {
  if (!exploration.value) return null
  return dwellerStore.detailedDwellers[exploration.value.dweller_id] || null
})

const dwellerName = computed(() => {
  if (!dweller.value) return 'Unknown'
  return `${dweller.value.first_name} ${dweller.value.last_name}`
})

const dwellerImageUrl = computed(() => {
  const currentDweller = dweller.value
  if (!currentDweller || !('image_url' in currentDweller) || typeof currentDweller.image_url !== 'string') {
    return null
  }
  return currentDweller.image_url
})
const dwellerThumbnailUrl = computed(() => dweller.value?.thumbnail_url ?? null)

const allExplorations = computed(() => {
  return Object.values(explorationStore.activeExplorations)
})

const currentIndex = computed(() => {
  return allExplorations.value.findIndex((e) => e.id === explorationId.value)
})

const hasPrevious = computed(() => currentIndex.value > 0)
const hasNext = computed(() => currentIndex.value < allExplorations.value.length - 1)

const navigatePrevious = () => {
  if (hasPrevious.value) {
    const prevExploration = allExplorations.value[currentIndex.value - 1]
    router.push(`/vault/${vaultId.value}/exploration/${prevExploration!.id}`)
  }
}

const navigateNext = () => {
  if (hasNext.value) {
    const nextExploration = allExplorations.value[currentIndex.value + 1]
    router.push(`/vault/${vaultId.value}/exploration/${nextExploration!.id}`)
  }
}

const goBack = () => {
  router.push(`/vault/${vaultId.value}/exploration`)
}

const { progress: progressPercentage, timeRemaining } = useExplorationProgress(() => exploration.value)

// Equipment computed
const weaponName = computed(() => detailedDweller.value?.weapon?.name ?? null)
const outfitName = computed(() => detailedDweller.value?.outfit?.name ?? null)

const { healthJourney, totalDamage, totalHealed, healthTrendPoints } = useExplorationHealthJourney(
  () => exploration.value?.events
)

// Actions
type ExplorationFinishAction = (explorationId: string, token: string) => Promise<{ rewards_summary?: RewardsSummary }>

const finishExploration = async (action: ExplorationFinishAction, errorMessage: string) => {
  if (!authStore.token || !exploration.value) return

  try {
    const result = await action(exploration.value.id, authStore.token)

    if (result?.rewards_summary) {
      explorationStore.acknowledgeSseReward(exploration.value.dweller_id)
      completedExplorationRewards.value = result.rewards_summary
      completedDwellerName.value = dwellerName.value
      showRewardsModal.value = true
    }

    if (vaultId.value) {
      await vaultStore.refreshVault(vaultId.value, authStore.token)
      await dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token)
    }

  } catch (_error) {
    toast.error(errorMessage)
  }
}

const handleCompleteExploration = () =>
  finishExploration(explorationStore.completeExploration, 'Failed to complete exploration')

const handleRecallExploration = () => finishExploration(explorationStore.recallDweller, 'Failed to recall dweller')

const closeRewardsModal = () => {
  showRewardsModal.value = false
  completedExplorationRewards.value = null
  // Navigate back when modal is closed
  goBack()
  completedDwellerName.value = ''
}

const refreshExploration = async () => {
  if (explorationId.value && authStore.token) {
    await explorationStore.fetchExplorationDetails(explorationId.value, authStore.token)
  }
}

// Auto-refresh every 10 seconds. usePolling cleans up with this view scope.
usePolling(refreshExploration, { interval: 10_000, immediate: false })

onMounted(async () => {
  if (vaultId.value && authStore.token) {
    await explorationStore.fetchExplorationsByVault(vaultId.value, authStore.token)

    // Vault list returns the short schema — always fetch the full record (loot/events).
    await explorationStore.fetchExplorationDetails(explorationId.value, authStore.token)

    // Fetch full dweller data for the explorer (includes weapon/outfit)
    if (exploration.value) {
      await dwellerStore.fetchDwellerDetails(exploration.value.dweller_id, authStore.token)
    }

    explorationStore.startSseSubscription(vaultId.value, authStore.token)
  }
})

onUnmounted(() => {
  explorationStore.stopSseSubscription()
})

// Surface rewards when the game loop auto-completes an exploration server-side
watch(
  () => explorationStore.pendingSseRewards,
  (pending) => {
    if (!pending) return
    if (pending.dwellerId !== exploration.value?.dweller_id) return
    if (explorationStore.consumeAcknowledgedSseReward(pending.dwellerId)) {
      explorationStore.clearPendingSseRewards()
      return
    }
    completedExplorationRewards.value = pending.rewards
    completedDwellerName.value = dwellerName.value
    showRewardsModal.value = true
    explorationStore.clearPendingSseRewards()
  }
)

// Watch for exploration completion
watch(
  () => progressPercentage.value,
  (newProgress) => {
    if (newProgress >= 100 && exploration.value?.status === 'active') {
      // Auto-complete when progress reaches 100%
      handleCompleteExploration()
    }
  }
)
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-terminal-green">
    <div class="scanlines"></div>

    <div class="vault-layout">
      <SidePanel />

      <div class="main-content flicker pb-8" :class="{ collapsed: isCollapsed }">
        <PageContentRail>
          <PageNavigation
            back-label="Back to Exploration"
            :back-to="`/vault/${vaultId}/exploration`"
            :breadcrumbs="breadcrumbs"
          />

          <!-- Explorer paging controls -->
          <ExplorerNavbar
            class="mt-4 mb-6"
            :current-index="currentIndex"
            :total="allExplorations.length"
            :has-previous="hasPrevious"
            :has-next="hasNext"
            @previous="navigatePrevious"
            @next="navigateNext"
          />

          <!-- Main Content -->
          <div
            v-if="exploration && dweller"
            class="exploration-detail-content mx-auto w-full max-w-[1200px]"
          >
          <!-- Top Section: Dweller Info & Progress + Stats Grid -->
          <ExplorerSummaryCard
            :dweller-name="dwellerName"
            :dweller-image-url="dwellerImageUrl"
            :dweller-thumbnail-url="dwellerThumbnailUrl"
            :dweller-level="dweller.level"
            :health="dweller.health"
            :max-health="dweller.max_health"
            :radiation="dweller.radiation"
            :progress-percentage="progressPercentage"
            :time-remaining="timeRemaining"
            :exploration-duration="exploration.duration"
          />

          <ExplorerStatsGrid v-if="exploration" :exploration="exploration" />

          <!-- Vitals journey: cumulative health change (not an absolute health history). -->
          <div
            v-if="healthJourney.length > 0"
            class="health-trend mt-4 mb-4 flex flex-wrap items-center gap-4 rounded-lg border-2 border-theme-primary/40 bg-terminal-background p-3 text-sm"
          >
            <span class="flex items-center gap-1.5">
              <Icon icon="mdi:heart-broken" class="h-5 w-5 text-[#ff4444]" />
              <span class="font-bold text-[#ff4444]">-{{ totalDamage }}</span>
              <span class="text-theme-primary/70">damage</span>
            </span>
            <span class="flex items-center gap-1.5">
              <Icon icon="mdi:heart-plus" class="h-5 w-5 text-theme-primary" />
              <span class="font-bold text-theme-primary">+{{ totalHealed }}</span>
              <span class="text-theme-primary/70">healed</span>
            </span>
            <span class="text-theme-primary/50">over {{ healthJourney.length }} events</span>
            <div
              class="health-sparkline-frame ml-auto rounded border border-theme-primary/30 bg-surface-sunken px-2 py-1"
            >
              <svg
                class="h-7 w-[240px] max-w-full overflow-visible"
                viewBox="0 0 120 28"
                role="img"
                aria-label="Cumulative health change during this expedition"
              >
                <polyline :points="healthTrendPoints" fill="none" stroke="var(--color-theme-accent)" stroke-width="2" />
              </svg>
            </div>
          </div>

          <!-- Loot found mid-journey -->
          <ExplorationLootList :items="exploration.loot_collected" />

          <!-- Event Log Section -->
          <ExplorationEventLog
            class="event-log-section mt-4"
            :events="exploration?.events ?? []"
            reverse
          />

          <!-- Equipment Section -->
          <ExplorerEquipmentSlots :weapon-name="weaponName" :outfit-name="outfitName" />

          <!-- Action Buttons -->
          <ExplorerActions
            :can-complete="progressPercentage >= 100"
            @complete="handleCompleteExploration"
            @recall="handleRecallExploration"
          />
          </div>

          <!-- Loading/Error State -->
          <div
            v-else
            class="loading-state flex min-h-[60vh] flex-col items-center justify-center gap-6 text-theme-primary"
          >
            <Icon icon="mdi:loading" class="loading-icon h-20 w-20 animate-spin" />
            <p>Loading exploration data...</p>
          </div>

          <!-- Rewards Modal -->
          <ExplorationRewardsModal
            :show="showRewardsModal"
            :rewards="completedExplorationRewards"
            :dweller-name="completedDwellerName"
            @close="closeRewardsModal"
          />
        </PageContentRail>
        </div>
      </div>
    </div>
</template>
