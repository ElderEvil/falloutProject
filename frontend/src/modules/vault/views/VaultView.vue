<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useVaultStore } from '../stores/vault'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { isUnassignable } from '@/modules/dwellers/models/dweller'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import { useSound } from '@/core/composables/useSound'
import RoomGrid from '@/modules/rooms/components/RoomGrid.vue'
import BuildModeButton from '@/core/components/common/BuildModeButton.vue'
import RoomMenu from '@/modules/rooms/components/RoomMenu.vue'
import GameControlPanel from '@/modules/vault/components/shell/GameControlPanel.vue'
import { getOverseerAttentionCount } from '@/modules/vault/models/overseerBriefing'
import UnassignedDwellers from '@/modules/dwellers/components/UnassignedDwellers.vue'
import WastelandPanel from '@/modules/exploration/components/WastelandPanel.vue'
import IncidentAlert from '@/modules/combat/components/incidents/IncidentAlert.vue'
import TerminalLoadingState from '@/core/components/common/TerminalLoadingState.vue'
import SidePanel from '@/core/components/common/SidePanel.vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { useToast } from '@/core/composables/useToast'
import { usePolling } from '@/core/composables/usePolling'
import type { RoomTemplate } from '@/modules/rooms/models/room'

interface Position {
  x: number
  y: number
}

const route = useRoute()
const authStore = useAuthStore()
const roomStore = useRoomStore()
const vaultStore = useVaultStore()
const toast = useToast()
const { filter: dwellerStore } = useDwellerStore()
const explorationStore = useExplorationStore()
const incidentStore = useIncidentStore()
const { playMusic } = useSound()
const { isCollapsed } = useSidePanel()
const showRoomMenu = ref(false)
const isLoading = ref(true)
const errorMessage = ref<string | null>(null)
const openRoomId = ref<string | null>(null)
const highlightedRoomId = ref<string | null>(null)

const buildModeActive = computed(() => showRoomMenu.value || roomStore.isPlacingRoom)

// Get vault ID from route params
const vaultId = computed(() => route.params.id as string)

// Use loadedVaults for real-time updates
const currentVault = computed(() => {
  return vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null
})

const dwellersCount = computed(() => currentVault.value?.dweller_count ?? 0)
const populationMax = computed(() => currentVault.value?.population_max ?? 0)
const populationUtilization = computed(() => {
  const max = populationMax.value
  const current = dwellersCount.value

  // Avoid division by zero
  if (!max || max === 0) return 0

  return (current / max) * 100
})

const happiness = computed(() => currentVault.value?.happiness ?? 0)

const resourceWarnings = computed(() => currentVault.value?.resource_warnings ?? [])
const activeExplorationCount = computed(
  () =>
    Object.values(explorationStore.activeExplorations).filter(
      (item) => item.vault_id === vaultId.value
    ).length
)
const trainingCount = computed(
  () => dwellerStore.dwellers.filter((dweller) => dweller.status === 'training').length
)
const questingCount = computed(
  () => dwellerStore.dwellers.filter((dweller) => dweller.status === 'questing').length
)
const unassignedCount = computed(
  () => dwellerStore.dwellers.filter((dweller) => isUnassignable(dweller)).length
)
const dwellersPath = computed(() => `/vault/${vaultId.value}/dwellers`)
const overseerBriefing = computed(() => ({
  vaultNumber: currentVault.value?.number ?? 0,
  activeIncidentCount: activeIncidents.value.length,
  activeExplorationCount: activeExplorationCount.value,
  trainingCount: trainingCount.value,
  questingCount: questingCount.value,
  unassignedCount: unassignedCount.value,
  populationUtilization: populationUtilization.value,
  happiness: happiness.value,
  resourceWarnings: resourceWarnings.value,
  dwellersPath: dwellersPath.value,
}))
const overseerAttentionCount = computed(() => getOverseerAttentionCount(overseerBriefing.value))

const activeIncidents = computed(() => incidentStore.activeIncidents)

usePolling(
  () =>
    vaultId.value && authStore.token
      ? vaultStore.fetchGameState(vaultId.value, authStore.token)
      : undefined,
  { interval: 60_000, immediate: false }
)

const loadVaultData = async (id: string) => {
  if (!id) {
    errorMessage.value = 'No vault ID provided in URL'
    isLoading.value = false
    return
  }

  if (!authStore.token) {
    errorMessage.value = 'Not authenticated. Please log in again.'
    isLoading.value = false
    return
  }

  try {
    isLoading.value = true
    errorMessage.value = null

    // Revalidate on overview entry; the shell's header load shares this request.
    await Promise.all([
      vaultStore.fetchVaults(authStore.token),
      vaultStore.revalidateVault(id, authStore.token),
    ])

    // Verify vault was loaded
    if (!vaultStore.loadedVaults[id]) {
      throw new Error('Vault not found')
    }

    // Fetch rooms for this vault
    await roomStore.fetchRooms(id, authStore.token)

    // Fetch dwellers for this vault
    await dwellerStore.fetchDwellersByVault(id, authStore.token)

    // Fetch explorations for this vault
    try {
      await explorationStore.fetchExplorationsByVault(id, authStore.token)
    } catch (error) {
      toast.warning('Vault loaded, but explorations could not be loaded')
      // Don't fail the whole page load if explorations fail
    }

    // Fetch game state (the shared vault action owns the tick stream)
    try {
      await vaultStore.fetchGameState(id, authStore.token)
    } catch (error) {
      // Game state not available, continuing without it
    }

    // Start incident polling
    incidentStore.startPolling(id, authStore.token)

    isLoading.value = false
  } catch (error) {
    toast.error('Failed to load vault')
    errorMessage.value = error instanceof Error ? error.message : 'Failed to load vault data'
    isLoading.value = false
  }
}

// Watch for room highlight query parameter
watch(
  () => route.query.roomId,
  (newRoomId) => {
    if (newRoomId && typeof newRoomId === 'string') {
      highlightedRoomId.value = newRoomId
      openRoomId.value = newRoomId
      // Clear highlight after 3 seconds
      setTimeout(() => {
        highlightedRoomId.value = null
      }, 3000)
    }
  },
  { immediate: true }
)

// Watch for vault ID changes in the URL
watch(
  () => vaultId.value,
  (newId) => {
    if (newId) {
      incidentStore.stopPolling()
      loadVaultData(newId)
    }
  },
  { immediate: true }
)

// Keyboard shortcuts
const handleKeyPress = (e: KeyboardEvent) => {
  // Ignore if event already handled
  if (e.defaultPrevented) return

  // Ignore if modifier keys are pressed (Ctrl/Cmd+B is for SidePanel)
  if (e.ctrlKey || e.metaKey || e.altKey) return

  // Only handle if not typing in an input, textarea, or contenteditable
  const target = e.target as HTMLElement
  if (
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target.isContentEditable
  ) {
    return
  }

  // Toggle build mode with 'B' key (layout-independent via code)
  if (e.code === 'KeyB') {
    e.preventDefault()
    toggleBuildMode()
  }

  // ESC to exit build mode
  if (e.key === 'Escape' && buildModeActive.value) {
    e.preventDefault()
    showRoomMenu.value = false
    roomStore.deselectRoom()
  }
}

onMounted(async () => {
  // Initial load is handled by the watcher
  window.addEventListener('keydown', handleKeyPress)
  playMusic('vaultAmbient')
})

onUnmounted(() => {
  // Stop incident polling; the resource tick stream is owned by the shell
  // (useVaultHeaderContext) so it survives navigation between vault routes.
  // Music is intentionally NOT stopped: audioManager is a global singleton,
  // so the ambient loop keeps playing across navigation (issue #620).
  incidentStore.stopPolling()
  window.removeEventListener('keydown', handleKeyPress)
})

const toggleBuildMode = async () => {
  if (buildModeActive.value) {
    // Cancel building
    showRoomMenu.value = false
    roomStore.deselectRoom()
  } else {
    // Enter build mode
    await roomStore.fetchBuildableRooms(authStore.token as string, vaultId.value)
    showRoomMenu.value = true
  }
}

const handleRoomSelected = (room: RoomTemplate) => {
  // roomStore.selectRoom(room) is already called by RoomMenu
  showRoomMenu.value = false
}

// Incident surfaces open the affected room's overlay, not a separate modal.
const handleIncidentClicked = (incidentId: string) => {
  const incident = incidentStore.getIncidentById(incidentId)
  if (incident) openRoomId.value = incident.room_id
}

const reviewActiveIncidents = () => {
  const incident = activeIncidents.value[0]
  if (incident) handleIncidentClicked(incident.id)
}
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-terminal-green">
    <!-- Loading State -->
    <TerminalLoadingState v-if="isLoading" full-height message="Loading vault data..." />

    <!-- Error State -->
    <div v-else-if="errorMessage" class="flex min-h-screen items-center justify-center">
      <div class="max-w-md rounded border-2 border-danger/60 bg-surface-raised p-8 text-center">
        <div class="mb-4 text-6xl">⚠️</div>
        <h2 class="mb-4 text-2xl font-bold text-danger">Error Loading Vault</h2>
        <p class="mb-6 text-terminal-green">{{ errorMessage }}</p>
        <router-link
          to="/"
          class="rounded bg-terminal-green px-6 py-2 font-bold text-black hover:bg-green-400"
        >
          Go to Vault List
        </router-link>
      </div>
    </div>

    <!-- Main Vault View -->
    <div v-else class="vault-layout">
      <!-- Side Panel -->
      <SidePanel />

      <!-- Main Content Area -->
      <div class="main-content flicker" :class="{ collapsed: isCollapsed }">
        <div class="container mx-auto flex flex-col items-center justify-center px-4 py-8 lg:px-8">
          <GameControlPanel v-if="vaultId" :vaultId="vaultId" />

          <!-- Incident Alert Banner -->
          <div v-if="activeIncidents.length > 0" class="w-full mb-4">
            <IncidentAlert :incidents="activeIncidents" @click="handleIncidentClicked" />
          </div>

          <!-- Unassigned Dwellers Panel -->
          <div class="w-full mb-4">
            <UnassignedDwellers />
          </div>

          <!-- Wasteland Panel -->
          <div class="w-full mb-8">
            <WastelandPanel />
          </div>

          <!-- Room Grid -->
          <div class="relative w-full">
            <div class="build-control absolute right-4 top-4 z-30">
              <BuildModeButton
                :buildModeActive="buildModeActive"
                @toggleBuildMode="toggleBuildMode"
              />
            </div>
            <RoomGrid
              :incidents="activeIncidents"
              :highlightedRoomId="highlightedRoomId"
              :open-room-id="openRoomId"
              :overseer-briefing="overseerBriefing"
              :overseer-attention-count="overseerAttentionCount"
              @room-opened="openRoomId = null"
              @review-incidents="reviewActiveIncidents"
            />
          </div>

          <!-- Build Menu -->
          <RoomMenu
            v-if="showRoomMenu"
            @roomSelected="handleRoomSelected"
            @close="showRoomMenu = false"
          />
        </div>
      </div>
    </div>
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
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.main-content p,
.main-content span,
.main-content div {
  text-shadow: 0 0 2px var(--color-theme-glow);
}

/* Build Control */
.build-control {
  animation: subtlePulse 3s ease-in-out infinite;
}

@keyframes subtlePulse {
  0%,
  100% {
    opacity: 0.95;
  }
  50% {
    opacity: 1;
  }
}
</style>
