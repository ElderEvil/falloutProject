<script setup lang="ts">
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { getDwellerDisplayName } from '@/modules/dwellers/models/dweller'
import { usePolling } from '@/core/composables/usePolling'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { useSound } from '@/core/composables/useSound'
import PageNavigation from '@/core/components/common/PageNavigation.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import SidePanel from '@/core/components/common/SidePanel.vue'
import { useExplorationStore } from '../stores/exploration'
import { useExpeditionSiteStore } from '../stores/expeditionSite'
import { useExplorationProgress } from '../composables/useExplorationProgress'
import { useExplorationFinish } from '../composables/useExplorationFinish'
import ExplorationRewardsModal from '../components/ExplorationRewardsModal.vue'
import ExpeditionSiteModal from '../components/ExpeditionSiteModal.vue'
import ExplorerNavbar from '../components/ExplorerNavbar.vue'
import ExplorerSummaryCard from '../components/ExplorerSummaryCard.vue'
import ExplorerStatsGrid from '../components/ExplorerStatsGrid.vue'
import ExplorationEventLog from '../components/ExplorationEventLog.vue'
import ExplorationLootList from '../components/ExplorationLootList.vue'
import ExplorerEquipmentSlots from '../components/ExplorerEquipmentSlots.vue'
import ExplorerActions from '../components/ExplorerActions.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { filter: dwellerStore } = useDwellerStore()
const explorationStore = useExplorationStore()
const siteStore = useExpeditionSiteStore()
const { isCollapsed } = useSidePanel()
const { playMusic } = useSound()

const showSiteModal = ref(false)

const vaultId = computed(() => route.params.id as string)
const explorationId = computed(() => route.params.explorationId as string)
const breadcrumbs = computed(() => [
  { label: 'Vault', to: `/vault/${vaultId.value}` },
  { label: 'Exploration', to: `/vault/${vaultId.value}/exploration` },
  { label: 'Expedition' },
])

const {
  showRewardsModal,
  completedExplorationRewards,
  completedDwellerName,
  completedExplorationId,
  rewardsDirty,
  openRewards,
  resetRewards,
  refreshIfDirty,
  finishExploration: runExplorationFinish,
} = useExplorationFinish(vaultId)

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

const dwellerName = computed(() => getDwellerDisplayName(dweller.value) || 'Dweller')

const dwellerImageUrl = computed(() => {
  const currentDweller = dweller.value
  if (
    !currentDweller ||
    !('image_url' in currentDweller) ||
    typeof currentDweller.image_url !== 'string'
  ) {
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

const {
  progress: progressPercentage,
  timeRemaining,
  isReturning,
  isReady,
  canRecall,
} = useExplorationProgress(() => exploration.value)

// Seconds left on the exploration clock, for the site modal's expiry chip.
const timeRemainingSeconds = computed(() => {
  const exp = exploration.value
  if (!exp || exp.status !== 'active') return undefined
  const remaining = exp.duration * 3600 * (1 - progressPercentage.value / 100)
  return Math.max(0, Math.round(remaining))
})

// Equipment computed
const weaponName = computed(() => detailedDweller.value?.weapon?.name ?? null)
const outfitName = computed(() => detailedDweller.value?.outfit?.name ?? null)
const petName = computed(() => detailedDweller.value?.pet?.name ?? null)

// Actions
const handleCompleteExploration = () => {
  if (!exploration.value) return
  return runExplorationFinish(
    exploration.value.id,
    explorationStore.completeExploration,
    'Failed to complete exploration',
    { dwellerName: dwellerName.value }
  )
}

const handleRecallExploration = () => {
  if (!exploration.value) return
  return runExplorationFinish(
    exploration.value.id,
    explorationStore.recallDweller,
    'Failed to recall dweller',
    { dwellerName: dwellerName.value }
  )
}

const closeRewardsModal = async () => {
  if (!(await refreshIfDirty())) return
  resetRewards()
  goBack()
}

const refreshExploration = async () => {
  if (explorationId.value && authStore.token) {
    await explorationStore.fetchExplorationDetails(explorationId.value, authStore.token)
  }
}

const isActiveExploration = computed(() => exploration.value?.status === 'active')

const siteOptionsLoaded = ref(false)

// Enabled until we have a confirmed empty list; a failed load or an open run
// must never trap the player behind a disabled button.
const canOpenSite = computed(
  () => !siteOptionsLoaded.value || siteStore.availableSites.length > 0 || !!siteStore.room
)

const loadSiteOptions = async () => {
  const requestedId = explorationId.value
  if (!requestedId || !authStore.token || !isActiveExploration.value) return
  try {
    await siteStore.fetchAvailableSites(requestedId)
    if (explorationId.value === requestedId) siteOptionsLoaded.value = true
  } catch {
    // Leave the CTA enabled so opening the modal can surface the error.
  }
}

const handleSiteUpdated = async () => {
  siteOptionsLoaded.value = false
  await refreshExploration()
  await loadSiteOptions()
}

// Reconnect-safe: if a site run is already open server-side, surface the modal
// on mount so the player can pick up where they left off. A null room (no open
// run) is a normal answer, not an error.
const reconnectToSite = async () => {
  if (!explorationId.value || !authStore.token || !isActiveExploration.value) return
  try {
    const currentRoom = await siteStore.fetchCurrentRoom(explorationId.value)
    if (currentRoom?.exploration_id === explorationId.value) showSiteModal.value = true
  } catch {
    // Network failure — the entry CTA still works; don't block the page.
  }
}

// Auto-refresh every 10 seconds. usePolling cleans up with this view scope.
usePolling(refreshExploration, { interval: 10_000, immediate: false })

onMounted(async () => {
  playMusic('exploration')
  if (vaultId.value && authStore.token) {
    await explorationStore.fetchExplorationsByVault(vaultId.value, authStore.token)

    // Vault list returns the short schema — always fetch the full record (loot/events).
    await explorationStore.fetchExplorationDetails(explorationId.value, authStore.token)

    // Fetch full dweller data for the explorer (includes weapon/outfit)
    if (exploration.value) {
      await dwellerStore.fetchDwellerDetails(exploration.value.dweller_id, authStore.token)
    }

    explorationStore.startSseSubscription(vaultId.value, authStore.token)

    await reconnectToSite()
    await loadSiteOptions()
  }
})

onUnmounted(() => {
  playMusic('vaultAmbient')
  explorationStore.stopSseSubscription()
})

// Switching explorers reuses this view (router.push without a remount), so the
// mount-time reconnect never runs again. Re-scope the site store and reconnect.
watch(explorationId, async (id, previousId) => {
  if (!id || id === previousId) return
  siteStore.reset()
  showSiteModal.value = false
  siteOptionsLoaded.value = false
  if (!authStore.token) return
  await explorationStore.fetchExplorationDetails(id, authStore.token)
  if (exploration.value) {
    await dwellerStore.fetchDwellerDetails(exploration.value.dweller_id, authStore.token)
  }
  await reconnectToSite()
  await loadSiteOptions()
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
    openRewards(pending.rewards, dwellerName.value, pending.explorationId ?? '')
    explorationStore.clearPendingSseRewards()
  }
)

// Watch for exploration completion
watch(isReady, (ready) => {
  if (ready) handleCompleteExploration()
})
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-terminal-green">
    <div class="vault-layout">
      <SidePanel />

      <div class="main-content flicker pb-8" :class="{ collapsed: isCollapsed }">
        <PageContentRail width="content">
          <PageNavigation
            back-label="Back to Exploration"
            :back-to="`/vault/${vaultId}/exploration`"
            :breadcrumbs="breadcrumbs"
          >
            <template #actions>
              <ExplorerNavbar
                :current-index="currentIndex"
                :total="allExplorations.length"
                :has-previous="hasPrevious"
                :has-next="hasNext"
                @previous="navigatePrevious"
                @next="navigateNext"
              />
            </template>
          </PageNavigation>

          <!-- Main Content -->
          <div v-if="exploration && dweller" class="exploration-detail-content">
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
              :is-returning="isReturning"
              :exploration="exploration"
              :dweller="detailedDweller ?? dweller"
            />

            <!-- Expedition site entry CTA (active explorations only) -->
            <Button
              v-if="isActiveExploration"
              class="mb-4 w-full"
              size="lg"
              :disabled="!canOpenSite"
              @click="showSiteModal = true"
            >
              <Icon icon="mdi:radio-tower" class="h-5 w-5" />
              Expedition site
            </Button>

            <ExplorerStatsGrid v-if="exploration" :exploration="exploration" />

            <!-- Loot found mid-journey -->
            <ExplorationLootList :items="exploration.loot_collected" />

            <!-- Event Log Section -->
            <ExplorationEventLog
              class="event-log-section mt-4"
              :events="exploration?.events ?? []"
              reverse
            />

            <!-- Equipment Section -->
            <ExplorerEquipmentSlots
              :weapon-name="weaponName"
              :outfit-name="outfitName"
              :pet-name="petName"
              :weapon="detailedDweller?.weapon"
              :outfit="detailedDweller?.outfit"
              :pet="detailedDweller?.pet"
            />

            <!-- Action Buttons -->
            <ExplorerActions
              :can-complete="isReady"
              :can-recall="canRecall"
              :is-returning="isReturning"
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
            :exploration-id="completedExplorationId"
            @close="closeRewardsModal"
            @resolved="rewardsDirty = true"
          />

          <!-- Expedition Site Modal -->
          <ExpeditionSiteModal
            :show="showSiteModal"
            :exploration-id="explorationId"
            :dweller-name="dwellerName"
            :time-remaining-seconds="timeRemainingSeconds"
            :exploration-active="isActiveExploration"
            @close="showSiteModal = false"
            @updated="handleSiteUpdated"
          />
        </PageContentRail>
      </div>
    </div>
  </div>
</template>
