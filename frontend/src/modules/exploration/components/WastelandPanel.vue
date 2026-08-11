<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useToast } from '@/core/composables/useToast'
import { usePolling } from '@/core/composables/usePolling'
import { Icon } from '@iconify/vue'
import ExplorationRewardsModal from '@/modules/exploration/components/ExplorationRewardsModal.vue'
import type { RewardsSummary } from '@/modules/exploration/stores/exploration'

const route = useRoute()
const authStore = useAuthStore()
const { filter: dwellerStore, management: dwellerManagementStore } = useDwellerStore()
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

const isDraggingOver = ref(false)
const showDurationModal = ref(false)
const pendingDweller = ref<{
  dwellerId: string
  firstName: string
  lastName: string
  currentRoomId?: string
} | null>(null)
const selectedDuration = ref(4)
const selectedStimpaks = ref(0)
const selectedRadaways = ref(0)

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
    } catch (error) {
      toast.error('Failed to load explorations')
    }
  }
})

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

const getDetailedDweller = (dwellerId: string) => {
  return dwellerStore.detailedDwellers[dwellerId] || null
}

const getDwellerWeapon = (dwellerId: string) => {
  const detailed = getDetailedDweller(dwellerId)
  if (detailed?.weapon) return detailed.weapon
  return null
}

const getDwellerOutfit = (dwellerId: string) => {
  const detailed = getDetailedDweller(dwellerId)
  if (detailed?.outfit) return detailed.outfit
  return null
}

const handleDragOver = (event: DragEvent) => {
  event.preventDefault()
  event.dataTransfer!.dropEffect = 'move'
  isDraggingOver.value = true
}

const handleDragLeave = () => {
  isDraggingOver.value = false
}

const handleDrop = async (event: DragEvent) => {
  event.preventDefault()
  isDraggingOver.value = false

  try {
    const data = JSON.parse(event.dataTransfer!.getData('application/json'))
    const { dwellerId, firstName, lastName, currentRoomId } = data

    // Store dweller info and show duration modal
    pendingDweller.value = {
      dwellerId,
      firstName,
      lastName,
      currentRoomId,
    }

    // Default to 5 stimpaks and 5 radaways (capped by vault storage and dweller limit of 15)
    const DEFAULT_STIMPAKS = 5
    const DEFAULT_RADAWAYS = 5
    const DWELLER_MAX_SUPPLIES = 15

    selectedStimpaks.value = Math.min(
      DEFAULT_STIMPAKS,
      vaultMedicalSupplies.value.stimpaks,
      DWELLER_MAX_SUPPLIES
    )
    selectedRadaways.value = Math.min(
      DEFAULT_RADAWAYS,
      vaultMedicalSupplies.value.radaways,
      DWELLER_MAX_SUPPLIES
    )

    showDurationModal.value = true
  } catch (error) {
    toast.error('Failed to send dweller to wasteland')
  }
}

const confirmSendToWasteland = async () => {
  if (!pendingDweller.value || !vaultId.value) return
  if (!authStore.token) return

  try {
    const { dwellerId, firstName, lastName, currentRoomId } = pendingDweller.value

    // If dweller is assigned to a room, unassign them first
    if (currentRoomId) {
      await dwellerManagementStore.unassignDwellerFromRoom(dwellerId, authStore.token)
    }

    // Send to wasteland
    await explorationStore.sendDwellerToWasteland(
      vaultId.value,
      dwellerId,
      selectedDuration.value,
      authStore.token,
      selectedStimpaks.value,
      selectedRadaways.value
    )

    toast.success(
      `${firstName} ${lastName} sent to the wasteland for ${selectedDuration.value} hour(s)!`
    )

    // Close modal and reset
    showDurationModal.value = false
    pendingDweller.value = null
    selectedDuration.value = 4
    selectedStimpaks.value = 0
    selectedRadaways.value = 0
  } catch (error) {
    toast.error('Failed to send dweller to wasteland')
  }
}

const cancelSend = () => {
  showDurationModal.value = false
  pendingDweller.value = null
  selectedDuration.value = 4
  selectedStimpaks.value = 0
  selectedRadaways.value = 0
}

const formatTimeRemaining = (seconds: number) => {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return `${hours}h ${minutes}m`
}

const getProgressPercentage = (explorationId: string) => {
  const exploration = explorationStore.activeExplorations[explorationId]
  if (!exploration) return 0

  const now = Date.now()
  // Parse as UTC by appending 'Z' if not present
  let startTimeStr = exploration.start_time
  if (!startTimeStr.endsWith('Z')) {
    startTimeStr = startTimeStr.replace(' ', 'T') + 'Z'
  }
  const start = new Date(startTimeStr).getTime()
  const duration = exploration.duration * 3600 * 1000 // hours to ms
  const elapsed = now - start

  return Math.min(100, (elapsed / duration) * 100)
}

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
</script>

<template src="./WastelandPanel.template.html"></template>

<style src="./WastelandPanel.css" scoped></style>
