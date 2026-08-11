<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useExplorationStore } from '../stores/exploration'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { Icon } from '@iconify/vue'
import ExplorationRewardsModal from '../components/ExplorationRewardsModal.vue'
import type { RewardsSummary } from '../stores/exploration'
import { getEventIcon, getEventColor } from '../models/exploration'
import { usePolling } from '@/core/composables/usePolling'
import { useToast } from '@/core/composables/useToast'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { filter: dwellerStore } = useDwellerStore()
const explorationStore = useExplorationStore()
const vaultStore = useVaultStore()
const toast = useToast()

const vaultId = computed(() => route.params.id as string)
const explorationId = computed(() => route.params.explorationId as string)

// Rewards modal state
const showRewardsModal = ref(false)
const completedExplorationRewards = ref<RewardsSummary | null>(null)
const completedDwellerName = ref('')

// Current exploration and dweller
const exploration = computed(() => {
  return explorationStore.activeExplorations[explorationId.value]
})

const dweller = computed(() => {
  if (!exploration.value) return null
  return dwellerStore.dwellers.find((d) => d.id === exploration.value!.dweller_id)
})

const detailedDweller = computed(() => {
  if (!exploration.value) return null
  return dwellerStore.detailedDwellers[exploration.value.dweller_id] || null
})

const dwellerName = computed(() => {
  if (!dweller.value) return 'Unknown'
  return `${dweller.value.first_name} ${dweller.value.last_name}`
})

// Navigation between explorers
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

// Progress calculation
const progressPercentage = computed(() => {
  if (!exploration.value) return 0
  const now = Date.now()
  let startTimeStr = exploration.value.start_time
  if (!startTimeStr.endsWith('Z')) {
    startTimeStr = startTimeStr.replace(' ', 'T') + 'Z'
  }
  const start = new Date(startTimeStr).getTime()
  const duration = exploration.value.duration * 3600 * 1000
  const elapsed = now - start
  return Math.min(100, (elapsed / duration) * 100)
})

const timeRemaining = computed(() => {
  if (!exploration.value) return ''
  const progress = progressPercentage.value
  if (progress >= 100) return 'Complete!'

  const totalDuration = exploration.value.duration * 3600
  const remaining = totalDuration * (1 - progress / 100)

  const hours = Math.floor(remaining / 3600)
  const minutes = Math.floor((remaining % 3600) / 60)

  if (hours > 0) {
    return `${hours}h ${minutes}m remaining`
  }
  return `${minutes}m remaining`
})

// Events sorted by timestamp (most recent first)
const sortedEvents = computed(() => {
  if (!exploration.value?.events || exploration.value.events.length === 0) {
    return []
  }
  return [...exploration.value.events].reverse()
})

const formatEventTime = (hours: number): string => {
  const h = Math.floor(hours)
  const m = Math.floor((hours - h) * 60)
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

// Actions
const handleCompleteExploration = async () => {
  if (!authStore.token || !exploration.value) return

  try {
    const result = await explorationStore.completeExploration(exploration.value.id, authStore.token)

    if (result?.rewards_summary) {
      completedExplorationRewards.value = result.rewards_summary
      completedDwellerName.value = dwellerName.value
      showRewardsModal.value = true
    }

    if (vaultId.value) {
      await vaultStore.refreshVault(vaultId.value, authStore.token)
      await dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token)
    }

    // Don't auto-navigate - let user close modal first
  } catch (error) {
    toast.error('Failed to complete exploration')
  }
}

const handleRecallExploration = async () => {
  if (!authStore.token || !exploration.value) return

  try {
    const result = await explorationStore.recallDweller(exploration.value.id, authStore.token)

    if (result?.rewards_summary) {
      completedExplorationRewards.value = result.rewards_summary
      completedDwellerName.value = dwellerName.value
      showRewardsModal.value = true
    }

    if (vaultId.value) {
      await vaultStore.refreshVault(vaultId.value, authStore.token)
      await dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token)
    }

    // Don't auto-navigate - let user close modal first
  } catch (error) {
    toast.error('Failed to recall dweller')
  }
}

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

    // Fetch full dweller data for the explorer (includes weapon/outfit)
    if (exploration.value) {
      await dwellerStore.fetchDwellerDetails(exploration.value.dweller_id, authStore.token)
    }
  }

})

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

<template src="./ExplorationDetailView.template.html"></template>

<style src="./ExplorationDetailView.css" scoped></style>
