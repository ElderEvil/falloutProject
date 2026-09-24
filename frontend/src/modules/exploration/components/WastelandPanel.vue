<script setup lang="ts">
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { isReadyToComplete } from '@/modules/exploration/composables/useExplorationProgress'
import { useExplorationFinish } from '@/modules/exploration/composables/useExplorationFinish'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useToast } from '@/core/composables/useToast'
import { usePolling } from '@/core/composables/usePolling'
import type { Dweller } from '@/modules/dwellers/models/dweller'
import WastelandDropzone from '@/modules/exploration/components/WastelandDropzone.vue'
import ActiveExplorationList from '@/modules/exploration/components/ActiveExplorationList.vue'
import ExplorationDurationModal from '@/modules/exploration/components/ExplorationDurationModal.vue'
import ExplorationRewardsModal from '@/modules/exploration/components/ExplorationRewardsModal.vue'
import { useSendToWasteland } from '@/modules/exploration/composables/useSendToWasteland'

const route = useRoute()
const authStore = useAuthStore()
const { filter: dwellerStore } = useDwellerStore()
const explorationStore = useExplorationStore()
const vaultStore = useVaultStore()
const toast = useToast()

const vaultId = computed(() => route.params.id as string)

const currentVault = computed(() => (vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null))
const vaultMedicalSupplies = computed(() => {
  const v = currentVault.value
  return {
    stimpaks: v?.stimpack ?? 0,
    radaways: v?.radaway ?? 0,
  }
})

const sendWasteland = useSendToWasteland(() => vaultId.value)

watch(vaultId, () => sendWasteland.cancel())

// Rewards modal state
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

// Track explorations being completed to prevent duplicate calls
const completingExplorations = ref<Set<string>>(new Set())

// Fetch active explorations on mount
onMounted(async () => {
  if (vaultId.value && authStore.token) {
    // Ensure vault is loaded for medical supplies
    if (!vaultStore.loadedVaults[vaultId.value]) {
      await vaultStore.loadVault(vaultId.value, authStore.token)
    }
    try {
      await explorationStore.fetchExplorationsByVault(vaultId.value, authStore.token)

      // Fetch full dweller data for explorers (includes weapon/outfit)
      for (const exploration of activeExplorationsArray.value) {
        await dwellerStore.fetchDwellerDetails(exploration.dweller_id, authStore.token)
      }

      explorationStore.startSseSubscription(vaultId.value, authStore.token)
    } catch (error) {
      toast.error('Failed to load explorations')
    }
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
    if (explorationStore.consumeAcknowledgedSseReward(pending.dwellerId)) {
      explorationStore.clearPendingSseRewards()
      return
    }
    const dweller = getDwellerById(pending.dwellerId)
    openRewards(
      pending.rewards,
      dweller ? `${dweller.first_name} ${dweller.last_name}` : 'Dweller',
      pending.explorationId ?? ''
    )
    explorationStore.clearPendingSseRewards()
  }
)

// Poll for exploration updates every 30 seconds. usePolling owns cleanup when
// this component's scope is disposed and prevents overlapping refreshes.
const pollExplorations = async () => {
  if (!vaultId.value || !authStore.token || !explorationStore.activeExplorations) return

  try {
    await explorationStore.fetchExplorationsByVault(vaultId.value, authStore.token)

    // Check for completed explorations and fetch detailed data for new explorers
    for (const exploration of activeExplorationsArray.value) {
      if (!dwellerStore.detailedDwellers[exploration.dweller_id]) {
        await dwellerStore.fetchDwellerDetails(exploration.dweller_id, authStore.token)
      }

      if (isReadyToComplete(exploration) && !completingExplorations.value.has(exploration.id)) {
        await handleCompleteExploration(exploration.id)
      }
    }
  } catch (error) {
    toast.error('Failed to refresh explorations')
  }
}

usePolling(pollExplorations, { interval: 30_000, immediate: false })

const activeExplorationsArray = computed(() => {
  return Object.values(explorationStore.activeExplorations)
})

const getDwellerById = (dwellerId: string) => {
  return dwellerStore.dwellers.find((d) => d.id === dwellerId)
}

// --- Dropzone handlers ---

const handleDropDweller = (payload: {
  dwellerId: string
  firstName: string
  lastName: string
  currentRoomId?: string
}) => {
  sendWasteland.open(payload)
}

const handleDropError = (message: string) => {
  toast.error(message)
}

const handleSendWastelandConfirm = (payload: {
  duration: number
  stimpaks: number
  radaways: number
}) =>
  sendWasteland.confirm(payload, () =>
    Promise.all([
      vaultStore.refreshVault(vaultId.value, authStore.token as string),
      dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token as string),
    ]).then(() => undefined)
  )

// --- Explorer actions ---

const recallDweller = (explorationId: string) =>
  runExplorationFinish(explorationId, explorationStore.recallDweller, 'Failed to recall dweller')

const handleCompleteExploration = async (explorationId: string) => {
  if (!authStore.token) return
  if (completingExplorations.value.has(explorationId)) return

  completingExplorations.value.add(explorationId)

  try {
    await runExplorationFinish(
      explorationId,
      explorationStore.completeExploration,
      'Failed to complete exploration'
    )
  } finally {
    completingExplorations.value.delete(explorationId)
  }
}

const closeRewardsModal = async () => {
  if (!(await refreshIfDirty())) return
  resetRewards()
}

// Type assertion: dwellerStore.dwellers is DwellerShort[] at runtime but
// ActiveExplorationList expects Dweller[] (=DwellerReadFull). Both share
// id/first_name/last_name — the only fields the component reads.
const dwellerList = computed(() => dwellerStore.dwellers as unknown as Dweller[])

// Type assertion: dwellerStore.detailedDwellers can contain null values but
// ActiveExplorationList handles missing entries via `|| null` internally.
const detailedDwellerMap = computed(
  () => dwellerStore.detailedDwellers as unknown as Record<string, Dweller>
)
</script>

<template>
  <div class="relative mb-4">
    <WastelandDropzone @drop-dweller="handleDropDweller" @drop-error="handleDropError">
      <ActiveExplorationList
        :explorations="activeExplorationsArray"
        :dwellers="dwellerList"
        :detailed-dwellers="detailedDwellerMap"
        :vault-id="vaultId"
        @recall="recallDweller"
        @complete="handleCompleteExploration"
      />
    </WastelandDropzone>

    <!-- Duration Selection Modal -->
    <ExplorationDurationModal
      :show="sendWasteland.showModal.value"
      :dweller-name="sendWasteland.pendingDweller.value?.firstName ?? ''"
      :max-stimpaks="vaultMedicalSupplies.stimpaks"
      :max-radaways="vaultMedicalSupplies.radaways"
      @confirm="handleSendWastelandConfirm"
      @cancel="sendWasteland.cancel"
    />

    <!-- Rewards Modal -->
    <ExplorationRewardsModal
      :show="showRewardsModal"
      :rewards="completedExplorationRewards"
      :dweller-name="completedDwellerName"
      :exploration-id="completedExplorationId"
      @close="closeRewardsModal"
      @resolved="rewardsDirty = true"
    />
  </div>
</template>
