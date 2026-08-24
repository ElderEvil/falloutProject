<script setup lang="ts">
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { getProgressPercentage as computeProgress } from '@/modules/exploration/composables/useExplorationProgress'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useToast } from '@/core/composables/useToast'
import { usePolling } from '@/core/composables/usePolling'
import type { RewardsSummary } from '@/modules/exploration/stores/exploration'
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

// Rewards modal state
const showRewardsModal = ref(false)
const completedExplorationRewards = ref<RewardsSummary | null>(null)
const completedDwellerName = ref('')

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
    const dweller = getDwellerById(pending.dwellerId)
    completedExplorationRewards.value = pending.rewards
    completedDwellerName.value = dweller ? `${dweller.first_name} ${dweller.last_name}` : 'Dweller'
    showRewardsModal.value = true
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
      const progress = getProgressPercentage(exploration.id)

      if (!dwellerStore.detailedDwellers[exploration.dweller_id]) {
        await dwellerStore.fetchDwellerDetails(exploration.dweller_id, authStore.token)
      }

      if (
        progress >= 100 &&
        exploration.status === 'active' &&
        !completingExplorations.value.has(exploration.id)
      ) {
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

const getProgressPercentage = (explorationId: string) => {
  const exploration = explorationStore.activeExplorations[explorationId]
  if (!exploration) return 0
  return computeProgress(exploration)
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

// --- Explorer actions ---

const recallDweller = async (explorationId: string) => {
  if (!authStore.token) return

  try {
    const exploration = explorationStore.activeExplorations[explorationId]
    if (!exploration) {
      toast.error('Exploration not found')
      return
    }

    const dweller = getDwellerById(exploration.dweller_id)
    if (!dweller) {
      toast.error('Dweller not found')
      return
    }

    const result = await explorationStore.recallDweller(explorationId, authStore.token)

    // Show rewards modal
    if (result?.rewards_summary) {
      completedExplorationRewards.value = result.rewards_summary
      completedDwellerName.value = `${dweller.first_name} ${dweller.last_name}`
      showRewardsModal.value = true
    }

    // Refresh vault and dweller data
    if (vaultId.value) {
      await vaultStore.refreshVault(vaultId.value, authStore.token)
      await dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token)
    }
  } catch (error) {
    toast.error('Failed to recall dweller')
  }
}

const handleCompleteExploration = async (explorationId: string) => {
  if (!authStore.token) return

  // Prevent duplicate calls
  if (completingExplorations.value.has(explorationId)) {
    return
  }

  completingExplorations.value.add(explorationId)

  try {
    const exploration = explorationStore.activeExplorations[explorationId]
    if (!exploration) {
      toast.error('Exploration not found')
      completingExplorations.value.delete(explorationId)
      return
    }

    const dweller = getDwellerById(exploration.dweller_id)
    if (!dweller) {
      toast.error('Dweller not found')
      completingExplorations.value.delete(explorationId)
      return
    }

    const result = await explorationStore.completeExploration(explorationId, authStore.token)

    // Show rewards modal
    if (result?.rewards_summary) {
      completedExplorationRewards.value = result.rewards_summary
      completedDwellerName.value = `${dweller.first_name} ${dweller.last_name}`
      showRewardsModal.value = true
    }

    // Refresh vault and dweller data
    if (vaultId.value) {
      await vaultStore.refreshVault(vaultId.value, authStore.token)
      await dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token)
    }
  } catch (error) {
    toast.error('Failed to complete exploration')
  } finally {
    completingExplorations.value.delete(explorationId)
  }
}

const closeRewardsModal = () => {
  showRewardsModal.value = false
  completedExplorationRewards.value = null
  completedDwellerName.value = ''
}

// Type assertion: dwellerStore.dwellers is DwellerShort[] at runtime but
// ActiveExplorationList expects Dweller[] (=DwellerReadFull). Both share
// id/first_name/last_name — the only fields the component reads.
const dwellerList = computed(() => dwellerStore.dwellers as unknown as Dweller[])

// Type assertion: dwellerStore.detailedDwellers can contain null values but
// ActiveExplorationList handles missing entries via `|| null` internally.
const detailedDwellerMap = computed(() =>
  dwellerStore.detailedDwellers as unknown as Record<string, Dweller>
)
</script>

<template>
  <div class="relative mb-4">
    <WastelandDropzone
      @drop-dweller="handleDropDweller"
      @drop-error="handleDropError"
    >
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
      @confirm="sendWasteland.confirm"
      @cancel="sendWasteland.cancel"
    />

    <!-- Rewards Modal -->
    <ExplorationRewardsModal
      :show="showRewardsModal"
      :rewards="completedExplorationRewards"
      :dweller-name="completedDwellerName"
      @close="closeRewardsModal"
    />
  </div>
</template>
