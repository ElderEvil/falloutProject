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
const reportedSiteId = computed(() =>
  typeof route.query.siteId === 'string' ? route.query.siteId : undefined
)

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
    await explorationStore.fetchExplorationDetails(explorationId.value)
  }
}

// Encounters are offered and actionable while the journey is active OR returning;
// only a terminal exploration is close-only recovery.
const isInProgressExploration = computed(
  () => exploration.value?.status === 'active' || exploration.value?.status === 'returning'
)

const siteOptionsLoaded = ref(false)
const siteContextId = ref<string | null>(null)
let explorerLoadVersion = 0

// Enabled until we have a confirmed empty list; a failed load or an open run
// must never trap the player behind a disabled button.
const canOpenSite = computed(
  () => !siteOptionsLoaded.value || siteStore.availableSites.length > 0 || !!siteStore.room
)
const siteCtaReady = computed(() => siteOptionsLoaded.value && canOpenSite.value)

const loadSiteOptions = async () => {
  const requestedId = explorationId.value
  if (!requestedId || !authStore.token || !isInProgressExploration.value) return
  try {
    await siteStore.fetchAvailableSites(requestedId)
    if (explorationId.value === requestedId) siteOptionsLoaded.value = true
  } catch {
    // Leave the CTA enabled so opening the modal can surface the error.
  }
}

// Journey polling/SSE already owns refreshes; update the picker when that snapshot
// gains a report, including when the player is already looking at this explorer.
watch(
  () => exploration.value?.events?.filter((event) => event.event === 'site_found').length ?? 0,
  (count, previous) => {
    if (count > previous && siteContextId.value === explorationId.value) void loadSiteOptions()
  }
)

const handleSiteUpdated = async () => {
  siteOptionsLoaded.value = false
  await refreshExploration()
  await loadSiteOptions()
}

// Mounts and explorer switches share the same reconnect-before-picker ordering.
const initializeExplorer = async (id: string) => {
  const token = authStore.token
  if (!id || !token) return
  const version = ++explorerLoadVersion
  siteContextId.value = null
  const isCurrent = () =>
    version === explorerLoadVersion && explorationId.value === id && authStore.token === token
  await explorationStore.fetchExplorationDetails(id)
  if (!isCurrent()) return
  if (exploration.value) {
    await dwellerStore.fetchDwellerDetails(exploration.value.dweller_id, token)
  }
  if (!isCurrent()) return
  try {
    if (isInProgressExploration.value) {
      const currentRoom = await siteStore.fetchCurrentRoom(id)
      if (isCurrent() && currentRoom?.exploration_id === id) showSiteModal.value = true
    }
  } catch {
    // Network failure — the entry CTA still works; don't block the page.
  }
  if (!isCurrent()) return
  await loadSiteOptions()
  if (isCurrent()) siteContextId.value = id
}

// Auto-refresh every 10 seconds. usePolling cleans up with this view scope.
usePolling(refreshExploration, { interval: 10_000, immediate: false })

onMounted(async () => {
  playMusic('exploration')
  if (vaultId.value && authStore.token) {
    await explorationStore.fetchExplorationsByVault(vaultId.value)

    explorationStore.startSseSubscription(vaultId.value, authStore.token)
    await initializeExplorer(explorationId.value)
  }
})

onUnmounted(() => {
  explorerLoadVersion++
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
  siteContextId.value = null
  await initializeExplorer(id)
})

watch([reportedSiteId, siteContextId], ([siteId, contextId]) => {
  if (siteId && contextId === explorationId.value) showSiteModal.value = true
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
                :can-recall="canRecall && !isReturning"
                @previous="navigatePrevious"
                @next="navigateNext"
                @recall="handleRecallExploration"
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

            <!-- Keep equipped items close to the explorer who carries them. -->
            <ExplorerEquipmentSlots
              :weapon-name="weaponName"
              :outfit-name="outfitName"
              :pet-name="petName"
              :weapon="detailedDweller?.weapon"
              :outfit="detailedDweller?.outfit"
              :pet="detailedDweller?.pet"
            />

            <!-- Expedition site entry CTA (in-progress journeys: active or returning) -->
            <Button
              v-if="isInProgressExploration"
              class="mb-4 w-full transition-shadow disabled:border disabled:border-theme-primary/60 disabled:bg-black disabled:text-theme-primary disabled:opacity-70 disabled:shadow-none"
              :class="siteCtaReady ? 'shadow-[var(--glow-2)]' : 'shadow-none'"
              :variant="siteCtaReady ? 'default' : 'secondary'"
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

            <!-- Action Buttons -->
            <ExplorerActions
              :can-complete="isReady"
              :can-recall="false"
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
            :reported-site-id="reportedSiteId"
            :pauses-travel="isInProgressExploration"
            :exploration-id="explorationId"
            :dweller-name="dwellerName"
            :dweller-image-url="dwellerImageUrl"
            :dweller-thumbnail-url="dwellerThumbnailUrl"
            :exploration-active="isInProgressExploration"
            @close="showSiteModal = false"
            @updated="handleSiteUpdated"
          />
        </PageContentRail>
      </div>
    </div>
  </div>
</template>
